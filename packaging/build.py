"""Reproducible Windows release builder. Never includes local databases or secrets."""
import hashlib,importlib.metadata,json,os,shutil,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app_runtime import APP_VERSION
CACHE=ROOT/'.local-cache'/'build-tools'
OUTPUT=ROOT/'.local-cache'/'package'/'dist'/'Meology'
DOWNLOADS={
 'innosetup-6.7.3.exe':('https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe','9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732'),
 'MicrosoftEdgeWebview2Setup.exe':('https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/86136859-b194-4c25-9482-6d47633ec46b/MicrosoftEdgeWebview2Setup.exe','87ad3fe4e3faa1b48bad79de1b9269e5eb30574545bb6f5f7c37d51035748caf')}

def download_tools():
 CACHE.mkdir(parents=True,exist_ok=True)
 for name,(url,digest) in DOWNLOADS.items():
  target=CACHE/name
  if not target.exists():
   part=target.with_suffix('.partial')
   with urllib.request.urlopen(url,timeout=120) as response,part.open('wb') as out:
    while chunk:=response.read(1024*1024):out.write(chunk)
   if hashlib.sha256(part.read_bytes()).hexdigest()!=digest:raise RuntimeError('Unexpected checksum: '+name)
   part.replace(target)
  if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise RuntimeError('Unexpected checksum: '+name)
  check="$s=Get-AuthenticodeSignature -LiteralPath '"+str(target).replace("'","''")+"'; if($s.Status -ne 'Valid'){exit 1}"
  tool_env=dict(os.environ);tool_env.pop('PSModulePath',None)
  subprocess.run([shutil.which('pwsh.exe') or 'powershell.exe','-NoProfile','-NonInteractive','-Command',check],check=True,env=tool_env)
 compiler=CACHE/'inno'/'ISCC.exe'
 if not compiler.exists():
  subprocess.run([str(CACHE/'innosetup-6.7.3.exe'),'/PORTABLE=1','/CURRENTUSER','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/NOICONS','/TASKS=','/DIR='+str(compiler.parent)],check=True)
 return compiler

def licenses():
 folder=OUTPUT/'THIRD_PARTY_LICENSES';folder.mkdir(parents=True,exist_ok=True);notices=[]
 for name in ['pywebview','pystray','Pillow','pythonnet','clr_loader','cffi','pycparser','bottle','proxy_tools','six','typing_extensions','PyInstaller','setuptools','packaging']:
  dist=importlib.metadata.distribution(name);notices.append(name+' '+dist.version+'\n'+str(dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'See included license text'))
  for file in dist.files or []:
   if any(value in str(file).lower() for value in ('license','copying','notice')) and dist.locate_file(file).is_file():
    (folder/(name+'-'+str(file).replace('/','_').replace('\\','_'))).write_bytes(dist.locate_file(file).read_bytes())
 base=Path(sys.base_prefix)
 for file in [base/'LICENSE.txt',base/'tcl'/'tcl8.6'/'license.terms',base/'tcl'/'tk8.6'/'license.terms']:
  if file.exists():(folder/(file.parent.name+'-'+file.name)).write_bytes(file.read_bytes())
 (OUTPUT/'THIRD_PARTY_NOTICES.txt').write_text('\n\n'.join(notices)+'\n\nMicrosoft Edge WebView2 is redistributed as an unmodified Microsoft Evergreen bootstrapper.\nhttps://developer.microsoft.com/microsoft-edge/webview2/\n',encoding='utf-8')
 for file in ['Windows安装与发布.md','Windows-Quick-Start.txt']:(OUTPUT/file).write_bytes((ROOT/'docs'/file).read_bytes())

if __name__=='__main__':
 if os.name!='nt':raise SystemExit('Build this x64 release on Windows x64.')
 compiler=download_tools()
 subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--distpath',str(OUTPUT.parent),'--workpath',str(ROOT/'.local-cache'/'package'/'build'),str(ROOT/'packaging'/'Meology.spec')],cwd=ROOT,check=True)
 licenses()
 prohibited={'personal.sqlite3','credentials.bin','api_key','test-placeholder-only'}
 for file in OUTPUT.rglob('*'):
  if file.name in prohibited or file.suffix.lower() in ('.sqlite3','.db') or file.name.startswith('test_') or '.git' in file.parts:raise RuntimeError('Unexpected private/test artifact: '+str(file))
 subprocess.run([str(compiler),'/DAppVersion='+APP_VERSION,'/DSourceDir='+str(OUTPUT),'/DRuntimeInstaller='+str(CACHE/'MicrosoftEdgeWebview2Setup.exe'),str(ROOT/'packaging'/'Meology.iss')],cwd=ROOT,check=True)
 setup=ROOT/'release'/('Meology-'+APP_VERSION+'-Setup-x64.exe')
 digest=hashlib.sha256(setup.read_bytes()).hexdigest();setup.with_suffix('.exe.sha256').write_text(digest+'  '+setup.name+'\n',encoding='ascii')
 manifest={'product':'Meology','version':APP_VERSION,'platform':'Windows 10 2004+ / Windows 11 x64','sha256':digest,'bytes':setup.stat().st_size,'contains_personal_data':False,'signed':False,'runtime_installers':{k:v[1] for k,v in DOWNLOADS.items()}}
 (setup.parent/'release-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Release ready:',setup)
