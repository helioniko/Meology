"""Small resident Tk window; the full local web UI opens only when requested."""
import ctypes, json, os, sys, threading, uuid
from pathlib import Path
from storage import ROOT

class TkAttachment:
 def __new__(cls,root):
  from desktop_host import DesktopAttachment
  # Cache our top-level HWND before parenting; GA_ROOT would later return Explorer.
  get_ancestor=ctypes.windll.user32.GetAncestor;get_ancestor.argtypes=[ctypes.c_void_p,ctypes.c_uint];get_ancestor.restype=ctypes.c_void_p
  hwnd=get_ancestor(root.winfo_id(),2)
  class Adapter(DesktopAttachment):
   def _invoke(self,action):return action()
   def _hwnd(self):return hwnd
  class Native:
   @property
   def TopMost(self):return bool(root.attributes('-topmost'))
   @TopMost.setter
   def TopMost(self,value):root.attributes('-topmost',bool(value))
  class Window:pass
  window=Window();window.native=Native()
  return Adapter(window)

class LightWindow:
 def t(self,text):
  from i18n import translate
  return translate(text,self.language)
 def apply_language(self):
  self.language=self.store.settings()['language']
  self.root.title(self.t('拾记'));self.brand.configure(text=self.t('拾记'))
  self.placeholder.configure(text=self.t('想到什么就写下来…'))
  self.send_button.configure(text=self.t('发送'));self.ai_check.configure(text=self.t('✓ AI 整理' if self.share.get() else '○ AI 整理'))
  self.embed.configure(text=self.t('解锁' if self.attachment.enabled else '固定'))
  self.agenda_title.configure(text=self.t('日程'));self.agenda_all.configure(text=self.t('全部'));self.agenda_empty.configure(text=self.t('暂无待办'))
  if self.tray:self.tray.title=self.t('拾记 · 轻量窗口');self.tray.update_menu()
  self.layout_card()
 def __init__(self,url,store,provider,worker):
  import tkinter as tk
  from appearance import palette
  self.tk=tk;self.url=url;self.store=store;self.provider=provider;self.worker=worker
  self.closed=False;self.refresh_pending=False;self.changing=False;self.tray=None;self.hotkey_thread_id=None;self.detail_process=None
  self.language=store.settings()['language'];self.colours=palette(store.settings());self.buttons=[];self.sid=next(iter(store.sessions()),{}).get('id');self.last_message_id=None
  self.root=tk.Tk();self.root.title(self.t('拾记'));
  if (ROOT/'packaging'/'meology.ico').exists():self.root.iconbitmap(str(ROOT/'packaging'/'meology.ico'))
  self.root.overrideredirect(True);self.root.configure(bg=self.colours['bg'])
  self.shape_size=None;self.native_rounded=False;self.drag_origin=None
  self.shell=tk.Canvas(self.root,highlightthickness=0,bd=0,takefocus=False);self.shell.place(x=0,y=0,relwidth=1,relheight=1)
  self.root.option_add('*Font',('Microsoft YaHei UI',9));self.root.option_add('*Background',self.colours['bg']);self.root.option_add('*Foreground',self.colours['ink'])
  self.root.minsize(320,220);self.root.maxsize(380,260)
  self.bounds=store.path.parent/'light-window.json'
  try:bounds=json.loads(self.bounds.read_text(encoding='utf-8'))
  except (OSError,ValueError):bounds={}
  compact=bounds.get('layout_version')==3
  width=max(320,min(380,int(bounds.get('width',360)))) if compact else 360
  height=max(220,min(260,int(bounds.get('height',240)))) if compact else 240
  x=int(bounds.get('x',max(0,self.root.winfo_screenwidth()-width-50)));y=int(bounds.get('y',80))
  if not 0<=x<self.root.winfo_screenwidth()-width or not 0<=y<self.root.winfo_screenheight()-height:x=max(0,self.root.winfo_screenwidth()-width-50);y=80
  self.root.geometry(f'{width}x{height}+{x}+{y}');self.root.attributes('-topmost',store.settings()['pinned'])
  self.header=tk.Frame(self.root);self.header.pack(fill='x',padx=16,pady=(14,0))
  self.mark=tk.Canvas(self.header,width=26,height=28,highlightthickness=0,bd=0);self.mark.pack(side='left',padx=(0,7))
  self.brand=tk.Label(self.header,text='拾记',font=('Microsoft YaHei UI',11,'bold'));self.brand.pack(side='left')
  self.embed=self.button(self.header,'固定',self.toggle_desktop);self.embed.pack(side='right')
  self.manage=self.button(self.header,'管理',self.open_management);self.manage.pack(side='right',padx=(0,6))
  for widget in (self.header,self.brand,self.mark):
   widget.configure(cursor='fleur');widget.bind('<ButtonPress-1>',self.start_drag);widget.bind('<B1-Motion>',self.drag);widget.bind('<ButtonRelease-1>',lambda e:setattr(self,'drag_origin',None))
  self.card=tk.Canvas(self.root,height=50,highlightthickness=0,bd=0)
  self.compose=tk.Text(self.card,height=1,wrap='none',relief='flat',borderwidth=0,highlightthickness=0,padx=0,pady=0,undo=True,maxundo=30,insertwidth=2,font=('Microsoft YaHei UI',10))
  self.compose.bind('<FocusIn>',self.layout_card);self.compose.bind('<FocusOut>',self.layout_card)
  self.compose.bind('<ButtonPress-1>',self.focus_compose)
  self.compose.bind('<Return>',self.enter);self.compose.bind('<Shift-Return>',lambda e:'break');self.compose.bind('<<Paste>>',self.paste);self.compose.bind('<KeyRelease>',lambda e:self.update_placeholder())
  self.placeholder=tk.Label(self.card,text='想到什么就写下来…',font=('Microsoft YaHei UI',9),anchor='w',cursor='ibeam')
  self.placeholder.bind('<ButtonPress-1>',self.focus_compose)
  self.footer=tk.Frame(self.card)
  self.share=tk.BooleanVar(value=True)
  self.ai_check=self.button(self.footer,'✓ AI 整理',self.toggle_ai,quiet=True);self.ai_check.text_font.configure(size=8);self.ai_check.configure(text='✓ AI 整理');self.ai_check.pack(side='left')
  self.send_button=self.button(self.footer,'发送',self.send,primary=True);self.send_button.pack(side='right')
  self.card.bind('<Configure>',self.layout_card);self.card.pack(side='bottom',fill='x',padx=16,pady=(8,14))
  self.feedback=tk.StringVar(value='')
  self.agenda_frame=tk.Frame(self.root);self.agenda_frame.pack(fill='both',expand=True,padx=16,pady=(10,0))
  self.agenda_header=tk.Frame(self.agenda_frame);self.agenda_header.pack(fill='x')
  self.agenda_title=tk.Label(self.agenda_header,text='日程',font=('Microsoft YaHei UI',9,'bold'),anchor='w');self.agenda_title.pack(side='left')
  self.agenda_all=self.button(self.agenda_header,'全部',lambda:self.open_full('agenda'),quiet=True);self.agenda_all.pack(side='right')
  self.agenda_list=tk.Frame(self.agenda_frame);self.agenda_list.pack(fill='both',expand=True)
  self.agenda_empty=tk.Label(self.agenda_list,text='暂无待办',font=('Microsoft YaHei UI',9),anchor='w')
  self.agenda_rows=[];self.agenda_items=[]
  for index in range(3):
   row=tk.Frame(self.agenda_list,height=29);row.pack_propagate(False)
   done=self.button(row,'○',lambda i=index:self.complete_task(i),quiet=True);done.configure(width=26);done.pack(side='left')
   title=tk.Label(row,anchor='w',font=('Microsoft YaHei UI',9),cursor='hand2');title.pack(side='left',fill='both',expand=True,padx=(4,0));title.bind('<Button-1>',lambda e:self.open_full('agenda'))
   self.agenda_rows.append((row,done,title))
  self.root.update_idletasks();self.attachment=TkAttachment(self.root)
  from send_feedback import SendFeedback
  self.send_feedback=SendFeedback(self.root,self.card,lambda:self.colours)
  self.root.bind('<Escape>',lambda e:self.close())
  self.root.protocol('WM_DELETE_WINDOW',self.close);self.root.bind('<<MemoryChanged>>',self.request_refresh);self.root.bind('<FocusIn>',self.request_refresh)
  self.root.bind('<Configure>',self.configure_window);self.root.bind('<Destroy>',self.on_destroy)
  self.unsubscribe=store.subscribe(self.changed);self.apply_language();self.apply_theme();self.layout_shell();self.refresh();self.setup_tray();self.schedule_date_refresh()
  if store.settings()['desktop_embedded'] and store.settings()['onboarding_complete']:self.root.after(300,lambda:self.set_desktop(True))
  if not store.settings()['onboarding_complete']:self.root.after(800,lambda:self.open_full('profile'))
 def button(self,parent,text,action,primary=False,quiet=False):
  from rounded_controls import RoundedButton
  button=RoundedButton(parent,text,action,primary,quiet);self.buttons.append((button,primary));return button
 def toggle_ai(self):
  self.share.set(not self.share.get());self.ai_check.configure(text=self.t('✓ AI 整理' if self.share.get() else '○ AI 整理'));self.layout_card()
 def open_management(self):self.open_full('memory' if self.store.pending_reviews_count() else 'settings' if self.store.settings()['ai_mode']=='web' else 'profile')
 def start_drag(self,event):
  if not self.attachment.enabled:self.drag_origin=(event.x_root,event.y_root,self.root.winfo_x(),self.root.winfo_y())
 def drag(self,event):
  if not self.drag_origin or self.attachment.enabled:return
  x,y,left,top=self.drag_origin;self.root.geometry(f'+{max(0,left+event.x_root-x)}+{max(0,top+event.y_root-y)}')
 def configure_window(self,event):
  if event.widget is self.root:self.layout_shell();self.save_bounds(event);self.request_refresh()
 def layout_shell(self):
  from rounded_controls import rounded_shape
  from appearance import mix
  w,h=self.root.winfo_width(),self.root.winfo_height();c=self.colours
  if w<40 or h<40:return
  self.shell.configure(bg=c['bg']);self.shell.delete('all')
  rounded_shape(self.shell,1,1,w-2,h-2,22,fill=c['bg'],outline=mix(c['bg'],c['ink'],.12),width=1)
  self.root.tk.call('lower',self.shell._w)
  if os.name!='nt' or not hasattr(self,'attachment') or self.shape_size==(w,h):return
  from ctypes import wintypes
  user32=ctypes.windll.user32;gdi=ctypes.windll.gdi32
  user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)];user32.GetWindowRect.restype=wintypes.BOOL
  user32.SetWindowRgn.argtypes=[wintypes.HWND,wintypes.HRGN,wintypes.BOOL];user32.SetWindowRgn.restype=ctypes.c_int
  gdi.CreateRoundRectRgn.argtypes=[ctypes.c_int]*6;gdi.CreateRoundRectRgn.restype=wintypes.HRGN
  gdi.DeleteObject.argtypes=[wintypes.HGDIOBJ];gdi.DeleteObject.restype=wintypes.BOOL
  rect=wintypes.RECT();hwnd=self.attachment._hwnd()
  if not user32.GetWindowRect(hwnd,ctypes.byref(rect)):return
  region=gdi.CreateRoundRectRgn(0,0,rect.right-rect.left+1,rect.bottom-rect.top+1,44,44)
  if not region:return
  # Windows owns a region after success; only release it ourselves on failure.
  self.shape_size=(w,h)
  if user32.SetWindowRgn(hwnd,region,True):self.native_rounded=True
  else:gdi.DeleteObject(region);self.shape_size=None
 def apply_theme(self):
  from appearance import palette,luminance
  c=palette(self.store.settings());self.colours=c
  self.root.configure(bg=c['bg']);self.header.configure(bg=c['bg']);self.card.configure(bg=c['bg'])
  self.brand.configure(bg=c['bg'],fg=c['ink']);self.footer.configure(bg=c['paper'])
  self.mark.configure(bg=c['bg']);self.mark.delete('all')
  self.mark.create_oval(1,2,25,26,fill=c['accent'],outline='');self.mark.create_line(9,10,18,10,fill=c['button_ink'],width=2);self.mark.create_line(9,16,15,16,fill=c['button_ink'],width=2)
  self.compose.configure(bg=c['paper'],fg=c['ink'],insertbackground=c['accent'],selectbackground=c['soft'],selectforeground=c['ink'])
  self.placeholder.configure(bg=c['paper'],fg=c['muted'])
  for widget in (self.agenda_frame,self.agenda_header,self.agenda_list):widget.configure(bg=c['bg'])
  self.agenda_title.configure(bg=c['bg'],fg=c['ink']);self.agenda_empty.configure(bg=c['bg'],fg=c['muted'])
  for row,done,title in self.agenda_rows:row.configure(bg=c['bg']);title.configure(bg=c['bg'],fg=c['ink'])
  for button,primary in self.buttons:
   button.set_colours(c,c['paper'] if button.master is self.footer else c['bg'])
  self.layout_card();self.layout_shell()
  if os.name=='nt':
   try:
    hwnd=self.attachment._hwnd();dwm=ctypes.windll.dwmapi.DwmSetWindowAttribute
    dwm.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
    for attribute,colour in [(35,c['bg']),(36,c['ink'])]:
     value=ctypes.c_uint(sum(int(colour[i:i+2],16)<<(8*n) for n,i in enumerate((1,3,5))))
     dwm(hwnd,attribute,ctypes.byref(value),ctypes.sizeof(value))
    dark=ctypes.c_int(luminance(c['bg'])<.3);dwm(hwnd,20,ctypes.byref(dark),ctypes.sizeof(dark))
   except (OSError,AttributeError):pass
 def layout_card(self,event=None):
  w=self.card.winfo_width();h=self.card.winfo_height();c=self.colours
  if w<20 or h<40:return
  from rounded_controls import rounded_shape
  from appearance import mix
  self.card.delete('outline')
  focused=self.root.focus_get() is self.compose
  rounded_shape(self.card,1,1,w-2,h-2,18,fill=c['paper'],outline=mix(c['paper'],c['accent'],.45) if focused else mix(c['paper'],c['ink'],.1),width=1,tags='outline');self.card.tag_lower('outline')
  controls=self.ai_check.winfo_reqwidth()+self.send_button.winfo_reqwidth()+4
  self.footer.place(x=w-controls-9,y=10,width=controls,height=30)
  self.input_width=max(60,w-controls-26);self.compose.place(x=12,y=15,width=self.input_width,height=22);self.update_placeholder()
  if hasattr(self,'send_feedback'):self.send_feedback.reposition()
 def focus_compose(self,event=None):
  # A desktop child can remain inactive after Explorer receives focus. Only
  # an explicit input click claims focus; keep Text's cursor/selection bindings.
  if not self.closed:self.compose.focus_force()
 def update_placeholder(self):
  if not self.compose.get('1.0','end-1c') and self.root.focus_get() is not self.compose:self.placeholder.place(x=12,y=15,width=getattr(self,'input_width',100),height=22)
  else:self.placeholder.place_forget()
 def changed(self):
  if self.closed:return
  try:self.root.event_generate('<<MemoryChanged>>',when='tail')
  except (RuntimeError,self.tk.TclError):pass
 def request_refresh(self,event=None):
  if self.closed or self.refresh_pending:return
  self.refresh_pending=True;self.root.after_idle(self.refresh)
 def paste(self,event=None):
  try:text=self.root.clipboard_get()
  except self.tk.TclError:return 'break'
  self.compose.insert('insert',' '.join(text.splitlines()));self.update_placeholder();return 'break'
 def enter(self,event):
  self.send();return 'break'
 def send(self):
  text=self.compose.get('1.0','end-1c').strip()
  if not text:return
  try:
   if self.sid is None:self.sid=self.store.new_session()
   self.last_message_id=self.store.send(self.sid,text,self.share.get(),uuid.uuid4().hex);self.worker.notify()
   self.compose.delete('1.0','end');self.compose.edit_reset();self.update_placeholder();self.refresh()
   self.send_feedback.show(self.t('已记录 · 等待网页整理' if self.share.get() and self.store.settings()['ai_mode']=='web' else '已记录 · 等待定时整理' if self.share.get() else '已保存在本机'))
  except (ValueError,TypeError) as error:self.send_feedback.hide();self.error(str(error))
 def refresh(self):
  self.refresh_pending=False
  if self.closed:return
  from appearance import palette
  if self.store.settings()['language']!=self.language:self.apply_language()
  if palette(self.store.settings())!=self.colours:self.apply_theme()
  pending=self.store.pending_reviews_count()
  self.manage.configure(text=self.t('管理')+(f' · {pending}' if pending else ''))
  rows=self.store.messages(self.sid,limit=3) if self.sid else []
  user=next((r for r in reversed(rows) if r['role']=='user'),None)
  if user and user['retention_state']=='compact':self.feedback.set(self.t('已整理到档案。点击这里查看详情。'))
  elif user:self.feedback.set(self.t('已保存在本机 · ')+self.t('点击管理，使用网页 AI 整理' if self.store.settings()['ai_mode']=='web' else '等待定时整理' if self.provider.ready() else '配置 AI 后自动整理'))
  else:self.feedback.set('')
  self.render_agenda()
 def render_agenda(self):
  from agenda import rows
  from storage import today
  self.agenda_items=rows(self.store,limit=3)
  self.agenda_empty.pack_forget()
  for index,(frame,done,label) in enumerate(self.agenda_rows):
   frame.pack_forget()
   if index>=len(self.agenda_items) or index>=max(1,(self.root.winfo_height()-152)//29):continue
   item=self.agenda_items[index];due=item['due_at'];date_text=self.t('待办') if not due else (self.t('今天') if due[:10]==today() else due[5:10].replace('-','/'))+((' '+due[11:]) if item['precision']=='time' else '')
   text=date_text+' · '+item['title'];available=max(160,self.root.winfo_width()-75)
   from tkinter import font
   measure=font.Font(font=label.cget('font'))
   while len(text)>1 and measure.measure(text)>available:text=text[:-2]+'…'
   label.configure(text=text,fg=self.colours['accent'] if due and due[:10]<today() else self.colours['ink']);frame.pack(fill='x')
  if not self.agenda_items:self.agenda_empty.pack(fill='x',pady=(14,0))
 def schedule_date_refresh(self):
  from datetime import datetime,timedelta
  from storage import TZ
  clock=datetime.now(TZ);midnight=(clock+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
  self.root.after(max(1000,int((midnight-clock).total_seconds()*1000)),self.date_refresh)
 def date_refresh(self):
  if self.closed:return
  self.request_refresh();self.schedule_date_refresh()
 def complete_task(self,index):
  if index>=len(self.agenda_items):return
  from agenda import set_status
  try:set_status(self.store,self.agenda_items[index]['id'],'done');self.refresh()
  except ValueError as error:self.error(str(error))
 def open_full(self,view='settings'):
  import subprocess
  if view not in ('chat','profile','journal','memory','settings','connect','agenda'):raise ValueError('窗口页面无效')
  if self.detail_process and self.detail_process.poll() is None:
   try:self.detail_process.stdin.write(json.dumps(dict(view=view,language=self.language))+'\n');self.detail_process.stdin.flush();return
   except (OSError,ValueError):pass
  if self.detail_process and self.detail_process.stdin:self.detail_process.stdin.close()
  from app_runtime import helper_command
  folder=self.store.path.parent.parent/'.local-cache';folder.mkdir(parents=True,exist_ok=True)
  args=helper_command('panel')+['--url',self.url,'--view',view,'--background',self.colours['bg'],'--language',self.language]
  try:
   with (folder/'details-error.log').open('w',encoding='utf-8') as log:
    self.detail_process=subprocess.Popen(args,cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,text=True,encoding='utf-8',env={**os.environ,'MEOLOGY_DATA_ROOT':str(self.store.path.parent.parent)},creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
  except OSError:self.error('无法打开大窗口，请检查桌面依赖。')
 def close_details(self):
  process=self.detail_process
  if process and process.poll() is None:
   try:process.stdin.write('{"action":"quit"}\n');process.stdin.flush();process.wait(timeout=2)
   except Exception:
    if process.poll() is None:process.terminate()
  if process and process.stdin:process.stdin.close()
  self.detail_process=None
 def error(self,message):
  from tkinter import messagebox
  from i18n import error_text
  messagebox.showerror(self.t('拾记'),error_text(message,self.language),parent=self.root)
 def toggle_desktop(self):self.set_desktop(not self.attachment.enabled)
 def set_desktop(self,enabled,persist=True):
  self.changing=True
  try:
   result=self.attachment.set_enabled(enabled)
   if persist:self.store.update_settings({'desktop_embedded':result})
   self.embed.configure(text=self.t('解锁' if result else '固定'));self.shape_size=None;self.layout_shell();return result
  except Exception as error:
   self.store.update_settings({'desktop_embedded':False});self.error(str(error));return False
  finally:self.changing=False
 def show(self):
  if self.closed:return
  self.root.deiconify()
  if self.attachment.enabled:ctypes.windll.user32.ShowWindow(self.attachment._hwnd(),5)
  else:self.root.lift()
  self.request_refresh()
 def restore(self):
  if self.attachment.enabled:self.set_desktop(False)
  self.show()
 def save_bounds(self,event=None):
  if self.closed or self.changing or self.attachment.enabled or (event and event.widget is not self.root):return
  if getattr(self,'bounds_timer',None):self.root.after_cancel(self.bounds_timer)
  self.bounds_timer=self.root.after(700,self.write_bounds)
 def write_bounds(self):
  self.bounds_timer=None
  if self.root.state()!='normal' or self.attachment.enabled:return
  self.bounds.write_text(json.dumps(dict(layout_version=3,x=self.root.winfo_x(),y=self.root.winfo_y(),width=self.root.winfo_width(),height=self.root.winfo_height())),encoding='utf-8')
 def close(self):
  if self.attachment.enabled:return False
  if self.tray:self.root.withdraw();return False
  self.quit();return True
 def dispatch(self,action):
  if self.closed:return
  try:self.root.after(0,action)
  except (RuntimeError,self.tk.TclError):pass
 def setup_tray(self):
  vendor=ROOT/'vendor'
  if str(vendor) not in sys.path:sys.path.insert(0,str(vendor))
  try:
   import pystray
   from PIL import Image,ImageDraw
   image=Image.new('RGBA',(32,32),self.colours['accent']);draw=ImageDraw.Draw(image);draw.rounded_rectangle((7,5,25,27),4,fill=self.colours['paper']);draw.line((11,12,21,12),fill=self.colours['accent'],width=2);draw.line((11,18,21,18),fill=self.colours['accent'],width=2)
   self.tray=pystray.Icon('personal-memory',image,self.t('拾记 · 轻量窗口'),pystray.Menu(
    pystray.MenuItem(lambda item:self.t('打开拾记'),lambda *a:self.dispatch(self.show),default=True),
    pystray.MenuItem(lambda item:self.t('恢复普通窗口'),lambda *a:self.dispatch(self.restore)),
    pystray.MenuItem(lambda item:self.t('完整页面'),lambda *a:self.dispatch(lambda:self.open_full('chat'))),
    pystray.MenuItem(lambda item:self.t('退出'),lambda *a:self.dispatch(self.quit))))
   threading.Thread(target=self.tray.run,name='memory-tray',daemon=True).start()
  except ImportError:self.tray=None
  if os.name=='nt':threading.Thread(target=self.hotkey_loop,name='memory-hotkey',daemon=True).start()
 def hotkey_loop(self):
  from ctypes import wintypes
  user32=ctypes.windll.user32;self.hotkey_thread_id=ctypes.windll.kernel32.GetCurrentThreadId()
  if not user32.RegisterHotKey(None,7101,0x0001|0x0002|0x4000,0x20):return
  message=wintypes.MSG()
  try:
   while user32.GetMessageW(ctypes.byref(message),None,0,0)>0:
    if message.message==0x0312:self.dispatch(self.restore)
  finally:user32.UnregisterHotKey(None,7101)
 def on_destroy(self,event):
  if event.widget is self.root:self.closed=True
 def quit(self):
  if self.closed:return
  if self.attachment.enabled:self.set_desktop(False,persist=False)
  self.close_details();self.send_feedback.hide()
  self.closed=True;self.unsubscribe()
  for timer in self.root.tk.call('after','info'):self.root.after_cancel(timer)
  self.bounds_timer=None
  if self.tray:self.tray.stop()
  if self.hotkey_thread_id:ctypes.windll.user32.PostThreadMessageW(self.hotkey_thread_id,0x0012,0,0)
  self.root.destroy()

def run(url,store,provider,worker,register_show=None,register_quit=None):
 window=LightWindow(url,store,provider,worker)
 if register_show:register_show(lambda:window.dispatch(window.show))
 if register_quit:register_quit(lambda:window.dispatch(window.quit))
 try:window.root.mainloop()
 finally:
  if not window.closed:window.quit()
