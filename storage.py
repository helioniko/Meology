"""Local personal memory store. Key information outlives temporary chat input."""
from __future__ import annotations
import hashlib, json, re, sqlite3, uuid, threading, gzip, shutil
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from data_format import initialize_database, backup_database, copy_database, export_document, DataFormatError, decode_row

from app_runtime import RESOURCE_ROOT as ROOT, DB_PATH as DB
TZ = timezone(timedelta(hours=8))
def now(): return datetime.now(TZ).isoformat(timespec='seconds')
def today(): return datetime.now(TZ).date().isoformat()
KINDS = {'profile':'核心档案','state':'当前状态','journal':'日常记录','project':'项目与目标','decision':'决定与经验','resource':'资料来源','memory':'长期记忆'}
from profile_schema import FIELDS, FIELD_MAP, GROUPS, GROUP_MAP, PROFILE_SCHEMA_VERSION, QUESTIONNAIRE_VERSION, validate_answer, check_profile_metadata
DEFAULTS = dict(language='zh-CN',tutorial_seen=False,onboarding_complete=False,active_provider='',daily_call_limit=50,context_chars=12000,organize_delay=90,organize_interval=3600,organize_tokens=4000,auto_update_profile=False,autostart=False,pinned=False,desktop_embedded=False,retrieval_chars=1800,auto_backup_mb=256,cache_mb=32,compress_after_days=180,semantic_enabled=False,embedding_provider='',embedding_model='',http_access=False)

from appearance import DEFAULTS as APPEARANCE_DEFAULTS
DEFAULTS.update(APPEARANCE_DEFAULTS)
from web_ai import DEFAULTS as WEB_DEFAULTS
DEFAULTS.update(WEB_DEFAULTS)

def signature(value): return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

class Store:
 def __init__(self,path=DB):
  self.listeners=[]; self.path=Path(path); self.lock=threading.RLock(); self.path.parent.mkdir(parents=True,exist_ok=True); self.initialize()
 def subscribe(self,callback):
  self.listeners.append(callback)
  return lambda:self.listeners.remove(callback) if callback in self.listeners else None
 @contextmanager
 def connection(self):
  with self.lock:
   c=sqlite3.connect(self.path,timeout=15); c.row_factory=sqlite3.Row
   c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA secure_delete=ON'); c.execute('PRAGMA busy_timeout=15000'); c.execute('PRAGMA cache_size=-2048'); c.execute('PRAGMA temp_store=FILE')
   changed=False
   try:
    with c: yield c
    changed=c.total_changes>0
   finally: c.close()
  if changed:
   for callback in list(self.listeners):
    try: callback()
    except Exception: pass
 def initialize(self):
  with self.lock:
   initialize_database(self.path)
   with self.connection() as c:
    check_profile_metadata(c)
    row=c.execute("SELECT value FROM metadata WHERE key='profile_schema_version'").fetchone()
    previous=int(row[0]) if row else None
   if previous is not None and previous<PROFILE_SCHEMA_VERSION:
    backup_database(self.path,prefix='migration-profile-v'+str(previous)+'-personal')
   with self.connection() as c:
    c.execute('BEGIN IMMEDIATE')
    c.execute("INSERT OR REPLACE INTO metadata VALUES ('profile_schema_version',?)",(str(PROFILE_SCHEMA_VERSION),))
 def settings(self):
  with self.connection() as c: rows=c.execute("SELECT value FROM metadata WHERE key='settings'").fetchone()
  return {**DEFAULTS,**(json.loads(rows[0]) if rows else {}),'auto_update_profile':False}
 def update_settings(self,values):
  current=self.settings()
  for k,v in values.items():
   if k not in DEFAULTS or k=='auto_update_profile': continue
   if isinstance(DEFAULTS[k],bool):
    if type(v) is not bool: raise ValueError('设置值无效')
   if isinstance(DEFAULTS[k],str) and (not isinstance(v,str) or len(v)>200): raise ValueError('设置文本无效')
   current[k]=v
  for key,low,high in [('daily_call_limit',1,500),('context_chars',2000,24000),('organize_delay',15,1800),('organize_interval',600,86400),('organize_tokens',2000,8000),('retrieval_chars',600,6000),('auto_backup_mb',16,4096),('cache_mb',4,512),('compress_after_days',30,3650)]:
   if type(current[key]) is not int or not low<=current[key]<=high: raise ValueError('设置超出允许范围')
  if current['organize_interval'] not in (600,1800,3600,43200,86400):raise ValueError('请选择有效的整理周期')
  if current['organize_tokens'] not in (2000,4000,8000):raise ValueError('请选择有效的输出 token 上限')
  if current['language'] not in ('zh-CN','en'):raise ValueError('请选择中文或 English')
  from appearance import validate
  validate(current)
  from web_ai import validate as validate_web
  validate_web(current)
  with self.connection() as c: c.execute("INSERT OR REPLACE INTO metadata VALUES ('settings',?)",(json.dumps(current),))
  return current
 def records(self,q='',kind='',archived=False,limit=None,offset=0,ids=None,view=''):
  if limit is not None and (type(limit) is not int or not 1<=limit<=200):raise ValueError('记录页大小无效')
  if type(offset) is not int or offset<0:raise ValueError('记录页起点无效')
  if ids is not None and (not isinstance(ids,list) or len(ids)>100 or any(type(i) is not int for i in ids)):raise ValueError('记录来源编号无效')
  result=[];matched=0
  with self.connection() as c:
   where="archived=?";values=[int(archived)]
   if ids is None:where+=" AND NOT (kind='resource' AND content='' AND compressed_text IS NULL AND content_state='compact' AND source_message_id IS NOT NULL)"
   elif not ids:return []
   else:where+=' AND id IN ('+','.join('?' for _ in ids)+')';values.extend(ids)
   if kind:where+=' AND kind=?';values.append(kind)
   if view=='memory':where+=" AND kind!='journal' AND (kind!='profile' OR field_key IS NULL)"
   # Stream cold/decompressed search rows; never materialize the entire database for a page.
   for raw in c.execute('SELECT * FROM records WHERE '+where+' ORDER BY updated_at DESC,id DESC',values):
    row=decode_row('records',raw)
    if q and q.casefold() not in (row['title']+' '+row['content']+' '+row['tags']+' '+row['source']).casefold():continue
    matched+=1
    if matched<=offset:continue
    result.append(row)
    if limit is not None and len(result)>=limit:break
  return result
 def save_record(self,data,rid=None,c=None):
  if data.get('kind') not in KINDS: raise ValueError('记录类型无效')
  if data.get('status') not in ['confirmed','inferred','unconfirmed']: raise ValueError('确认状态无效')
  if data.get('sensitivity') not in ['normal','sensitive']: raise ValueError('隐私级别无效')
  if not all(str(data.get(k,'')).strip() for k in ('title','content','source')): raise ValueError('标题、内容、来源不能为空')
  if data.get('event_date'): date.fromisoformat(data['event_date'])
  if len(str(data['content']))>20000: raise ValueError('单条记录不能超过 20000 字')
  if not data.get('tags'):
   from retrieval import infer_tags
   data={**data,'tags':','.join(infer_tags(data))}
  keys=['kind','category','title','content','source','event_date','tags','status','sensitivity','share_with_ai','field_key','source_message_id','content_state']
  vals=[data.get(k,'') for k in keys]; vals[9]=int(bool(data.get('share_with_ai'))); vals[10]=data.get('field_key') or None; vals[11]=data.get('source_message_id') or None;vals[12]=data.get('content_state','entered')
  def write(conn):
   if rid:
    old=conn.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()
    if not old: raise ValueError('记录不存在')
    snapshot=decode_row('records',old)
    if (snapshot.get('field_key') or '').startswith('task.'):
     from agenda import get as get_agenda,content as agenda_content
     info=get_agenda(conn,rid)
     if info:snapshot['agenda']=info
     if c is None and (data.get('field_key')!=snapshot['field_key'] or data['content']!=agenda_content(data['content'],info)):raise ValueError('请在日程页编辑事项，保持日期和状态一致')
    conn.execute('INSERT INTO revisions(record_id,snapshot,changed_at) VALUES (?,?,?)',(rid,json.dumps(snapshot,ensure_ascii=False),now()))
    conn.execute('UPDATE records SET '+','.join(k+'=?' for k in keys)+',compressed_text=NULL,updated_at=? WHERE id=?',vals+[now(),rid])
    if old['source_message_id'] and old['content_state']=='pending':
     conn.execute("UPDATE messages SET content=?,compressed_text=NULL,share_with_ai=?,organized=0,organize_offset=0,compact_content='',retention_state='pending' WHERE id=?",(data['content'],int(data.get('share_with_ai',False) and data.get('sensitivity')=='normal'),old['source_message_id']))
    return rid
   # A deleted highest ID must never be assigned to a different personal fact.
   watermark=conn.execute("SELECT value FROM metadata WHERE key='record_id_highwater'").fetchone()
   if watermark:
    rid_next=max(int(watermark[0]),conn.execute('SELECT coalesce(max(id),0) FROM records').fetchone()[0])+1
    return conn.execute('INSERT INTO records(id,'+','.join(keys)+',created_at,updated_at) VALUES ('+','.join('?' for _ in range(16))+')',[rid_next]+vals+[now(),now()]).lastrowid
   return conn.execute('INSERT INTO records('+','.join(keys)+',created_at,updated_at) VALUES ('+','.join('?' for _ in range(15))+')',vals+[now(),now()]).lastrowid
  if c is not None: return write(c)
  with self.connection() as conn: return write(conn)
 def change_archive(self,rid,archived):
  with self.connection() as c:
   row=c.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()
   if not row: raise ValueError('记录不存在')
   snapshot=decode_row('records',row)
   if (snapshot.get('field_key') or '').startswith('task.'):
    from agenda import get as get_agenda
    snapshot['agenda']=get_agenda(c,rid)
   c.execute('INSERT INTO revisions(record_id,snapshot,changed_at) VALUES (?,?,?)',(rid,json.dumps(snapshot,ensure_ascii=False),now()))
   c.execute('UPDATE records SET archived=?,updated_at=? WHERE id=?',(int(archived),now(),rid))
 def delete_journal(self,rid):
  from record_deletion import delete_journal
  return delete_journal(self,rid)
 def delete_summary(self,sid):
  from record_deletion import delete_summary
  return delete_summary(self,sid)
 def history(self,rid):
  with self.connection() as c: return [decode_row('revisions',r) for r in c.execute('SELECT * FROM revisions WHERE record_id=? ORDER BY id DESC',(rid,))]
 def restore_revision(self,revision_id):
  with self.connection() as c:
   row=c.execute('SELECT * FROM revisions WHERE id=?',(revision_id,)).fetchone()
   if not row: raise ValueError('历史版本不存在')
   data=json.loads(decode_row('revisions',row)['snapshot'])
   if data.get('agenda'):
    from agenda import validate as validate_agenda
    validate_agenda(data['agenda'])
   self.save_record(data,row['record_id'],c)
   if data.get('agenda'):c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('agenda:'+str(row['record_id']),json.dumps(data['agenda'])))
   c.execute('UPDATE records SET archived=? WHERE id=?',(data['archived'],row['record_id']))
 def profile(self):
  with self.connection() as c:
   rows=c.execute("SELECT * FROM records WHERE archived=0 AND field_key IS NOT NULL AND field_key NOT LIKE 'event.%' AND field_key NOT LIKE 'idea.%'")
   return {r['field_key']:decode_row('records',r) for r in rows}
 def profile_fields(self):
  from dossier import fields_for
  return fields_for(self)
 def save_profile(self,fields,complete=False,c=None,skip_empty=False):
  if not isinstance(fields,dict): raise ValueError('档案格式无效')
  from dossier import validate_field
  specs={f[0]:f for f in self.profile_fields()}
  validated={}
  for key,entry in fields.items():
   if key not in specs or not isinstance(entry,dict): raise ValueError('档案字段无效')
   if type(entry.get('share_with_ai',False)) is not bool: raise ValueError('档案分享设置无效')
   with self.connection() as validation_conn: value=validate_field(validation_conn,key,entry.get('value',''))
   validated[key]=(value,entry.get('share_with_ai',False))
  def write(conn):
   existing={r['field_key']:decode_row('records',r) for r in conn.execute("SELECT * FROM records WHERE archived=0 AND field_key IS NOT NULL")}
   for key,(value,share) in validated.items():
    old=existing.get(key)
    if not value:
     if old and not skip_empty:
      conn.execute('INSERT INTO revisions(record_id,snapshot,changed_at) VALUES (?,?,?)',(old['id'],json.dumps(old,ensure_ascii=False),now()))
      conn.execute('UPDATE records SET archived=1,updated_at=? WHERE id=?',(now(),old['id']))
     continue
    if old and old['content']==value and bool(old['share_with_ai'])==share: continue
    self.save_record(dict(kind=old['kind'] if old else 'profile',category=specs[key][2],title=specs[key][1],content=value,source='本人填写个人档案',event_date=today(),content_state='entered',status='confirmed',sensitivity='normal',share_with_ai=share,field_key=key),old['id'] if old else None,c=conn)
   if complete:
    row=conn.execute("SELECT value FROM metadata WHERE key='settings'").fetchone()
    settings={**DEFAULTS,**(json.loads(row[0]) if row else {}),'onboarding_complete':True}
    conn.execute("INSERT OR REPLACE INTO metadata VALUES ('settings',?)",(json.dumps(settings),))
  if c is not None: write(c)
  else:
   with self.connection() as conn: write(conn)
 def onboarding(self):
  with self.connection() as c: row=c.execute("SELECT value FROM metadata WHERE key='onboarding'").fetchone()
  progress=json.loads(row[0]) if row else dict(version=QUESTIONNAIRE_VERSION,selected=['basic'],current_group='',in_progress=False)
  if progress.get('version')!=QUESTIONNAIRE_VERSION: raise DataFormatError('建档进度来自未支持的版本，请升级软件')
  return dict(profile_schema_version=PROFILE_SCHEMA_VERSION,questionnaire_version=QUESTIONNAIRE_VERSION,groups=GROUPS,learned_keys=['values','preferences','boundaries','goals','constraints','thinking_patterns','emotional_patterns'],progress=progress)
 def save_onboarding(self,data):
  if not isinstance(data,dict): raise ValueError('建档请求无效')
  version=data.get('questionnaire_version',QUESTIONNAIRE_VERSION)
  if type(version) is not int or version!=QUESTIONNAIRE_VERSION: raise ValueError('建档页面版本已变化，请刷新页面')
  if set(data)-{'selected','current_group','finish','fields','questionnaire_version'}: raise ValueError('建档请求含未支持的字段')
  selected=data.get('selected'); current=data.get('current_group',''); finish=data.get('finish',False); fields=data.get('fields',{})
  if not isinstance(selected,list) or any(not isinstance(g,str) or g not in GROUP_MAP for g in selected) or len(set(selected))!=len(selected): raise ValueError('请选择有效的填写方向')
  if not isinstance(current,str) or (current and current not in selected) or type(finish) is not bool: raise ValueError('建档进度无效')
  if not selected and not finish: raise ValueError('至少选择一个方向，也可以暂时结束')
  allowed={q['key'] for g in selected for q in GROUP_MAP[g]['questions']}
  if not isinstance(fields,dict) or any(key not in allowed for key in fields): raise ValueError('答案必须属于所选方向')
  for key,entry in fields.items():
   if not isinstance(entry,dict): raise ValueError('答案格式无效')
   validate_answer(key,entry.get('value',''),strict_choice=True)
  progress=dict(version=QUESTIONNAIRE_VERSION,selected=selected,current_group='' if finish else current,in_progress=not finish)
  with self.connection() as c:
   c.execute('BEGIN IMMEDIATE')
   self.save_profile(fields,complete=finish,c=c,skip_empty=True)
   c.execute("INSERT OR REPLACE INTO metadata VALUES ('onboarding',?)",(json.dumps(progress,ensure_ascii=False),))
  return self.onboarding()
 def new_session(self,title='新的记录'):
  sid=uuid.uuid4().hex
  with self.connection() as c: c.execute('INSERT INTO sessions VALUES (?,?,?)',(sid,title,now()))
  return sid
 def sessions(self):
  with self.connection() as c: return [dict(r) for r in c.execute('SELECT * FROM sessions ORDER BY created_at DESC LIMIT 100')]
 def message_view(self,c,raw):
  row=decode_row('messages',raw)
  if row.get('retention_state')=='compact' and row['role']=='user':
   source=c.execute('SELECT * FROM records WHERE source_message_id=?',(row['id'],)).fetchone()
   if source and decode_row('records',source)['content']:
    row['content']=decode_row('records',source)['content']
   else:
    refs=c.execute('SELECT value FROM metadata WHERE key=?',('dossier_links:'+str(row['id']),)).fetchone()
    links=json.loads(refs[0]) if refs else None
    if links:
     pids=links['proposal_ids'];changes=c.execute("SELECT title,status,record_id FROM proposals WHERE id IN ("+','.join('?' for _ in pids)+") AND status!='rejected' ORDER BY id",pids).fetchall() if pids else []
    else:changes=c.execute("SELECT p.title,p.status,p.record_id FROM proposals p,json_each(p.source_ids) j WHERE j.value=? AND p.status!='rejected' ORDER BY p.id",(row['id'],)).fetchall()
    saved=[]
    if links:
     for rid in links['record_ids']:
      record=c.execute('SELECT * FROM records WHERE id=? AND archived=0',(rid,)).fetchone()
      if record:saved.append(record['title']+'：'+decode_row('records',record)['content'][:200])
    for p in changes:
     if p['status']=='pending': saved.append('待核心审核：'+p['title'])
     elif p['record_id']:
      record=c.execute('SELECT * FROM records WHERE id=? AND archived=0',(p['record_id'],)).fetchone()
      if record: saved.append(p['title']+'：'+decode_row('records',record)['content'][:200])
    row['content']='已整理到档案：\n'+'\n'.join(dict.fromkeys(saved)) if saved else '没有新增档案信息；重复内容或闲聊已忽略。'
  return row
 def messages(self,sid=None,limit=64,before=None,ids=None):
  if type(limit) is not int or not 1<=limit<=100: raise ValueError('消息页大小无效')
  with self.connection() as c:
   where="retention_state!='discarded'"; values=[]
   if sid: where+=' AND session_id=?'; values.append(sid)
   if before: where+=' AND id<?';values.append(int(before))
   if ids:
    if len(ids)>100:raise ValueError('一次最多查询100项来源')
    where+=' AND id IN ('+','.join('?' for _ in ids)+')';values.extend(ids)
   rows=c.execute('SELECT * FROM messages WHERE '+where+' ORDER BY id DESC LIMIT ?',values+[limit]).fetchall()
   return [self.message_view(c,r) for r in reversed(rows)]
 def send(self,sid,text,share,request_id):
  if not text.strip() or len(text)>20000: raise ValueError('记录为空或超过 20000 字')
  if not request_id or len(request_id)>100: raise ValueError('请求标识无效')
  with self.connection() as c:
   old=c.execute('SELECT id FROM messages WHERE request_id=?',(request_id,)).fetchone()
   if old: return old['id']
   if not c.execute('SELECT 1 FROM sessions WHERE id=?',(sid,)).fetchone(): raise ValueError('对话不存在')
   mid=c.execute('INSERT INTO messages(session_id,role,content,created_at,share_with_ai,organized,request_id) VALUES (?,?,?,?,?,?,?)',(sid,'user',text.strip(),now(),int(share),int(not share),request_id)).lastrowid
   self.save_record(dict(kind='journal',category='日常',title=text.strip()[:40],content=text.strip(),source='本人记录 · 消息 #'+str(mid),event_date=today(),content_state='pending' if share else 'entered',status='confirmed',sensitivity='normal' if share else 'sensitive',share_with_ai=share,source_message_id=mid),c=c)
   c.execute('UPDATE sessions SET title=? WHERE id=? AND title=?',(text.strip()[:24],sid,'新的记录'))
   if not share:
    c.execute("UPDATE messages SET content='',retention_state='compact',source_hash=? WHERE id=?",(signature(text.strip()),mid))
   return mid
 def enqueue(self,kind,payload,key,c=None):
  def insert(conn): return conn.execute('INSERT OR IGNORE INTO jobs(dedupe_key,kind,payload,due_at,created_at,updated_at) VALUES (?,?,?,?,?,?)',(key,kind,json.dumps(payload),now(),now(),now())).rowcount
  if c is not None: return insert(c)
  with self.connection() as conn: return insert(conn)
 def job_rows(self):
  with self.connection() as c: return [dict(r) for r in c.execute('SELECT * FROM jobs WHERE status!=? ORDER BY id DESC LIMIT 50',('done',))]
 def claim_job(self):
  with self.connection() as c:
   c.execute('BEGIN IMMEDIATE')
   row=c.execute("SELECT * FROM jobs WHERE status IN ('queued','retry','budget') AND due_at<=? ORDER BY CASE kind WHEN 'chat' THEN 0 WHEN 'organize' THEN 1 ELSE 2 END,id LIMIT 1",(now(),)).fetchone()
   if not row: return None
   c.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?",(now(),row['id']))
   return dict(row)
 def finish_job(self,jid):
  with self.connection() as c: c.execute("UPDATE jobs SET status='done',last_error='',payload=CASE WHEN kind IN ('organize','chat') THEN '{}' ELSE payload END,updated_at=? WHERE id=?",(now(),jid))
 def retry_job(self,jid):
  with self.connection() as c: c.execute("UPDATE jobs SET status='queued',attempts=0,due_at=?,last_error='' WHERE id=? AND status IN ('failed','retry','budget')",(now(),jid))
 def fail_job(self,job,error,budget=False):
  attempts=job['attempts']+(0 if budget else 1)
  delay=(datetime.now(TZ)+timedelta(seconds=30*2**attempts)).isoformat(timespec='seconds')
  if budget: delay=(datetime.now(TZ).replace(hour=0,minute=0,second=0)+timedelta(days=1)).isoformat(timespec='seconds')
  with self.connection() as c: c.execute('UPDATE jobs SET status=?,attempts=?,due_at=?,last_error=?,updated_at=? WHERE id=?',('budget' if budget else ('failed' if attempts>=3 else 'retry'),attempts,delay,str(error)[:300],now(),job['id']))
 def providers(self):
  with self.connection() as c: return [dict(r) for r in c.execute('SELECT * FROM providers ORDER BY rowid')]
 def save_provider(self,data):
  from urllib.parse import urlparse
  pid=data.get('id') or uuid.uuid4().hex
  base=str(data.get('base_url','')).strip().rstrip('/')
  parsed=urlparse(base)
  if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment: raise ValueError('服务地址无效，请填写 API 根地址，例如 https://服务地址/v1')
  if parsed.scheme=='http' and parsed.hostname not in ('127.0.0.1','localhost','::1'): raise ValueError('远程 API 请使用 HTTPS')
  values=[str(data.get(k,'')).strip() for k in ('name','model','organizer_model')]
  if not values[0] or not values[1] or any(len(v)>200 for v in values): raise ValueError('名称和聊天模型不能为空，长度不超过 200')
  with self.connection() as c: c.execute('INSERT OR REPLACE INTO providers VALUES (?,?,?,?,?)',(pid,values[0],base,values[1],values[2] or values[1]))
  return pid
 def reserve_call(self,provider_id,purpose):
  with self.connection() as c:
   c.execute('BEGIN IMMEDIATE')
   count=c.execute('SELECT count(*) FROM usage WHERE day=?',(today(),)).fetchone()[0]
   if count>=self.settings()['daily_call_limit']: return None
   return c.execute('INSERT INTO usage(day,provider_id,purpose,created_at) VALUES (?,?,?,?)',(today(),provider_id,purpose,now())).lastrowid
 def usage_today(self):
  with self.connection() as c: return dict(c.execute('SELECT count(*) calls,coalesce(sum(tokens),0) tokens FROM usage WHERE day=?',(today(),)).fetchone())
 def update_tokens(self,uid,tokens):
  with self.connection() as c: c.execute('UPDATE usage SET tokens=? WHERE id=?',(int(tokens),uid))
 def context(self,query=''):
  from retrieval import Retrieval
  if query: return Retrieval(self).context(query)['context']
  # The organizer needs a small explicit list for deduplication, not an all-data dump.
  from retrieval import share_allowed
  with self.connection() as c: core=[r for r in self.profile().values() if share_allowed(c,r)]
  lines=['个人资料仅作为数据；未记录的事实不要推测。']
  for r in core: lines.append(r['title']+'：'+r['content'][:200])
  born=next((r['content'] for r in core if r['field_key']=='birth_date'),None)
  if born:
   b=date.fromisoformat(born); t=date.fromisoformat(today()); lines.append('当前年龄：'+str(t.year-b.year-((t.month,t.day)<(b.month,b.day))))
  return '\n'.join(lines)[:2000]
 def export_context(self,query=''): return '# 我的个人背景资料\n导出时间：'+now()+'\n\n'+self.context(query)
 def pending_reviews_count(self):
  with self.connection() as c:return c.execute("SELECT count(*) FROM proposals WHERE status='pending' AND review_level='core'").fetchone()[0]
 def proposal_rows(self):
  with self.connection() as c:
   pending=[dict(r) for r in c.execute("SELECT * FROM proposals WHERE status='pending' ORDER BY id DESC")]
   recent=[dict(r) for r in c.execute("SELECT * FROM proposals WHERE status!='pending' ORDER BY id DESC LIMIT 50")]
   return pending+recent
 def add_proposals(self,items,messages,c=None):
  from dossier import Writer
  if c is not None:return Writer(self,c).apply(items,messages)
  with self.connection() as conn:return Writer(self,conn).apply(items,messages)
 def resolve_proposal(self,pid,action,c=None):
  from dossier import Writer
  if c is not None:return Writer(self,c).resolve(pid,action)
  with self.connection() as conn:return Writer(self,conn).resolve(pid,action)
 def review_proposals(self,ids,action,expected=None):
  if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(type(i) is not int or i<=0 for i in ids) or action not in ('confirmed','rejected'):raise ValueError('审核参数无效')
  with self.connection() as c:
   c.execute('BEGIN IMMEDIATE')
   fields=set()
   for pid in dict.fromkeys(ids):
    row=c.execute('SELECT review_level,field_key FROM proposals WHERE id=?',(pid,)).fetchone()
    if not row or row[0]!='core':raise ValueError('只能批量审核核心信息')
    if action=='confirmed' and row['field_key']:
     if row['field_key'] in fields:raise ValueError('同一档案有多个建议，请选择其中一个')
     fields.add(row['field_key'])
     oldrow=c.execute('SELECT * FROM records WHERE field_key=? AND archived=0',(row['field_key'],)).fetchone()
     old=decode_row('records',oldrow) if oldrow else None
     if not isinstance(expected,dict) or expected.get(str(pid))!=(old['content'] if old else ''):raise ValueError('当前档案已变化，请刷新列表后重新审核')
    self.resolve_proposal(pid,action,c)
 def export_all(self):
  with self.connection() as c: return export_document(c,now())
 def backup(self):
  with self.lock: return backup_database(self.path)
 def restore_backup(self,filename):
  folder=(self.path.parent.parent/'backups').resolve(); target=(folder/filename).resolve()
  if target.parent!=folder or not (target.name.endswith('.sqlite3') or target.name.endswith('.sqlite3.gz')) or not target.is_file(): raise ValueError('备份文件无效')
  stage=self.path.parent/('.restore-'+uuid.uuid4().hex+'.sqlite3')
  try:
   if target.name.endswith('.gz'):
    with gzip.open(target,'rb') as src, stage.open('wb') as dst:
     copied=0
     while True:
      chunk=src.read(1024**2)
      if not chunk: break
      copied+=len(chunk)
      if copied>8*1024**3: raise DataFormatError('解压备份超过支持范围，未覆盖现有数据')
      dst.write(chunk)
   else: copy_database(target,stage)
   initialize_database(stage,make_backup=False)
   c=sqlite3.connect(stage)
   try:
    with c:
     check_profile_metadata(c)
     c.execute("UPDATE jobs SET status='queued' WHERE status='running'")
   finally: c.close()
   with self.lock:
    safety=self.backup()
    try: copy_database(stage,self.path)
    except Exception:
     copy_database(safety,self.path)
     raise DataFormatError('恢复未完成，已恢复操作前的数据') from None
  except (sqlite3.Error,gzip.BadGzipFile,EOFError): raise DataFormatError('备份文件无效，未覆盖现有数据') from None
  finally:
   stage.unlink(missing_ok=True)

 def delete_backup(self,filename):
  folder=(self.path.parent.parent/'backups').resolve(); target=(folder/filename).resolve()
  if target.parent!=folder or not target.is_file() or not (target.name.endswith('.sqlite3') or target.name.endswith('.sqlite3.gz')): raise ValueError('备份文件无效')
  with self.lock: target.unlink()

 def storage_stats(self):
  from compact_storage import storage_stats
  return storage_stats(self)
 def maintain_storage(self):
  from compact_storage import maintain
  return maintain(self)
