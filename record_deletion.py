"""Explicit deletion of journal facts and reviews, with transactional cleanup."""
import json
from datetime import date, timedelta
from data_format import decode_row
from storage import now, signature


def valid_id(value):
    if type(value) is not int or value <= 0:
        raise ValueError('记录编号无效')


def suppress_summary(c, row):
    start = row['period']
    end = (date.fromisoformat(start) + timedelta(days=6)).isoformat() if row['type'] == 'weekly' else start
    current = c.execute("SELECT id,updated_at FROM records WHERE kind='journal' AND archived=0 AND status='confirmed' AND share_with_ai=1 AND sensitivity='normal' AND content_state!='pending' AND event_date BETWEEN ? AND ? ORDER BY updated_at DESC,id DESC", (start, end))
    fingerprint = signature([(r['id'], r['updated_at']) for r in current])
    # Keep only the period and input fingerprint to avoid generating the same review again.
    c.execute("UPDATE summaries SET summary='',events='[]',ideas='[]',source_ids='[]',status='deleted',fingerprint=?,updated_at=? WHERE id=?", (fingerprint, now(), row['id']))
    c.execute("DELETE FROM jobs WHERE kind='summary' AND json_extract(payload,'$.period')=? AND json_extract(payload,'$.type')=?", (start, row['type']))


def delete_summary(store, sid):
    valid_id(sid)
    with store.connection() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute("SELECT * FROM summaries WHERE id=? AND status!='deleted'", (sid,)).fetchone()
        if not row:
            raise ValueError('回顾不存在或已删除')
        suppress_summary(c, row)
        c.execute('DELETE FROM summary_cache')


def delete_journal(store, rid):
    valid_id(rid)
    with store.connection() as c:
        c.execute('BEGIN IMMEDIATE')
        raw = c.execute('SELECT * FROM records WHERE id=?', (rid,)).fetchone()
        if not raw or raw['kind'] != 'journal':
            raise ValueError('只能删除记录与回顾中的日常记录')
        row = decode_row('records', raw)
        watermark = c.execute("SELECT value FROM metadata WHERE key='record_id_highwater'").fetchone()
        highest = max(int(watermark[0]) if watermark else 0, c.execute('SELECT max(id) FROM records').fetchone()[0])
        c.execute("INSERT OR REPLACE INTO metadata VALUES ('record_id_highwater',?)", (str(highest),))
        mid = row['source_message_id']
        affected = list(c.execute("SELECT p.id FROM proposals p LEFT JOIN metadata m ON m.key='dossier_plan:'||p.id WHERE p.record_id=? OR (p.status='pending' AND json_extract(m.value,'$.target_id')=?) OR (p.status='pending' AND ? IS NOT NULL AND EXISTS(SELECT 1 FROM json_each(p.source_ids) WHERE value=?))", (rid, rid, mid, mid)))
        pids = {p['id'] for p in affected}
        for pid in pids:
            # Retain source IDs and proposal IDs, but remove the deleted fact and candidate text.
            c.execute("UPDATE proposals SET record_id=NULL,field_key=NULL,title='已删除',content='',quote='',reason='',status='rejected' WHERE id=?", (pid,))
            for prefix in ('dossier_plan:', 'agenda_plan:'):
                c.execute('DELETE FROM metadata WHERE key=?', (prefix + str(pid),))
        for link in c.execute("SELECT key,value FROM metadata WHERE key LIKE 'dossier_links:%'"):
            info = json.loads(link['value'])
            records = [i for i in info['record_ids'] if i != rid]
            proposals = [i for i in info['proposal_ids'] if i not in pids]
            if records != info['record_ids'] or proposals != info['proposal_ids']:
                info.update(record_ids=records, proposal_ids=proposals)
                c.execute('UPDATE metadata SET value=? WHERE key=?', (json.dumps(info), link['key']))
        if mid:
            message = c.execute('SELECT * FROM messages WHERE id=?', (mid,)).fetchone()
            if message:
                first = c.execute("SELECT min(id) FROM messages WHERE session_id=? AND role='user' AND retention_state!='discarded'", (message['session_id'],)).fetchone()[0]
                if first == mid:
                    c.execute("UPDATE sessions SET title='新的记录' WHERE id=?", (message['session_id'],))
            # Bare source metadata remains valid for other facts; deleted input cannot be retried.
            c.execute("UPDATE messages SET content='',compressed_text=NULL,compact_content='',share_with_ai=0,organized=1,organize_offset=0,retention_state='discarded' WHERE id=? OR answer_for=?", (mid, mid))
            c.execute("DELETE FROM jobs WHERE (kind='chat' AND json_extract(payload,'$.message_id')=?) OR (kind='organize' AND EXISTS(SELECT 1 FROM json_each(payload,'$.messages') WHERE json_extract(value,'$.id')=?))", (mid, mid))
            c.execute('DELETE FROM entry_digests WHERE EXISTS(SELECT 1 FROM json_each(source_ids) WHERE value=?)', (mid,))
        c.execute('DELETE FROM revisions WHERE record_id=?', (rid,))
        for chunk in list(c.execute('SELECT id FROM memory_chunks WHERE record_id=?', (rid,))):
            c.execute('DELETE FROM memory_fts WHERE rowid=?', (chunk['id'],))
        c.execute('DELETE FROM memory_chunks WHERE record_id=?', (rid,))
        c.execute('DELETE FROM metadata WHERE key IN (?,?)', ('dossier_origin:' + str(rid), 'agenda:' + str(rid)))
        c.execute('DELETE FROM records WHERE id=?', (rid,))
        c.execute('DELETE FROM memory_dirty WHERE record_id=?', (rid,))
        for summary in list(c.execute("SELECT * FROM summaries WHERE status!='deleted' AND EXISTS(SELECT 1 FROM json_each(source_ids) WHERE value=?)", (rid,))):
            suppress_summary(c, summary)
        c.execute('DELETE FROM summary_cache')
        c.execute('DELETE FROM embedding_cache')
