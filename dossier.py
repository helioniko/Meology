"""Evidence-based dossier updates using stable record keys, not new SQL columns."""
import hashlib, json, re, unicodedata, uuid
from datetime import date
from data_format import decode_row, DataFormatError
from profile_schema import FIELD_MAP, FIELDS, validate_answer

VERSION = 1
RULES = ['所有个人信息方向均可发现新主题、建立档案并持续增加属性', '同一属性的重复信息合并，不重复保存', '同一属性的变化更新现状，保留必要历史',
         '重要经历、决定和想法保留简短时间线', '核心修改和 AI 推测经本人审核',
         '提取、校验和保存成功后清除原文，不另存每次聊天摘要']
TIMELINE_FIELDS = {'city', 'school', 'workplace', 'job_title', 'education_status', 'employment_status', 'relationship_status'}
CORE_WORDS = ('价值观', '决策原则', '思考模式', '人格', '性格', '底线', '长期目标', '姓名', '出生日期', '身份证', '血型', '确诊', '诊断', '婚姻', '学历', '工作单位', '离婚', '结婚', '买房', '辞职', '退学', '贷款')


def canonical(text):
    return re.sub(r'[\W_]+', '', unicodedata.normalize('NFKC', str(text)).casefold())


def fingerprint(text):
    return hashlib.sha256(str(text).encode()).hexdigest()


def load_registry(c):
    row = c.execute("SELECT value FROM metadata WHERE key='dossier_fields'").fetchone()
    return json.loads(row[0]) if row else dict(version=VERSION, fields=[])


def check_metadata(c):
    registry = load_registry(c)
    if not isinstance(registry, dict) or type(registry.get('version')) is not int or registry['version'] != VERSION:
        raise DataFormatError('扩展档案来自未支持的版本，请升级软件')
    fields = registry.get('fields')
    if not isinstance(fields, list):
        raise DataFormatError('扩展档案字段格式无效')
    keys = set(); identities = set()
    for field in fields:
        if not isinstance(field, dict) or set(field) != {'key', 'title', 'category', 'subject', 'kind'}:
            raise DataFormatError('扩展档案字段定义无效')
        if any(not isinstance(field[k], str) or not field[k].strip() or len(field[k]) > 100 for k in field):
            raise DataFormatError('扩展档案字段内容无效')
        key = field['key']; identity = (canonical(field['subject']), canonical(field['title']))
        if not re.fullmatch(r'custom\.[0-9a-f]{32}', key) or key in keys or identity in identities or field['kind'] not in ('profile', 'state', 'memory', 'project'):
            raise DataFormatError('扩展档案编号或语义冲突')
        keys.add(key); identities.add(identity)
    if set(registry) != {'version','fields'}:raise DataFormatError('扩展档案有未支持的字段')
    for row in c.execute("SELECT key,value FROM metadata WHERE key LIKE 'dossier_plan:%' OR key LIKE 'dossier_origin:%' OR key LIKE 'dossier_links:%'"):
        try: info=json.loads(row[1])
        except (ValueError,TypeError):raise DataFormatError('档案更新元数据无效') from None
        if not isinstance(info,dict) or type(info.get('version')) is not int or info['version']!=VERSION:
            raise DataFormatError('档案更新元数据来自未支持的版本')
        try:rid=int(row[0].split(':')[1]);assert rid>0
        except (ValueError,AssertionError):raise DataFormatError('档案元数据编号无效') from None
        if row[0].startswith('dossier_links:'):
            if set(info)!={'version','record_ids','proposal_ids'} or not c.execute('SELECT 1 FROM messages WHERE id=?',(rid,)).fetchone():raise DataFormatError('档案输入关联无效')
            for key,table in [('record_ids','records'),('proposal_ids','proposals')]:
                if not isinstance(info[key],list) or len(info[key])>128 or any(type(i) is not int or i<=0 or not c.execute('SELECT 1 FROM '+table+' WHERE id=?',(i,)).fetchone() for i in info[key]):raise DataFormatError('档案关联编号无效')
        elif row[0].startswith('dossier_plan:'):
            if set(info)!={'version','operation','target_id','expected_hash','category','event_date'} or info['operation'] not in ('create','update','merge','ignore'):
                raise DataFormatError('档案更新计划有未支持的字段或操作')
            if info['target_id'] is not None and (type(info['target_id']) is not int or info['target_id']<=0):raise DataFormatError('档案更新目标无效')
            if not isinstance(info['category'],str) or len(info['category'])>100 or not isinstance(info['expected_hash'],str) or (info['expected_hash'] and not re.fullmatch('[0-9a-f]{64}',info['expected_hash'])):raise DataFormatError('档案更新计划无效')
            try:date.fromisoformat(info['event_date'])
            except (TypeError,ValueError):raise DataFormatError('档案更新日期无效') from None
            if not c.execute('SELECT 1 FROM proposals WHERE id=?',(rid,)).fetchone():raise DataFormatError('档案更新缺少候选来源')
        else:
            if set(info)!={'version','parent_record','source_ids','content_hash'} or type(info['parent_record']) is not int or info['parent_record']<=0 or info['parent_record']==rid:raise DataFormatError('档案变化来源无效')
            parent=c.execute('SELECT field_key FROM records WHERE id=?',(info['parent_record'],)).fetchone()
            if not parent or not parent[0] or parent[0].startswith(('event.','idea.')) or not c.execute('SELECT 1 FROM records WHERE id=?',(rid,)).fetchone():raise DataFormatError('档案变化缺少原档案')
            if not isinstance(info['source_ids'],list) or any(type(mid) is not int or mid<=0 or not c.execute('SELECT 1 FROM messages WHERE id=?',(mid,)).fetchone() for mid in info['source_ids']):raise DataFormatError('档案变化输入来源无效')
            if not isinstance(info['content_hash'],str) or not re.fullmatch('[0-9a-f]{64}',info['content_hash']):raise DataFormatError('档案变化摘要校验无效')



def fields_for(store):
    with store.connection() as c: registry = load_registry(c)
    return FIELDS + [(f['key'], (f['title'] if f['subject']=='本人' else f['subject']+' · '+f['title']), f['category'], 'textarea') for f in registry['fields']]


def validate_field(c, key, value):
    if key in FIELD_MAP:
        return validate_answer(key, value)
    if not isinstance(value, str) or len(value.strip()) > 3000:
        raise ValueError('档案内容无效或过长')
    if re.fullmatch(r'task\.[0-9a-f]{64}',key):return value.strip()
    if key not in {f['key'] for f in load_registry(c)['fields']}:
        raise ValueError('档案字段不存在')
    return value.strip()


class Writer:
    def __init__(self, store, c):
        self.store = store; self.c = c; self.registry = load_registry(c)

    def slot(self, item, old=None):
        key = item.get('field_key') or ''
        if old: key = old.get('field_key') or key
        if key in FIELD_MAP:
            if str(item.get('subject') or '本人') != '本人': raise ValueError('本人字段不能保存其他人的信息')
            spec = FIELD_MAP[key]
            return dict(key=key, title=spec[1], category=spec[2], subject='本人', kind='profile')
        if key.startswith('task.'):
            raise ValueError('日程更新必须包含日程时间和状态')
        if key.startswith(('event.', 'idea.')):
            return dict(key=key, title=old['title'], category=old['category'], subject=item.get('subject', '本人'), kind=old['kind'])
        subject = str(item.get('subject') or '本人').strip()[:80]
        title = str(item.get('title') or item.get('field_name') or '').strip()[:80]
        if not title or not canonical(title): raise ValueError('新增档案需要明确的项目名称')
        for spec in self.registry['fields']:
            if spec['key'] == key or (canonical(spec['title']) == canonical(title) and canonical(spec['subject']) == canonical(subject)):
                if canonical(spec['subject']) != canonical(subject): raise ValueError('不能把他人的信息写入本人的档案')
                return spec
        if key.startswith('custom.'): raise ValueError('目标档案编号不存在')
        kind = item.get('kind', 'memory')
        if kind not in ('profile', 'state', 'memory', 'project'): kind = 'memory'
        spec = dict(key='custom.' + uuid.uuid4().hex, title=title,
                    category=str(item.get('category') or '其他档案').strip()[:80], subject=subject, kind=kind)
        self.registry['fields'].append(spec)
        self.c.execute("INSERT OR REPLACE INTO metadata VALUES ('dossier_fields',?)", (json.dumps(self.registry, ensure_ascii=False),))
        return spec

    def prepare(self, item, originals):
        if not isinstance(item, dict): raise ValueError('档案更新格式无效')
        text = str(item.get('content', '')).strip(); quote = str(item.get('quote', '')).strip()
        ids = item.get('source_ids', [])
        if not text or len(text) > 500 or not quote or not isinstance(ids, list) or not ids or any(type(i) is not int or i not in originals for i in ids) or not any(quote in originals[i]['content'] for i in ids):
            raise ValueError('档案更新缺少有效输入依据')
        modern = bool(item.get('_structured'))
        if not modern and item.get('kind') != 'profile' and text not in quote:
            raise ValueError('旧格式的普通信息必须有逐字依据')
        if item.get('kind') not in ('profile', 'state', 'memory', 'project', 'decision', 'journal'):
            raise ValueError('档案更新类型无效')
        operation = item.get('operation') or 'create'
        if operation not in ('create', 'update', 'merge', 'ignore'): raise ValueError('档案更新操作无效')
        target = item.get('target_id')
        if target is not None and (type(target) is not int or target <= 0): raise ValueError('目标记录编号无效')
        old = self.c.execute('SELECT * FROM records WHERE id=? AND archived=0', (target,)).fetchone() if target else None
        old = decode_row('records', old) if old else None
        if target and not old: raise ValueError('目标记录已变化，请重新整理')
        field = item.get('field_key') or ''
        if not modern and item['kind']=='profile' and field not in FIELD_MAP: raise ValueError('旧格式档案字段无效')
        if old and field and field != old['field_key']: raise ValueError('目标记录与档案字段不一致')
        if not old and field:
            row = self.c.execute('SELECT * FROM records WHERE field_key=? AND archived=0', (field,)).fetchone()
            old = decode_row('records', row) if row else None
        if old and (old.get('field_key') or '').startswith('task.') and 'agenda' not in item:raise ValueError('日程更新必须包含日期与状态')
        if old and (not old['share_with_ai'] or old['sensitivity'] != 'normal'):
            raise ValueError('目标档案仅本地保存，请手动修改')
        event_date = str(item.get('event_date') or max(originals[i]['date'] for i in ids))
        date.fromisoformat(event_date)
        memory_type = item.get('memory_type') or ('fact' if field or item['kind'] in ('profile', 'state', 'project') else 'event')
        if memory_type not in ('fact', 'state', 'event', 'idea'): raise ValueError('档案内容类别无效')
        # Old candidate formats are literal timeline items unless they identify a fixed field.
        if not modern and not field and item['kind'] in ('memory', 'decision', 'journal'): memory_type = 'event'
        if old and old['field_key'] and old['field_key'].startswith(('event.', 'idea.')):
            memory_type = 'event' if old['field_key'].startswith('event.') else 'idea'
        if old and old['event_date'] and event_date < old['event_date'] and memory_type in ('fact', 'state'):
            # A recollection must not replace the latest known value.
            memory_type = 'event'; target = None; old = None; field = ''; operation = 'create'
            item = {**item, 'title': str(item.get('title') or FIELD_MAP.get(item.get('field_key'), ('', '档案变化'))[1]) + '（过去的经历）'}
        agenda_info=None
        if 'agenda' in item:
            from agenda import slot as agenda_slot,validate_source_time
            if field in FIELD_MAP or item['kind']!='project' or memory_type!='fact':raise ValueError('日程不能修改个人核心字段')
            spec,text,agenda_info=agenda_slot(item,old,self.c)
            validate_source_time(item,originals,old,self.c)
        elif memory_type in ('event', 'idea'):
            title = str(item.get('title') or text[:50]).strip()[:80]
            key = old['field_key'] if old else ('idea.' if memory_type == 'idea' else 'event.') + fingerprint(canonical(str(item.get('subject') or '本人')) + '|' + event_date + '|' + canonical(text))
            spec = dict(key=key, title=title, category=str(item.get('category') or ('想法' if memory_type == 'idea' else '重要经历'))[:80], subject=str(item.get('subject') or '本人'), kind='journal')
        else:
            spec = self.slot(item, old)
        if not old:
            row = self.c.execute('SELECT * FROM records WHERE field_key=? AND archived=0', (spec['key'],)).fetchone()
            old = decode_row('records', row) if row else None
        if old and canonical(old['content']) == canonical(text):
            return dict(operation='ignore', record_id=old['id'], title=old['title'])
        if operation == 'ignore': raise ValueError('忽略操作必须与已知内容一致，不能丢弃新信息')
        if old and modern and operation == 'create' and memory_type in ('fact', 'state'):
            raise ValueError('该档案项已经存在，应明确选择更新或合并')
        if operation == 'merge' and (not old or old['content'] not in text):
            raise ValueError('合并必须保留已有信息，不能静默遗漏')
        if operation in ('update', 'merge') and not old: raise ValueError('更新目标不存在')
        inferred = item.get('inferred', False)
        if type(inferred) is not bool: raise ValueError('推测标识无效')
        critical = spec['kind'] == 'profile' or inferred or any(w in (spec['title'] + ' ' + text) for w in CORE_WORDS)
        if old and old['kind'] == 'profile': critical = True
        if modern and spec['key'] in FIELD_MAP: text = validate_answer(spec['key'], text)
        expected = item.get('_expected_hash')
        if old and expected and expected != fingerprint(old['content']): raise ValueError('目标资料在整理期间发生变化，重新整理后再写入')
        # Merge provenance includes the existing component, so revocation stays effective.
        if operation == 'merge' and old:
            previous = self.c.execute("SELECT source_ids FROM proposals WHERE record_id=? AND content=? AND status IN ('confirmed','automatic') ORDER BY id DESC LIMIT 1", (old['id'], old['content'])).fetchone()
            if previous: ids = list(dict.fromkeys(json.loads(previous[0]) + ids))
        key = fingerprint(json.dumps([spec['key'], text, operation if old else 'create'], ensure_ascii=False))
        pending = self.c.execute("SELECT id FROM proposals WHERE dedupe_key=? AND status='pending'", (key,)).fetchone()
        if pending: return dict(operation='pending', proposal_id=pending[0], title=spec['title'])
        if self.c.execute('SELECT 1 FROM proposals WHERE dedupe_key=?',(key,)).fetchone(): key += '.' + uuid.uuid4().hex
        title = spec['title'] if spec['subject']=='本人' else spec['subject'] + ' · ' + spec['title']
        from storage import now
        pid = self.c.execute('INSERT INTO proposals(dedupe_key,kind,field_key,title,content,quote,source_ids,reason,review_level,evidence_verified,created_at) VALUES (?,?,?,?,?,?,?,?,?,1,?)',
            (key, spec['kind'], spec['key'], title, text, '输入依据已校验；仅保留提取信息', json.dumps(ids), str(item.get('reason') or ('更新已有档案' if old else '新增档案信息'))[:160], 'core' if critical else 'routine', now())).lastrowid
        plan = dict(version=VERSION, operation=operation if old else 'create', target_id=old['id'] if old else None,
                    expected_hash=fingerprint(old['content']) if old else '', category=spec['category'], event_date=event_date)
        self.c.execute('INSERT INTO metadata VALUES (?,?)', ('dossier_plan:' + str(pid), json.dumps(plan, ensure_ascii=False)))
        if agenda_info:self.c.execute('INSERT INTO metadata VALUES (?,?)',('agenda_plan:'+str(pid),json.dumps(agenda_info)))
        if critical: return dict(operation='pending', proposal_id=pid, title=spec['title'])
        rid = self.resolve(pid, 'automatic')
        return dict(operation=plan['operation'], record_id=rid, proposal_id=pid, title=spec['title'])

    def apply(self, items, messages):
        if not isinstance(items, list) or len(items) > 64: raise ValueError('档案更新条目过多或格式无效')
        originals = {m['id']: dict(content=m.get('evidence_content', m['content']), date=m.get('source_event_date') or m.get('created_at', '')[:10], recorded_at=m.get('created_at') or '') for m in messages if m.get('role') == 'user' and m.get('share_with_ai')}
        # Membership evidence operates on content; retain dates separately for temporal updates.
        outcomes = []
        for item in items:
            try:
                outcome=self.prepare(item, originals);outcomes.append(outcome)
                # Small ID references let the window display current facts without scanning all history.
                for mid in item['source_ids']:
                    key='dossier_links:'+str(mid);row=self.c.execute('SELECT value FROM metadata WHERE key=?',(key,)).fetchone()
                    links=json.loads(row[0]) if row else dict(version=VERSION,record_ids=[],proposal_ids=[])
                    for field,source in [('record_ids','record_id'),('proposal_ids','proposal_id')]:
                        if outcome.get(source):links[field]=list(dict.fromkeys(links[field]+[outcome[source]]))[-128:]
                    self.c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',(key,json.dumps(links)))
            except ValueError:
                if isinstance(item, dict) and item.get('_structured'): raise
                # Older model formats retain independently verified points as timeline fallback.
                outcomes.append(dict(operation='invalid'))
        return outcomes

    def resolve(self, pid, action):
        from storage import now
        if action not in ('confirmed', 'rejected', 'automatic'): raise ValueError('操作无效')
        row = self.c.execute('SELECT * FROM proposals WHERE id=?', (pid,)).fetchone()
        if not row or row['status'] != 'pending': raise ValueError('候选已处理或不存在')
        if action == 'automatic' and row['review_level'] == 'core': raise ValueError('核心信息必须由你审核')
        planrow = self.c.execute('SELECT value FROM metadata WHERE key=?', ('dossier_plan:' + str(pid),)).fetchone()
        plan = json.loads(planrow[0]) if planrow else dict(version=VERSION, operation='update', category='提取的关键信息', event_date='')
        rid = None
        if action != 'rejected':
            ids = json.loads(row['source_ids']); marks = ','.join('?' for _ in ids)
            sources = list(self.c.execute("SELECT r.* FROM records r JOIN messages m ON m.id=r.source_message_id WHERE m.id IN (" + marks + ") AND m.share_with_ai=1 AND m.role='user' AND r.share_with_ai=1 AND r.sensitivity='normal' AND r.archived=0", ids))
            if not ids or len(sources) != len(ids): raise ValueError('来源已限制分享，不能保存')
            oldrow = self.c.execute('SELECT * FROM records WHERE field_key=? AND archived=0', (row['field_key'],)).fetchone() if row['field_key'] else None
            old = decode_row('records', oldrow) if oldrow else None
            if old and (not old['share_with_ai'] or old['sensitivity'] != 'normal'): raise ValueError('目标档案仅本地，请手动修改')
            if planrow and (old['id'] if old else None) != plan.get('target_id'): raise ValueError('目标档案已变化，请重新审核')
            if old and planrow and (action == 'automatic' or plan['operation'] == 'merge') and fingerprint(old['content']) != plan['expected_hash']:
                raise ValueError('目标档案已变化，不能覆盖')
            content = validate_field(self.c, row['field_key'], row['content']) if row['field_key'] and not row['field_key'].startswith(('event.', 'idea.')) else row['content']
            event_date = plan['event_date'] or max(s['event_date'] or s['created_at'][:10] for s in sources)
            if old and old['event_date'] and event_date < old['event_date']: raise ValueError('过去的信息不能覆盖当前档案')
            if old and canonical(content) == canonical(old['content']): rid = old['id']
            else:
                rid = self.store.save_record(dict(kind=row['kind'], category=plan['category'], title=row['title'], content=content,
                    source='记录 #' + ','.join(map(str, ids)) + ' · ' + ('自动更新档案' if action == 'automatic' else '本人审核核心信息'),
                    event_date=event_date, status='confirmed', sensitivity='normal', share_with_ai=True, field_key=row['field_key'], content_state='compact'), old['id'] if old else None, self.c)
                if old and row['field_key'] in TIMELINE_FIELDS:
                    summary = row['title'] + '：' + old['content'] + ' → ' + content
                    event_key = 'event.' + fingerprint(row['field_key'] + '|' + event_date + '|' + canonical(summary))
                    if not self.c.execute('SELECT 1 FROM records WHERE field_key=? AND archived=0', (event_key,)).fetchone():
                        event_id=self.store.save_record(dict(kind='journal', category='重要变化', title=row['title'] + '变化', content=summary,
                            source='本人审核后的变化 · 档案 #' + str(rid), event_date=event_date, status='confirmed', sensitivity='normal',
                            share_with_ai=True, field_key=event_key, content_state='compact'), c=self.c)
                        previous=self.c.execute("SELECT source_ids FROM proposals WHERE record_id=? AND content=? AND status IN ('confirmed','automatic') ORDER BY id DESC LIMIT 1",(old['id'],old['content'])).fetchone()
                        history_ids=list(dict.fromkeys(ids+(json.loads(previous[0]) if previous else [])+([old['source_message_id']] if old['source_message_id'] else [])))
                        origin=dict(version=VERSION,parent_record=rid,source_ids=history_ids,content_hash=fingerprint(summary))
                        self.c.execute('INSERT INTO metadata VALUES (?,?)',('dossier_origin:'+str(event_id),json.dumps(origin)))
        agenda_plan=self.c.execute('SELECT value FROM metadata WHERE key=?',('agenda_plan:'+str(pid),)).fetchone()
        if agenda_plan:
            if rid:self.c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('agenda:'+str(rid),agenda_plan[0]))
            self.c.execute('DELETE FROM metadata WHERE key=?',('agenda_plan:'+str(pid),))
        self.c.execute('UPDATE proposals SET status=?,record_id=? WHERE id=?', (action, rid, pid))
        self.c.execute('DELETE FROM metadata WHERE key=?', ('dossier_plan:' + str(pid),))
        return rid
