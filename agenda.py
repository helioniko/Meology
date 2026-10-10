"""Compact agenda protocol in existing records/metadata, with explicit-source extraction."""
import json,re
from datetime import datetime,date,timedelta
from data_format import DataFormatError,decode_row
from dossier import canonical,fingerprint

VERSION=1
STATES={'pending':'待办','done':'已完成','cancelled':'已取消'}
KEYS={'version','due_at','precision','status'}
MARK='\n日程：'

def validate(info):
 if not isinstance(info,dict) or set(info)!=KEYS or type(info.get('version')) is not int or info['version']!=VERSION:raise ValueError('日程协议版本或字段无效')
 if not isinstance(info['status'],str) or info['status'] not in STATES or not isinstance(info['precision'],str) or info['precision'] not in ('none','date','time') or not isinstance(info['due_at'],str):raise ValueError('日程时间或状态无效')
 due=info['due_at']
 try:
  if info['precision']=='none':assert due==''
  elif info['precision']=='date':assert re.fullmatch(r'\d{4}-\d{2}-\d{2}',due);date.fromisoformat(due)
  else:assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}',due);datetime.fromisoformat(due)
 except (ValueError,AssertionError):raise ValueError('日程日期或时间无效') from None
 return info

def body(text):return text.rsplit(MARK,1)[0]
def content(text,info):
 validate(info);return body(text)+MARK+(info['due_at'].replace('T',' ') or '未指定日期')+' · '+STATES[info['status']]

def check_metadata(c):
 for row in c.execute("SELECT key,value FROM metadata WHERE key LIKE 'agenda:%' OR key LIKE 'agenda_plan:%'"):
  try:
   prefix,number=row[0].split(':');rid=int(number);assert rid>0;info=validate(json.loads(row[1]))
   table='records' if prefix=='agenda' else 'proposals';target=c.execute('SELECT * FROM '+table+' WHERE id=?',(rid,)).fetchone();target=decode_row(table,target) if target else None
   assert target and re.fullmatch(r'task\.[0-9a-f]{64}',target['field_key'] or '') and target['content']==content(target['content'],info)
  except (ValueError,TypeError,AssertionError):raise DataFormatError('日程数据或来源格式无效，请使用相应版本') from None
 for row in c.execute("SELECT id FROM records WHERE field_key LIKE 'task.%'"):
  if not c.execute('SELECT 1 FROM metadata WHERE key=?',('agenda:'+str(row[0]),)).fetchone():raise DataFormatError('日程缺少时间与状态元数据')
 for row in c.execute("SELECT id FROM proposals WHERE field_key LIKE 'task.%' AND status='pending'"):
  if not c.execute('SELECT 1 FROM metadata WHERE key=?',('agenda_plan:'+str(row[0]),)).fetchone():raise DataFormatError('日程候选缺少有效计划')

 for raw in c.execute("SELECT v.* FROM revisions v JOIN records r ON r.id=v.record_id WHERE r.field_key LIKE 'task.%'"):
  try:
   snapshot=json.loads(decode_row('revisions',raw)['snapshot'])
   if 'agenda' in snapshot:
    info=validate(snapshot['agenda']);assert snapshot['content']==content(snapshot['content'],info)
  except (ValueError,TypeError,AssertionError):raise DataFormatError('日程历史协议无效，请使用相应版本') from None

def get(c,rid):
 row=c.execute('SELECT value FROM metadata WHERE key=?',('agenda:'+str(rid),)).fetchone()
 return validate(json.loads(row[0])) if row else None

def rows(store,status='pending',limit=100,offset=0):
 if status not in (*STATES,'all') or type(limit) is not int or not 1<=limit<=100 or type(offset) is not int or offset<0:raise ValueError('日程查询参数无效')
 where="m.key>='agenda:' AND m.key<'agenda;' AND r.archived=0 AND r.status='confirmed'";params=[]
 if status!='all':where+=" AND json_extract(m.value,'$.status')=?";params.append(status)
 with store.connection() as c:
  result=[]
  for raw in c.execute("SELECT r.*,m.value AS agenda_info FROM metadata m JOIN records r ON r.id=CAST(substr(m.key,8) AS INTEGER) WHERE "+where+" ORDER BY CASE WHEN json_extract(m.value,'$.due_at')='' THEN 1 ELSE 0 END,json_extract(m.value,'$.due_at'),r.id LIMIT ? OFFSET ?",params+[limit,offset]):
   row=decode_row('records',raw);info=validate(json.loads(row.pop('agenda_info')));row['record_status']=row['status'];row.update(info);row['description']=body(row['content']);result.append(row)
  return result

def slot(item,old,c):
 if not isinstance(item['agenda'],dict):raise ValueError('日程格式无效')
 info=validate({'version':VERSION,**item['agenda']})
 if type(item.get('inferred',False)) is not bool or item.get('inferred',False):raise ValueError('推测的安排不能自动加入日程，请明确记录')
 if (item.get('operation') in ('update','merge') or info['status']!='pending') and type(item.get('target_id')) is not int:raise ValueError('改期、完成或取消必须指定已有日程编号')
 if old and not (old['field_key'] or '').startswith('task.'):raise ValueError('不能把已有个人档案覆盖为日程')
 subject=str(item.get('subject') or '本人').strip()[:80];title=str(item.get('title') or '').strip()[:80]
 if not title or not canonical(title):raise ValueError('日程缺少事项名称')
 text=body(str(item.get('content') or '').strip())
 if not text or len(text)>380:raise ValueError('日程内容为空或过长')
 if not old:
  matching=c.execute("SELECT r.* FROM metadata m JOIN records r ON r.id=CAST(substr(m.key,8) AS INTEGER) WHERE m.key>='agenda:' AND m.key<'agenda;' AND r.archived=0 AND r.title=? AND json_extract(m.value,'$.due_at')=? LIMIT 1",(title if subject=='本人' else subject+' · '+title,info['due_at'])).fetchone()
  if matching:old=decode_row('records',matching)
 key=old['field_key'] if old else 'task.'+fingerprint(canonical(subject)+'|'+canonical(title)+'|'+info['due_at'])
 if not old and info['status']!='pending':raise ValueError('完成或取消需要已有日程编号')
 return dict(key=key,title=title,subject=subject,kind='project',category='日程'),content(text,info),info

def set_status(store,rid,status):
 if type(rid) is not int or not isinstance(status,str) or status not in STATES:raise ValueError('日程操作无效')
 with store.connection() as c:
  c.execute('BEGIN IMMEDIATE');raw=c.execute('SELECT * FROM records WHERE id=? AND archived=0',(rid,)).fetchone();info=get(c,rid)
  if not raw or not info:raise ValueError('日程不存在或已归档')
  if info['status']==status:return dict(ok=True)
  info={**info,'status':status};row=decode_row('records',raw)
  store.save_record({**row,'content':content(row['content'],info),'source':'本人更新日程状态'},rid,c)
  c.execute('UPDATE metadata SET value=? WHERE key=?',(json.dumps(info), 'agenda:'+str(rid)))
 return dict(ok=True)

def edit(store,rid,data):
 if type(rid) is not int or not isinstance(data,dict) or set(data)!={'title','description','due_at','precision'}:raise ValueError('日程编辑字段无效')
 if any(not isinstance(data[k],str) for k in data) or not data['title'].strip() or len(data['title'])>80 or not data['description'].strip() or len(data['description'])>380 or MARK in data['description']:raise ValueError('日程事项或内容无效')
 with store.connection() as c:
  c.execute('BEGIN IMMEDIATE');raw=c.execute('SELECT * FROM records WHERE id=? AND archived=0',(rid,)).fetchone();old=get(c,rid)
  if not raw or not old:raise ValueError('日程不存在或已归档')
  info=validate({**old,'due_at':data['due_at'],'precision':data['precision']});row=decode_row('records',raw)
  store.save_record({**row,'title':data['title'].strip(),'content':content(data['description'].strip(),info),'source':'本人编辑日程'},rid,c)
  c.execute('UPDATE metadata SET value=? WHERE key=?',(json.dumps(info),'agenda:'+str(rid)))
 return dict(ok=True)

NUM={'零':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
def number(text):
 if text.isdecimal():return int(text)
 if '十' in text:
  left,right=text.split('十',1);return NUM.get(left,1)*10+NUM.get(right,0)
 return NUM.get(text,-1)

def time_constraints(text,recorded_at):
 """Validate an AI-selected schedule's time evidence; never detect/create tasks."""
 from storage import TZ
 clock=datetime.fromisoformat(recorded_at)
 clock=clock.replace(tzinfo=TZ) if clock.tzinfo is None else clock.astimezone(TZ)
 base=clock.date();day=None;relative_clock=None
 full=list(re.finditer(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?',text))
 short=[] if full else list(re.finditer(r'(\d{1,2})月(\d{1,2})[日号]',text))
 relative=list(re.finditer(r'大后天|后天|明天|今天|今晚',text))
 weeks=list(re.finditer(r'(下|本|这|上)?(?:周|星期)([一二三四五六日天])',text))
 if len(full)+len(short)+len(relative)+len(weeks)==1:
  try:
   if full:day=date(*map(int,full[0].groups()))
   elif short:
    day=date(base.year,*map(int,short[0].groups()))
    if day<base:day=date(base.year+1,day.month,day.day)
   elif relative:day=base+timedelta(days={'今天':0,'今晚':0,'明天':1,'后天':2,'大后天':3}[relative[0][0]])
   else:
    week=weeks[0];offset=7 if week[1]=='下' else -7 if week[1]=='上' else 0
    day=base-timedelta(days=base.weekday())+timedelta(days='一二三四五六日'.index(week[2].replace('天','日'))+offset)
    if not week[1] and day<base:day+=timedelta(days=7)
  except ValueError:raise ValueError('日程引用中的日期无效，输入保留') from None
 duration=re.search(r'([零一二三四五六七八九十两\d]{1,3}|半)(?:个)?(分钟|小时|天)(?:之后|以后|后)',text)
 if duration and not (full or short or relative or weeks):
  amount=.5 if duration[1]=='半' else number(duration[1]);unit={'分钟':60,'小时':3600,'天':86400}[duration[2]]
  later=clock+timedelta(seconds=amount*unit);day=later.date()
  if duration[2]!='天':relative_clock=later.strftime('%H:%M')
 tm=re.search(r'(上午|下午|晚上|早上|中午|凌晨)?\s*([零一二三四五六七八九十两\d]{1,3})[点时](?:([零一二三四五六七八九十两\d]{1,3})分?|(半)|(一刻)|(三刻))?',text)
 colon=False
 if not tm:tm=re.search(r'(?:(上午|下午|晚上|早上|中午|凌晨)\s*)?(\d{1,2}):(\d{2})',text);colon=bool(tm)
 exact_time=relative_clock;ambiguous=False
 if tm:
  hour=number(tm[2]);minute=number(tm[3]) if tm[3] else 30 if not colon and tm[4] else 15 if not colon and tm[5] else 45 if not colon and tm[6] else 0
  if tm[1] in ('下午','晚上','中午') and hour<12:hour+=12
  if tm[1]=='凌晨' and hour==12:hour=0
  midnight=(tm[1]=='晚上' and hour in (0,12)) or hour==24
  if midnight:
   hour=0
   if day:day+=timedelta(days=1)
  if not 0<=hour<=23 or not 0<=minute<=59:raise ValueError('日程引用中的时间无效，输入保留')
  ambiguous=not colon and not tm[1] and 1<=hour<=12
  if not ambiguous:exact_time=f'{hour:02}:{minute:02}'
 return day.isoformat() if day else None,exact_time,ambiguous


def validate_source_time(item,originals,old,c):
 """Guard common relative-date/clock mistakes after AI extraction, for both modes."""
 info=validate({'version':VERSION,**item['agenda']});quote=item['quote']
 sources=[originals[mid] for mid in item['source_ids'] if quote in originals[mid]['content']]
 old_info=get(c,old['id']) if old else None
 constraints=[time_constraints(quote,source['recorded_at']) for source in sources]
 known_days={day for day,_,_ in constraints if day}
 clocks={clock for _,clock,_ in constraints if clock}
 if known_days and info['due_at'][:10] not in known_days:raise ValueError('日程日期与记录时的时间依据不符，输入保留')
 if known_days and clocks and info['precision']!='time':raise ValueError('日程遗漏明确的具体时间，输入保留')
 if info['due_at'] and not known_days and not re.search(r'\d.*(?:年|月|日|号|/|-)|今天|明天|后天|今晚|周|星期|节|分钟.*后|小时.*后|天.*后|today|tomorrow|next|monday|tuesday|wednesday|thursday|friday|saturday|sunday',quote,re.I):
  if not old_info or info['due_at'][:10]!=old_info['due_at'][:10]:raise ValueError('日程没有日期依据，不能补日期或改日期，输入保留')
 if info['precision']=='time':
  inherited=old_info and old_info['precision']=='time' and info['due_at'][11:]==old_info['due_at'][11:]
  if clocks and info['due_at'][11:] not in clocks:raise ValueError('日程具体时间与输入不符，输入保留')
  if not clocks and not inherited:raise ValueError('日程缺少明确具体时间，不能猜测，输入保留')
