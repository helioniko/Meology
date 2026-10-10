"""Shared, small colour preferences; independent of personal data and providers."""
import re
PRESETS={
 'paper':dict(label='暖白',theme_bg='#f5f5f2',theme_accent='#47725d',theme_text='#283a31'),
 'sage':dict(label='鼠尾草',theme_bg='#eaf0e8',theme_accent='#55735b',theme_text='#263b2c'),
 'blue':dict(label='雾蓝',theme_bg='#edf2f7',theme_accent='#4b6b91',theme_text='#263647'),
 'night':dict(label='夜色',theme_bg='#24272c',theme_accent='#95bfa7',theme_text='#e8eee9')}
DEFAULTS=dict(theme_preset='paper',**{k:v for k,v in PRESETS['paper'].items() if k!='label'})

def mix(a,b,fraction):
 return '#'+''.join(f'{round(int(a[i:i+2],16)*(1-fraction)+int(b[i:i+2],16)*fraction):02x}' for i in (1,3,5))
def luminance(colour):
 values=[int(colour[i:i+2],16)/255 for i in (1,3,5)]
 values=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
 return sum(a*b for a,b in zip(values,(.2126,.7152,.0722)))
def contrast(a,b):
 light,dark=sorted((luminance(a),luminance(b)),reverse=True);return (light+.05)/(dark+.05)
def validate(settings):
 if settings['theme_preset'] not in (*PRESETS,'custom'):raise ValueError('配色选项无效')
 for key in ('theme_bg','theme_accent','theme_text'):
  if not isinstance(settings[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',settings[key]):raise ValueError('颜色须为 #RRGGBB 格式')
def palette(settings):
 values={**DEFAULTS,**settings};validate(values)
 if values['theme_preset'] in PRESETS:values.update(PRESETS[values['theme_preset']])
 bg,accent,text=(values[k].lower() for k in ('theme_bg','theme_accent','theme_text'))
 dark=luminance(bg)<.3
 return dict(bg=bg,accent=accent,ink=text,paper=mix(bg,'#ffffff',.05 if dark else .8),
  soft=mix(bg,accent,.12),line=mix(bg,text,.15),muted=mix(bg,text,.6),hover=mix(bg,accent,.2),
  button_ink='#ffffff' if contrast(accent,'#ffffff')>=contrast(accent,'#17251d') else '#17251d')
