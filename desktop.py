"""Windows user startup registration for the installed app and source launcher."""
import sys
from pathlib import Path
from storage import ROOT

def set_autostart(enabled):
 import winreg
 executable=Path(sys.executable).with_name('pythonw.exe')
 if not executable.exists(): executable=Path(sys.executable)
 command='"'+str(sys.executable)+'"' if getattr(sys,'frozen',False) else '"'+str(executable)+'" "'+str(ROOT/'app.py')+'" --desktop'
 value_name='Meology' if getattr(sys,'frozen',False) else 'PersonalMemory'
 with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
  if enabled: winreg.SetValueEx(key,value_name,0,winreg.REG_SZ,command)
  else:
   try: winreg.DeleteValue(key,value_name)
   except FileNotFoundError: pass
