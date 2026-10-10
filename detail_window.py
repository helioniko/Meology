"""On-demand full UI in a separate window; closing exits its browser process."""
import argparse,json,sys,threading
from pathlib import Path
from urllib.parse import urlparse
from app_runtime import RESOURCE_ROOT as ROOT, CACHE_ROOT
sys.path.insert(0,str(ROOT/'vendor'))
VIEWS={'chat':'随手记','profile':'我的档案','journal':'记录与回顾','memory':'核心审核','settings':'设置','connect':'其他 AI','agenda':'日程'}

def run(url,view='settings',background='#f5f5f2',language='zh-CN'):
 import webview
 from i18n import translate
 parsed=urlparse(url)
 if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.port or parsed.path not in ('','/') or parsed.query or parsed.fragment:raise ValueError('仅支持本地拾记界面')
 if view not in VIEWS:raise ValueError('窗口页面无效')
 webview.settings['ALLOW_DOWNLOADS']=True;webview.settings['ALLOW_FILE_URLS']=False
 class Bridge:
  def set_language(self,selected,current_view):
   nonlocal language
   if selected not in ('zh-CN','en') or current_view not in VIEWS:return False
   language=selected;window.set_title(translate('拾记',language)+' · '+translate(VIEWS[current_view],language));return True
 window=webview.create_window(translate('拾记',language)+' · '+translate(VIEWS[view],language),url.rstrip('/')+'/?panel=1#'+view,width=1100,height=780,min_size=(760,560),background_color=background,js_api=Bridge())
 def commands():
  nonlocal language
  for line in sys.stdin:
   try:
    action=json.loads(line)
    if action.get('action')=='quit':window.destroy();return
    selected=action.get('view')
    if selected in VIEWS:
     language=action.get('language',language) if action.get('language',language) in ('zh-CN','en') else language;window.show();window.restore();window.set_title(translate('拾记',language)+' · '+translate(VIEWS[selected],language))
     window.evaluate_js('location.hash='+json.dumps(selected))
   except Exception:pass
 def setup():
  if sys.stdin:threading.Thread(target=commands,name='panel-commands',daemon=True).start()
 webview.start(setup,gui='edgechromium',debug=False,private_mode=True,storage_path=str(CACHE_ROOT/'panel-webview'))

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--url',required=True);parser.add_argument('--view',default='settings');parser.add_argument('--background',default='#f5f5f2');parser.add_argument('--language',choices=['zh-CN','en'],default='zh-CN');args=parser.parse_args()
 run(args.url,args.view,args.background,args.language)

if __name__=='__main__':main()
