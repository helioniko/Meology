from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules
root=Path(SPECPATH).parent
assets=[(str(root/'static'),'static'),(str(root/'locales'),'locales'),(str(root/'packaging'/'meology.ico'),'packaging'),(str(root/'docs'/'personal-memory-v1.schema.json'),'docs')]
assets+=collect_data_files('webview')+collect_data_files('pythonnet')+collect_data_files('clr_loader')
binaries=collect_dynamic_libs('clr_loader')
hidden=['detail_window','memory_interface','light_desktop','desktop','webview.platforms.winforms','webview.platforms.edgechromium','pystray._win32']+collect_submodules('clr_loader')
a=Analysis([str(root/'installed_entry.py')],pathex=[str(root)],binaries=binaries,datas=assets,hiddenimports=hidden,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['PyQt5','PyQt6','PySide2','PySide6','gi','webview.platforms.qt','webview.platforms.gtk','webview.platforms.cocoa','matplotlib','numpy','pytest','unittest','IPython'],noarchive=False)
pyz=PYZ(a.pure)
common=dict(exclude_binaries=True,debug=False,bootloader_ignore_signals=False,strip=False,upx=False,icon=str(root/'packaging'/'meology.ico'),version=str(root/'packaging'/'version_info.txt'))
main=EXE(pyz,a.scripts,[],name='Meology',console=False,**common)
panel=EXE(pyz,a.scripts,[],name='MeologyPanel',console=True,**common)
mcp=EXE(pyz,a.scripts,[],name='MeologyMCP',console=True,**common)
coll=COLLECT(main,panel,mcp,a.binaries,a.datas,strip=False,upx=False,name='Meology')
