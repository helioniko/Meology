"""Product identity and writable paths, independent of bundled resources."""
import os, sys
from pathlib import Path
APP_VERSION = '1.0.1'
DISPLAY_VERSION = 'V1.0.1'
APP_NAME = 'Meology'
CHINESE_NAME = '拾记'
RESOURCE_ROOT = Path(__file__).resolve().parent

def data_root():
    override = os.environ.get('MEOLOGY_DATA_ROOT')
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, 'frozen', False):
        return Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / APP_NAME
    return RESOURCE_ROOT

DATA_ROOT = data_root()
DB_PATH = DATA_ROOT / 'data' / 'personal.sqlite3'
CACHE_ROOT = DATA_ROOT / '.local-cache'

def helper_command(kind):
    if getattr(sys, 'frozen', False):
        return [str(Path(sys.executable).with_name({'panel':'MeologyPanel.exe', 'mcp':'MeologyMCP.exe'}[kind]))]
    executable=Path(sys.executable)
    if kind=='mcp' and executable.name.lower()=='pythonw.exe' and executable.with_name('python.exe').exists():executable=executable.with_name('python.exe')
    return [str(executable), '-X', 'utf8', str(RESOURCE_ROOT / {'panel':'detail_window.py', 'mcp':'memory_interface.py'}[kind])]
