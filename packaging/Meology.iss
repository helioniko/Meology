#ifndef AppVersion
 #define AppVersion "1.0.1"
#endif
#ifndef SourceDir
 #define SourceDir "..\.local-cache\package\dist\Meology"
#endif
#ifndef RuntimeInstaller
 #define RuntimeInstaller "..\.local-cache\build-tools\MicrosoftEdgeWebview2Setup.exe"
#endif
[Setup]
AppId={{D568531D-2A6F-442F-BB58-795C6FAC1F4D}
AppName=拾记 · Meology
AppVersion={#AppVersion}
AppVerName=拾记 · Meology V{#AppVersion}
AppPublisher=Meology
DefaultDirName={localappdata}\Programs\Meology
DefaultGroupName=拾记 · Meology
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir=..\release
OutputBaseFilename=Meology-{#AppVersion}-Setup-x64
SetupIconFile=meology.ico
UninstallDisplayIcon={app}\Meology.exe
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Meology
VersionInfoDescription=Meology V{#AppVersion} Windows Setup
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
CloseApplicationsFilter=Meology.exe,MeologyPanel.exe,MeologyMCP.exe
RestartApplications=no
DisableProgramGroupPage=yes
DisableWelcomePage=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
Uninstallable=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimplified.AppShortcut=拾记 · Meology
english.AppShortcut=Meology · 拾记
chinesesimplified.DesktopShortcut=创建桌面图标（推荐）
english.DesktopShortcut=Create a desktop shortcut (recommended)
chinesesimplified.LaunchApp=立即启动拾记 · Meology
english.LaunchApp=Launch Meology now
chinesesimplified.UninstallApp=卸载拾记 · Meology
english.UninstallApp=Uninstall Meology
chinesesimplified.RuntimeInstalling=正在联网补齐管理界面所需的 WebView2 组件，请稍候…
english.RuntimeInstalling=Downloading WebView2 for the management window. Please keep the computer online…
chinesesimplified.RuntimeFailed=无法安装 WebView2 运行组件。请从 Microsoft 官网安装 WebView2 后重新运行本安装程序。
english.RuntimeFailed=WebView2 could not be installed. Install WebView2 from Microsoft and run this setup again.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; Flags: checkedonce

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RuntimeInstaller}"; DestName: "MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{userdesktop}\{cm:AppShortcut}"; Filename: "{app}\Meology.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userprograms}\{groupname}\{cm:AppShortcut}"; Filename: "{app}\Meology.exe"; WorkingDir: "{app}"
Name: "{userprograms}\{groupname}\{cm:UninstallApp}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Meology.exe"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Meology"; Flags: uninsdeletevalue

[Code]
function WebViewInstalled: Boolean;
var Version: String;
begin
  Result := (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM32, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;
function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer;
begin
  Result := '';
  if not WebViewInstalled then begin
    WizardForm.StatusLabel.Caption := CustomMessage('RuntimeInstalling');
    ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
    if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Code) then
      Result := CustomMessage('RuntimeFailed')
    else if not WebViewInstalled then
      Result := CustomMessage('RuntimeFailed');
  end;
end;
