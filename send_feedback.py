"""Short in-window feedback; one bounded timer and no extra window or thread."""
import time
import tkinter as tk
from tkinter import font
from rounded_controls import rounded_shape
from appearance import mix

class SendFeedback(tk.Canvas):
 def __init__(self,parent,anchor,colours):
  super().__init__(parent,height=34,highlightthickness=0,bd=0,takefocus=False,bg=colours()['bg'])
  self.anchor=anchor;self.colours=colours;self.timer=None;self.visible=False;self.message='';self.started=0
  self.text_font=font.Font(family='Microsoft YaHei UI',size=9)
  self.bind('<Destroy>',lambda e:self.cancel() if e.widget is self else None)
 def cancel(self):
  if self.timer is not None:
   try:self.after_cancel(self.timer)
   except tk.TclError:pass
   self.timer=None
 def hide(self):
  self.cancel();self.visible=False
  try:self.place_forget();self.delete('all')
  except tk.TclError:pass
 def show(self,message):
  self.cancel();self.message=message;self.started=time.monotonic();self.visible=True
  self.reposition();self.master.tk.call('raise',self._w);self.tick()
 def reposition(self):
  if not self.visible:return
  width=min(self.master.winfo_width()-32,self.text_font.measure(self.message)+54)
  self.place(x=(self.master.winfo_width()-width)//2,y=max(46,self.anchor.winfo_y()-40),width=width,height=34)
 def tick(self):
  self.timer=None
  if not self.visible:return
  age=time.monotonic()-self.started
  if age>=1.55:self.hide();return
  alpha=1-(1-min(1,age/.16))**3 if age<.16 else 1 if age<.95 else (1-(age-.95)/.6)**2
  c=self.colours();bg=c['bg'];self.configure(bg=bg);self.delete('all')
  width=int(self.place_info().get('width',200))
  rounded_shape(self,1,3,width-2,30,15,fill=mix(bg,c['ink'],.07*alpha),outline='')
  rounded_shape(self,1,1,width-2,30,15,fill=mix(bg,c['paper'],alpha),outline=mix(bg,c['accent'],.18*alpha))
  self.create_text(20,16,text='✓',font=('Microsoft YaHei UI',10,'bold'),fill=mix(bg,c['accent'],alpha))
  self.create_text(width/2+10,16,text=self.message,font=self.text_font,fill=mix(bg,c['ink'],alpha))
  self.timer=self.after(33,self.tick)
