"""Frozen entry points; no user interpreter or console is needed to launch."""
import ctypes, hashlib, json, os, re, socket, sys, time
from pathlib import Path
from urllib.request import Request, urlopen
from app_runtime import APP_NAME, APP_VERSION, DB_PATH, CACHE_ROOT

def instance_id(path):
    return hashlib.sha256(os.path.normcase(str(Path(path).resolve())).encode('utf-8')).hexdigest()[:24]

def show_existing(endpoint, identity):
    try:
        url=endpoint['url']
        if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}',url):return False
        with urlopen(url+'/health',timeout=1) as response:health=json.load(response)
        if health.get('instance')!=identity or not health.get('desktop'):return False
        with urlopen(url+'/',timeout=1) as response:html=response.read().decode('utf-8')
        token=re.search(r'name="memory-csrf" content="([^"]+)"',html).group(1)
        with urlopen(Request(url+'/api/window/show',data=b'{}',headers={'Content-Type':'application/json','X-Memory-CSRF':token}),timeout=2):pass
        return True
    except (OSError,ValueError,KeyError,AttributeError):return False

def free_port(preferred, excluded=()):
    for port in [preferred]+list(range(preferred+10000,preferred+10020)):
        if port in excluded:continue
        with socket.socket() as sock:
            try:sock.bind(('127.0.0.1',port));return port
            except OSError:pass
    raise OSError('No local port is available')

def launch():
    if sys.stdin is None:sys.stdin=open(os.devnull,'r',encoding='utf-8')
    if sys.stdout is None:sys.stdout=open(os.devnull,'w',encoding='utf-8')
    if sys.stderr is None:sys.stderr=open(os.devnull,'w',encoding='utf-8')
    identity=instance_id(DB_PATH);CACHE_ROOT.mkdir(parents=True,exist_ok=True)
    endpoint_path=CACHE_ROOT/'instance.json'
    kernel=ctypes.windll.kernel32
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle.restype=ctypes.c_bool
    handle=kernel.CreateMutexW(None,False,'Local\\Meology-'+identity)
    if not handle:raise OSError('Cannot create the application instance')
    existed=kernel.GetLastError()==183
    try:
        if existed:
            for _ in range(60):
                try:
                    if show_existing(json.loads(endpoint_path.read_text(encoding='utf-8')),identity):return
                except (OSError,ValueError):pass
                time.sleep(.15)
            ctypes.windll.user32.MessageBoxW(None,'Meology is already starting. Please try again in a moment.\n拾记正在启动，请稍后再试。',APP_NAME,0x40)
            return
        options=sys.argv[1:]
        if not any(arg in options for arg in ('--no-browser','--desktop','--init')):options+=['--desktop']
        if '--port' not in options:options+=['--port',str(free_port(8765))]
        port=int(options[options.index('--port')+1])
        if '--interface-port' not in options:options+=['--interface-port',str(free_port(8766,(port,)))]
        endpoint_path.write_text(json.dumps({'url':'http://127.0.0.1:'+str(port),'version':APP_VERSION}),encoding='utf-8')
        sys.argv=[sys.argv[0]]+options
        import app
        app.main()
    finally:
        if not existed:
            try:endpoint_path.unlink()
            except OSError:pass
        kernel.CloseHandle(handle)

def main():
    from multiprocessing import freeze_support
    freeze_support()
    helper=Path(sys.executable).stem if getattr(sys,'frozen',False) else ''
    if helper=='MeologyPanel':
        from detail_window import main as panel_main
        panel_main();return
    if helper=='MeologyMCP':
        from memory_interface import main as mcp_main
        mcp_main();return
    try:launch()
    except Exception as error:
        # Record the failure type only; never include input, API keys or API replies.
        CACHE_ROOT.mkdir(parents=True,exist_ok=True)
        (CACHE_ROOT/'startup-error.log').write_text(type(error).__name__,encoding='utf-8')
        ctypes.windll.user32.MessageBoxW(None,'Meology could not start. Please reinstall Meology or check that the data folder is writable.\n拾记无法启动，请重新安装拾记或检查数据文件夹是否可写。\n'+str(CACHE_ROOT/'startup-error.log'),APP_NAME,0x10)
        raise SystemExit(1)

if __name__=='__main__':main()
