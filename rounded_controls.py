"""Small canvas controls; no images, animation timers or browser runtime."""
import tkinter as tk
from tkinter import font


def rounded_shape(canvas, x, y, box_width, box_height, radius, **options):
 radius=min(radius,box_width/2,box_height/2);right=x+box_width;bottom=y+box_height
 points=(x+radius,y,right-radius,y,right,y,right,y+radius,right,bottom-radius,right,bottom,right-radius,bottom,x+radius,bottom,x,bottom,x,bottom-radius,x,y+radius,x,y)
 return canvas.create_polygon(points,smooth=True,splinesteps=32,**options)


class RoundedButton(tk.Canvas):
 def __init__(self,parent,text,command,primary=False,quiet=False):
  self.text=text;self.command=command;self.primary=primary;self.quiet=quiet
  self.hover=False;self.pressed=False;self.focused=False;self.colours=None;self.surface=None
  self.text_font=font.Font(family='Microsoft YaHei UI',size=9,weight='bold' if primary else 'normal')
  super().__init__(parent,width=max(44,self.text_font.measure(text)+24),height=30 if primary else 28,highlightthickness=0,bd=0,takefocus=True,cursor='hand2')
  self.bind('<Configure>',lambda e:self.draw())
  self.bind('<Enter>',lambda e:self.state(hover=True));self.bind('<Leave>',lambda e:self.state(hover=False,pressed=False))
  self.bind('<FocusIn>',lambda e:self.state(focused=True));self.bind('<FocusOut>',lambda e:self.state(focused=False))
  self.bind('<ButtonPress-1>',self.press);self.bind('<ButtonRelease-1>',self.release)
  self.bind('<Return>',self.activate);self.bind('<space>',self.activate)
 def configure(self,cnf=None,**kwargs):
  options=dict(cnf or {});options.update(kwargs)
  if 'text' in options:
   self.text=options.pop('text');options['width']=max(44,self.text_font.measure(self.text)+24)
  result=super().configure(**options) if options else None
  self.draw();return result
 config=configure
 def set_colours(self,colours,surface):
  self.colours=colours;self.surface=surface;super().configure(bg=surface);self.draw()
 def state(self,**values):
  for key,value in values.items():setattr(self,key,value)
  self.draw()
 def press(self,event):self.focus_set();self.state(pressed=True)
 def release(self,event):
  was_pressed=self.pressed;self.state(pressed=False)
  if was_pressed and 0<=event.x<self.winfo_width() and 0<=event.y<self.winfo_height():self.invoke()
 def activate(self,event=None):self.invoke();return 'break'
 def invoke(self):return self.command()
 def draw(self):
  if not self.colours:return
  from appearance import mix,contrast
  c=self.colours;w=self.winfo_width();h=self.winfo_height()
  if w<10 or h<10:return
  self.delete('all')
  if self.primary:
   fill=mix(c['accent'],c['ink'],.12) if self.pressed else mix(c['accent'],c['paper'],.1) if self.hover else c['accent'];ink=c['button_ink']
  else:
   fill=c['hover'] if self.pressed else c['soft'] if self.hover else self.surface if self.quiet else mix(self.surface,c['accent'],.08);ink=c['accent'] if self.quiet and contrast(c['accent'],self.surface)>=3 else c['ink']
  rounded_shape(self,1,1,w-2,h-2,14,fill=fill,outline=c['accent'] if self.focused else fill,width=1)
  self.create_text(w/2,h/2,text=self.text,font=self.text_font,fill=ink)
