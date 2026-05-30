; DeskFlow 安装包配置 — Inno Setup
; 在 GitHub Actions Windows runner 上自动编译

#define MyAppName "DeskFlow"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "DeskFlow"
#define MyAppURL "https://github.com/gentle233/deskflow"
#define MyAppExeName "DeskFlow.exe"

[Setup]
; 基本信息
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 安装路径：%LOCALAPPDATA%\DeskFlow（无需管理员权限）
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; 输出
OutputDir=installer
OutputBaseFilename=DeskFlow-Setup-{#MyAppVersion}

; 压缩
Compression=lzma2/max
SolidCompression=yes

; 图标
SetupIconFile=ui\icons\deskflow.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; 权限：不需要管理员，当前用户安装
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog

; 其他
AllowNoIcons=yes
ShowComponentSizes=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式:"; Flags: checkedonce

[Files]
; 整个 dist\DeskFlow\ 目录所有文件
Source: "dist\DeskFlow\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; 安装完成后可选启动
Filename: "{app}\{#MyAppExeName}"; Description: "启动 DeskFlow"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 卸载时删除用户配置（可选）
; Filename: "{cmd}"; Parameters: "/c rmdir /s /q ""{localappdata}\.deskflow"""; Flags: runhidden

[Code]
{ 安装前检查旧版本并关闭 }
function InitializeSetup: Boolean;
var
  ResultCode: Integer;
begin
  { 如果正在运行，尝试关闭它 }
  Exec('taskkill', '/f /im DeskFlow.exe', '', 0, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
