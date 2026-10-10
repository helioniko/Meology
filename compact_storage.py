"""Lossless cold text and bounded regenerable caches/automatic snapshots."""
import gzip, shutil, sqlite3, uuid, hashlib
from datetime import datetime, timedelta
from pathlib import Path
from storage import TZ, today


def storage_stats(store):
    folder=store.path.parent.parent/'backups'
    files=[p for p in folder.iterdir() if p.is_file() and (p.name.endswith('.sqlite3') or p.name.endswith('.sqlite3.gz'))] if folder.exists() else []
    with store.connection() as c:
        packed=sum(c.execute('SELECT count(*) FROM '+t+' WHERE compressed_text IS NOT NULL').fetchone()[0] for t in ('records','messages','revisions'))
        cache=c.execute('SELECT coalesce(sum(length(CAST(result AS BLOB))),0) FROM summary_cache').fetchone()[0]+c.execute('SELECT coalesce(sum(length(vector)),0) FROM embedding_cache').fetchone()[0]
    with store.connection() as c:
        pending=c.execute("SELECT count(*) FROM messages WHERE role='user' AND retention_state='pending'").fetchone()[0]
        reviews=c.execute("SELECT count(*) FROM proposals WHERE status='pending' AND review_level='core'").fetchone()[0]
    size=store.path.stat().st_size
    for suffix in ('-wal','-shm'):
        try:size+=Path(str(store.path)+suffix).stat().st_size
        except FileNotFoundError:pass  # SQLite removes sidecars after the last connection closes.
    free=shutil.disk_usage(store.path.parent).free
    return {'pending_inputs':pending,'core_reviews':reviews,'database_bytes':size,'backup_bytes':sum(p.stat().st_size for p in files),'auto_backup_bytes':sum(p.stat().st_size for p in files if p.name.startswith('auto-')),'cache_bytes':cache,'compressed_entries':packed,'free_bytes':free,'warning':free<2*1024**3}


def maintain(store):
    settings=store.settings(); cutoff=(datetime.now(TZ)-timedelta(days=settings['compress_after_days'])).date().isoformat()
    saved=0
    with store.lock:
        with store.connection() as c:
            for table,column,extra,maximum in [('records','content'," AND kind='journal' AND content_state!='pending'",200),('messages','content','',400),('revisions','snapshot','',200)]:
                time_column='changed_at' if table=='revisions' else 'created_at'
                cursor_key='compression_cursor_'+table
                cursor_row=c.execute('SELECT value FROM metadata WHERE key=?',(cursor_key,)).fetchone()
                cursor=int(cursor_row[0]) if cursor_row and cursor_row[0].isdecimal() else 0
                rows=c.execute('SELECT id,'+column+' FROM '+table+' WHERE compressed_text IS NULL AND '+time_column+'<? AND id>?'+extra+' ORDER BY id LIMIT ?', (cutoff,cursor,maximum)).fetchall()
                c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',(cursor_key,str(rows[-1]['id'] if rows else 0)))
                for row in rows:
                    raw=row[column].encode('utf-8'); packed=gzip.compress(raw,compresslevel=6,mtime=0)
                    if 256<len(raw)<=2_000_000 and len(packed)+32<len(raw):
                        # Round-trip before removing the uncompressed representation.
                        if gzip.decompress(packed)!=raw: raise ValueError('无损压缩校验未通过')
                        c.execute('UPDATE '+table+' SET '+column+"='',compressed_text=? WHERE id=?",(packed,row['id'])); saved+=len(raw)-len(packed)
            limit=settings['cache_mb']*1024**2
            cache=[]
            for table,column in [('summary_cache','result'),('embedding_cache','vector')]:
                for r in c.execute('SELECT rowid, length(CAST('+column+' AS BLOB)) bytes FROM '+table+' ORDER BY rowid'):
                    cache.append((r['rowid'],table,r['bytes']))
            total=sum(r[2] for r in cache)
            for rowid,table,size in cache:
                if total<=limit: break
                c.execute('DELETE FROM '+table+' WHERE rowid=?',(rowid,)); total-=size
            # Completed queue payloads are reproducible from original records, not user memory.
            c.execute("UPDATE jobs SET payload='{}' WHERE status='done' AND created_at<?",(cutoff,))
        folder=(store.path.parent.parent/'backups').resolve()
        if folder.exists():
            for original in folder.glob('auto-personal-*.sqlite3'):
                if original.resolve().parent!=folder: continue
                target=original.with_suffix('.sqlite3.gz'); temp=folder/('.packing-'+uuid.uuid4().hex)
                try:
                    original_hash=hashlib.sha256()
                    with original.open('rb') as src, gzip.open(temp,'wb',compresslevel=6) as dst:
                        while chunk:=src.read(1024**2): original_hash.update(chunk); dst.write(chunk)
                    # Verify the entire compressed copy before replacing the auto snapshot.
                    restored_hash=hashlib.sha256()
                    with gzip.open(temp,'rb') as src:
                        while chunk:=src.read(1024**2): restored_hash.update(chunk)
                    if restored_hash.digest()!=original_hash.digest(): raise ValueError('自动备份压缩校验未通过，原备份保留')
                    temp.replace(target); original.unlink()
                finally: temp.unlink(missing_ok=True)
            copies=sorted([p for p in folder.glob('auto-personal-*') if p.is_file() and (p.name.endswith('.sqlite3') or p.name.endswith('.sqlite3.gz'))],reverse=True)
            total=sum(p.stat().st_size for p in copies); limit=settings['auto_backup_mb']*1024**2
            for p in reversed(copies[1:]):
                if len(copies)<=14 and total<=limit: break
                if p.resolve().parent==folder:
                    total-=p.stat().st_size; p.unlink(); copies.remove(p)
        # Reuse freed SQLite pages; compact the physical file only when it frees useful space.
        if saved>1024**2 and shutil.disk_usage(store.path.parent).free>store.path.stat().st_size*2+16*1024**2:
            with store.connection() as c: c.execute('VACUUM')
    return storage_stats(store)
