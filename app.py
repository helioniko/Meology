from pathlib import Path
import argparse, json, secrets, threading, webbrowser, socket, gzip, os, sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from storage import Store,ROOT,DB,FIELDS,FIELD_MAP,KINDS,now,today
from ai import Vault,Provider,APIError
from worker import Worker
from app_runtime import APP_VERSION
TOKEN=secrets.token_urlsafe(32)

def create_server(store,provider,worker,port=8765):
 from web_ai import WebAI
 web_ai=WebAI(store,worker)
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args): pass
  def valid_host(self): return self.headers.get('Host') in ('127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port))
  def respond(self,data,code=200,mime='application/json; charset=utf-8',filename=None):
   content=json.dumps(data,ensure_ascii=False).encode() if mime.startswith('application/json') else (data if isinstance(data,bytes) else data.encode())
   self.send_response(code); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(content))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer')
   self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
   if filename: self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
   self.end_headers(); self.wfile.write(content)
  def do_GET(self):
   if not self.valid_host(): return self.respond({'error':'访问地址不允许'},403)
   parsed=urlparse(self.path); q={k:v[0] for k,v in parse_qs(parsed.query).items()}
   try:
    if parsed.path=='/':
     content=(ROOT/'static'/'index.html').read_text(encoding='utf-8-sig').replace('__CSRF__',TOKEN)
     return self.respond(content,mime='text/html; charset=utf-8')
    if parsed.path in ('/app.js','/i18n.js','/style.css'):
     return self.respond((ROOT/'static'/parsed.path[1:]).read_bytes(),mime='text/javascript; charset=utf-8' if parsed.path.endswith('.js') else 'text/css; charset=utf-8')
    if parsed.path=='/health': return self.respond({'app':'personal-memory','version':APP_VERSION,'pid':os.getpid(),'instance':getattr(self.server,'instance_id',''),'desktop':bool(getattr(self.server,'show_window',None))})
    if parsed.path=='/api/state':
     profile=store.profile(); age=None
     from appearance import palette
     if profile.get('birth_date'):
      from datetime import date
      try:
       b=date.fromisoformat(profile['birth_date']['content']); t=date.fromisoformat(today()); age=t.year-b.year-((t.month,t.day)<(b.month,b.day))
      except ValueError: pass
     return self.respond({'version':APP_VERSION,'data_folder':str(store.path.parent.parent.resolve()),'settings':store.settings(),'appearance':palette(store.settings()),'profile':profile,'fields':store.profile_fields(),'age':age,'sessions':store.sessions(),'jobs':store.job_rows(),'pending':store.pending_reviews_count(),'usage':store.usage_today(),'ai_ready':provider.ready(),'today':today()})
    if parsed.path=='/api/web-ai':return self.respond(web_ai.info())
    if parsed.path=='/api/agenda':
     from agenda import rows
     return self.respond(rows(store,q.get('status','pending'),int(q.get('limit',100)),int(q.get('offset',0))))
    if parsed.path=='/api/appearance':
     from appearance import PRESETS,palette
     return self.respond(dict(presets=PRESETS,current=palette(store.settings())))
    if parsed.path=='/api/onboarding': return self.respond(store.onboarding())
    if parsed.path=='/api/messages': return self.respond(store.messages(q.get('session'),int(q.get('limit',64)),q.get('before'),[int(v) for v in q['ids'].split(',')] if q.get('ids') else None))
    if parsed.path=='/api/records': return self.respond(store.records(q.get('q',''),q.get('kind',''),q.get('archived')=='1',int(q.get('limit',100)),int(q.get('offset',0)),[int(v) for v in q['ids'].split(',')] if q.get('ids') else None,q.get('view','')))
    if parsed.path=='/api/proposals': return self.respond(store.proposal_rows())
    if parsed.path=='/api/history': return self.respond(store.history(int(q['id'])))
    if parsed.path=='/api/summaries':
     with store.connection() as c: data=[dict(r) for r in c.execute("SELECT * FROM summaries WHERE status!='deleted' ORDER BY period DESC,type")]
     return self.respond(data)
    if parsed.path=='/api/digests':
     with store.connection() as c: data=[dict(r) for r in c.execute('SELECT * FROM entry_digests ORDER BY id DESC LIMIT 100')]
     return self.respond(data)
    if parsed.path=='/api/memory-rules':
     from dossier import RULES
     return self.respond(RULES)
    if parsed.path=='/api/prompts':
     from worker import ORGANIZE_PROMPT,SUMMARY_PROMPT
     return self.respond({'档案提取与更新':ORGANIZE_PROMPT,'日常回顾':SUMMARY_PROMPT})
    if parsed.path=='/api/storage': return self.respond(store.storage_stats())
    if parsed.path=='/api/integration':
     from memory_interface import configuration
     return self.respond(configuration(store,provider))
    if parsed.path=='/api/providers': return self.respond([{**p,'has_key':provider.vault.has(p['id'])} for p in store.providers()])
    if parsed.path=='/api/backups':
     folder=store.path.parent.parent/'backups'
     return self.respond([{'name':p.name,'size':p.stat().st_size} for p in sorted([p for p in folder.iterdir() if p.name.endswith('.sqlite3') or p.name.endswith('.sqlite3.gz')],reverse=True)] if folder.exists() else [])
    if parsed.path=='/context': return self.respond(store.export_context(q.get('q','')),mime='text/markdown; charset=utf-8',filename='ai-context.md')
    if parsed.path=='/export':
     document=store.export_all()
     if q.get('compress')=='1': return self.respond(gzip.compress(json.dumps(document,ensure_ascii=False,separators=(',',':')).encode(),mtime=0),mime='application/gzip',filename='personal-export.json.gz')
     return self.respond(document,filename='personal-export.json')
    return self.respond({'error':'页面不存在'},404)
   except (ValueError,KeyError) as e: return self.respond({'error':str(e)},400)
   except Exception: return self.respond({'error':'读取失败，请重试'},500)
  def do_POST(self):
   if not self.valid_host() or not secrets.compare_digest(self.headers.get('X-Memory-CSRF',''),TOKEN): return self.respond({'error':'请求校验失败，请刷新页面'},403)
   origin=self.headers.get('Origin')
   if origin and origin not in ('http://127.0.0.1:'+str(self.server.server_port),'http://localhost:'+str(self.server.server_port)): return self.respond({'error':'请求来源无效'},403)
   try:
    size=int(self.headers.get('Content-Length','0'))
    if size<=0 or size>2_000_000: return self.respond({'error':'请求大小无效'},413)
    data=json.loads(self.rfile.read(size).decode('utf-8'))
    if not isinstance(data,dict): raise ValueError('请求格式无效')
    path=urlparse(self.path).path; result={'ok':True}
    if path=='/api/window/show':
     show=getattr(self.server,'show_window',None)
     if show: show()
     else: raise ValueError('当前是网页版模式')
    elif path=='/api/window/quit':
     quit_window=getattr(self.server,'quit_window',None)
     if quit_window:quit_window()
     else:raise ValueError('当前窗口不支持此退出方式')
    elif path=='/api/data-folder/open':
     if os.name=='nt':os.startfile(str(store.path.parent.parent.resolve()))
     else:raise ValueError('This action is supported on Windows only')
    elif path=='/api/session': result={'id':store.new_session()}
    elif path=='/api/send': result={'id':store.send(data['session_id'],str(data['content']),bool(data.get('share_with_ai')),str(data['request_id']))}; worker.notify()
    elif path=='/api/onboarding': result=store.save_onboarding(data)
    elif path=='/api/profile': store.save_profile(data['fields'],bool(data.get('complete')))
    elif path=='/api/context':
     from retrieval import Retrieval
     result=Retrieval(store,provider).context(**data)
    elif path=='/api/context/sources':
     from retrieval import Retrieval
     result=Retrieval(store,provider).sources(**data)
    elif path=='/api/integration/key':
     from memory_interface import KEY_ID
     key=secrets.token_urlsafe(32); provider.vault.set(KEY_ID,key); store.update_settings({'http_access':True}); result={'key':key}
    elif path=='/api/integration/disable': store.update_settings({'http_access':False})
    elif path=='/api/storage/maintain': result=store.maintain_storage()
    elif path=='/api/agenda/edit':
     from agenda import edit
     result=edit(store,data['id'],data['fields'])
    elif path=='/api/agenda/status':
     from agenda import set_status
     result=set_status(store,data['id'],data['status'])
    elif path=='/api/web-ai/open':result=web_ai.open(data['provider'])
    elif path=='/api/web-ai/prepare':result=web_ai.prepare()
    elif path=='/api/web-ai/apply':result=web_ai.apply(data['request_id'],data['reply'])
    elif path=='/api/settings':
     old=store.settings(); updated=store.update_settings(data)
     if old['autostart']!=updated['autostart']:
      try:
       from desktop import set_autostart
       set_autostart(updated['autostart'])
      except Exception:
       store.update_settings({'autostart':old['autostart']}); raise ValueError('无法更新开机启动设置')
     worker.notify()
    elif path=='/api/provider/save':
     pid=store.save_provider(data)
     if data.get('api_key'): provider.vault.set(pid,str(data['api_key']).strip())
     if data.get('clear_key'): provider.vault.set(pid,'')
     if data.get('activate',True): store.update_settings({'active_provider':pid})
     result={'id':pid}; worker.notify()
    elif path=='/api/provider/test':
     profile=next((p for p in store.providers() if p['id']==data.get('id')),None)
     if not profile: raise ValueError('请先保存 AI 配置')
     reply=provider.request(profile,[{'role':'user','content':'请只回复 OK。'}],'chat'); result={'reply':reply[:200]}
    elif path=='/api/organize': worker.schedule(True); worker.notify()
    elif path=='/api/retry': store.retry_job(int(data['id'])); worker.notify()
    elif path=='/api/review': store.review_proposals(data['ids'],data['action'],data.get('expected'))
    elif path=='/api/proposal':
     proposal=next((p for p in store.proposal_rows() if p['id']==int(data['id'])),None)
     if proposal and proposal['review_level']=='core' and data['action']=='confirmed': store.review_proposals([int(data['id'])],data['action'],data.get('expected'))
     else: store.resolve_proposal(int(data['id']),data['action'])
    elif path=='/api/record/save': result={'id':store.save_record(data.get('record',{}),data.get('id'))}
    elif path in ('/api/record/delete','/api/summary/delete'):
     if not worker.operation_lock.acquire(blocking=False): raise ValueError('AI 正在整理，完成后再删除')
     try:
      if path=='/api/record/delete': store.delete_journal(data['id'])
      else: store.delete_summary(data['id'])
     finally: worker.operation_lock.release()
     worker.notify()
    elif path=='/api/archive': store.change_archive(int(data['id']),bool(data['archived']))
    elif path=='/api/revision': store.restore_revision(int(data['id']))
    elif path=='/api/summary/confirm':
     with store.connection() as c: c.execute("UPDATE summaries SET status='confirmed' WHERE id=? AND status!='deleted'",(int(data['id']),))
    elif path=='/api/backup/delete': store.delete_backup(str(data['name']))
    elif path=='/api/backup': result={'path':str(store.backup())}
    elif path=='/api/restore':
     if not worker.operation_lock.acquire(blocking=False): raise ValueError('AI 任务正在进行，完成后再恢复备份')
     try: store.restore_backup(str(data['name']))
     finally: worker.operation_lock.release()
     worker.notify()
    else: return self.respond({'error':'接口不存在'},404)
    return self.respond(result)
   except (ValueError,KeyError,TypeError,APIError) as e: return self.respond({'error':str(e)},400)
   except Exception: return self.respond({'error':'操作未完成，数据已保留，请重试'},500)
 server=ThreadingHTTPServer(('127.0.0.1',port),Handler,bind_and_activate=False)
 server.allow_reuse_address=False
 try:
  if hasattr(socket,'SO_EXCLUSIVEADDRUSE'): server.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
  server.server_bind(); server.server_activate()
 except Exception:
  server.server_close(); raise
 return server

def main():
 parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); parser.add_argument('--no-browser',action='store_true'); parser.add_argument('--desktop',action='store_true'); parser.add_argument('--init',action='store_true'); parser.add_argument('--interface-port',type=int,default=8766); args=parser.parse_args()
 first_install=getattr(sys,'frozen',False) and not DB.exists()
 store=Store()
 if first_install:
  import ctypes
  store.update_settings({'language':'zh-CN' if ctypes.windll.kernel32.GetUserDefaultUILanguage()&0x3ff==4 else 'en'})
 vault=Vault(store.path.parent/'credentials.bin'); provider=Provider(store,vault); worker=Worker(store,provider)
 if args.init: print('Database ready'); raise SystemExit
 server=create_server(store,provider,worker,args.port); interface=None
 from installed_entry import instance_id
 server.instance_id=instance_id(store.path)
 try:
  from memory_interface import create_interface
  interface=create_interface(store,provider,args.interface_port); provider.interface_port=interface.server_port; threading.Thread(target=interface.serve_forever,daemon=True).start()
 except OSError: print('Read interface port unavailable; local recording remains available.',flush=True)
 worker.start(); url='http://127.0.0.1:'+str(args.port)
 print('Personal Memory ready: '+url,flush=True)
 try:
  if args.desktop:
   threading.Thread(target=server.serve_forever,daemon=True).start()
   from light_desktop import run
   run(url,store,provider,worker,register_show=lambda show:setattr(server,'show_window',show),register_quit=lambda quit:setattr(server,'quit_window',quit))
  else:
   if not args.no_browser: webbrowser.open(url)
   server.serve_forever()
 finally:
  worker.stop(); server.server_close()
  if interface: interface.shutdown(); interface.server_close()

if __name__=='__main__':main()
