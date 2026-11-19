;由 Inno Setup Script Wizard 生成的脚本。
;有关创建 INNO SETUP 脚本文件的详细信息，请参阅文档
; 将Inno Setup 的安装目录添加到环境变量中 在命令行使用 ISCC "{xxx.iss}" 全路径 进行编译
; 或者 cd 到Inno Setup 的安装目录，然后在命令行中使用 iscc "{xxx.iss}" 进行编译
; 安装程序生成在该脚本的根目录下的Output目录下 
; 程序名称
#define MyAppName "Metasweeper"
; 程序版本
#define MyAppVersion "3.3.4"
; 发行商
#define MyAppPublisher "eee555"
; 官网
#define MyAppURL "https://github.com/eee555/Metasweeper"
; 运行主程序名称
#define MyAppExeName "metasweeper.exe"
; 程序目录
#define AppPath "metasweeper"
; 根目录
#define RootPath "Metasweeper-snapshot"
; 图标
#define IconPath "metasweeper\_internal\media\cat.ico"
[Setup]
;注意：AppId 的值唯一标识此应用程序。不要在其他应用程序的安装程序中使用相同的 AppId 值。
;（要生成新的 GUID，请单击 Tools |在 IDE 中生成 GUID
AppId={{A5BFCE55-30E5-4A1D-8849-E6372D2CF9D4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
;AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
;默认按照路径
DefaultDirName={autopf}\{#MyAppName}
;“ArchitecturesAllowed=x64compatible” 指定安装程序无法运行
;在 Arm 上的 x64 和 Windows 11 以外的任何设备上。
ArchitecturesAllowed=x64compatible
;“ArchitecturesInstallIn64BitMode=x64compatible” 请求
;在 x64 或 Arm 上的 Windows 11 上以“64 位模式”完成安装，
;这意味着它应该使用本机 64 位 Program Files 目录和
;注册表的 64 位视图。
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DisableDirPage=no
;取消注释以下行以在非管理安装模式下运行（仅为当前用户安装）。
PrivilegesRequired=admin
OutputBaseFilename=Metasweeper-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#RootPath}\{#IconPath}
UninstallDisplayIcon={app}\{#IconPath}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[CustomMessages]
english.FileAssocPageTitle=File Association
english.FileAssocPageDesc=Select file types to associate with %1, then click Next.

chinese.FileAssocPageTitle=文件打开方式
chinese.FileAssocPageDesc=勾选对应的文件类型，以添加对应文件类型使用%1的打开方式，然后点击"下一步"按钮。

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkablealone

[InstallDelete]
Type: filesandordirs; Name: "{app}\{#AppPath}\_internal\plugins\history"
Type: filesandordirs; Name: "{app}\{#AppPath}\_internal\plugins\clipboard_replay"
Type: filesandordirs; Name: "{app}\{#AppPath}\_internal\plugins\llm_minesweeper_controller"

[Files]
Source: {#RootPath}\{#AppPath}\{#MyAppExeName}; DestDir: "{app}\{#AppPath}"; Flags: ignoreversion
Source: {#RootPath}\*; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
;注意：不要在任何共享系统文件上使用 “Flags： ignoreversion”

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#AppPath}\{#MyAppExeName}";
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#AppPath}\{#MyAppExeName}"; Tasks: desktopicon;

[Run]
Filename: "{app}\{#AppPath}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runascurrentuser
[Code]
var
    Page: TWizardPage;
    AVFCheckbox, EVFCheckbox, RMVCheckbox, MVFCheckbox, EVFSCheckbox: TNewCheckbox;
procedure FileAssociationPage;
begin
    Page := CreateCustomPage(wpSelectDir, CustomMessage('FileAssocPageTitle'), FmtMessage(CustomMessage('FileAssocPageDesc'), ['{#MyAppName}']));

    AVFCheckbox := TNewCheckbox.Create(Page);
    AVFCheckbox.Top := 0;
    AVFCheckbox.Left := 0;
    AVFCheckbox.Width := Page.SurfaceWidth;
    AVFCheckbox.Caption := '.avf';
    AVFCheckbox.Checked := False;
    AVFCheckbox.Parent := Page.Surface;

    EVFCheckbox := TNewCheckbox.Create(Page);
    EVFCheckbox.Top := 20;
    EVFCheckbox.Left := 0;
    EVFCheckbox.Width := Page.SurfaceWidth;
    EVFCheckbox.Caption := '.evf';
    EVFCheckbox.Checked := False;
    EVFCheckbox.Parent := Page.Surface;

    RMVCheckbox := TNewCheckbox.Create(Page);
    RMVCheckbox.Top := 40;
    RMVCheckbox.Left := 0;
    RMVCheckbox.Width := Page.SurfaceWidth;
    RMVCheckbox.Caption := '.rmv';
    RMVCheckbox.Checked := False;
    RMVCheckbox.Parent := Page.Surface;

    MVFCheckbox := TNewCheckbox.Create(Page);
    MVFCheckbox.Top := 60;
    MVFCheckbox.Left := 0;
    MVFCheckbox.Width := Page.SurfaceWidth;
    MVFCheckbox.Caption := '.mvf';
    MVFCheckbox.Checked := False;
    MVFCheckbox.Parent := Page.Surface;
    
    EVFSCheckbox := TNewCheckbox.Create(Page);
    EVFSCheckbox.Top := 80;
    EVFSCheckbox.Left := 0;
    EVFSCheckbox.Width := Page.SurfaceWidth;
    EVFSCheckbox.Caption := '.evfs';
    EVFSCheckbox.Checked := False;
    EVFSCheckbox.Parent := Page.Surface;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
    if CurStep = ssPostInstall then
    begin
        if not (AVFCheckbox.Checked or EVFCheckbox.Checked or RMVCheckbox.Checked or MVFCheckbox.Checked or EVFSCheckbox.Checked) then
        begin
            RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}');
        end;

        if AVFCheckbox.Checked then
        begin
            RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}', '','{#MyAppName}');
            RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}', 'FriendlyAppName', '{#MyAppName}');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '.avf\OpenWithProgids', '', '{#MyAppName}.avf');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '.avf', '','{#MyAppName}.avf');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '{#MyAppName}.avf\DefaultIcon', '', ExpandConstant('{app}\media\AVF.ico,0'));
            RegWriteStringValue(HKEY_CLASSES_ROOT, '{#MyAppName}.avf\shell\open\command', '', ExpandConstant('"' + ExpandConstant('{app}\{#AppPath}\{#MyAppExeName}') + '" "%1"'));
        end
        else
        begin
            RegDeleteValue(HKEY_CLASSES_ROOT, '.avf\OpenWithProgids', '');
            RegDeleteValue(HKEY_CLASSES_ROOT, '.avf', '');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.avf\shell\open\command');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.avf\DefaultIcon');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.avf');
        end;

        if EVFCheckbox.Checked then
        begin
            RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}', '','{#MyAppName}');
            RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}', 'FriendlyAppName', '{#MyAppName}');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '.evf\OpenWithProgids', '', '{#MyAppName}.evf');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '.evf', '','{#MyAppName}.evf');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '{#MyAppName}.evf\DefaultIcon', '', ExpandConstant('{app}\media\EVF.ico,0'));
            RegWriteStringValue(HKEY_CLASSES_ROOT, '{#MyAppName}.evf\shell\open\command', '', ExpandConstant('"' + ExpandConstant('{app}\{#AppPath}\{#MyAppExeName}') + '" "%1"'));
        end
        else
        begin
            RegDeleteValue(HKEY_CLASSES_ROOT, '.evf\OpenWithProgids', '');
            RegDeleteValue(HKEY_CLASSES_ROOT, '.evf', '');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evf\shell\open\command');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evf\DefaultIcon');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evf');
        end;

        if RMVCheckbox.Checked then
        begin
            RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}', '','{#MyAppName}');
            RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}', 'FriendlyAppName', '{#MyAppName}');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '.rmv\OpenWithProgids', '', '{#MyAppName}.rmv');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '.rmv', '','{#MyAppName}.rmv');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '{#MyAppName}.rmv\DefaultIcon', '', ExpandConstant('{app}\media\RMV.ico,0'));
            RegWriteStringValue(HKEY_CLASSES_ROOT, '{#MyAppName}.rmv\shell\open\command', '', ExpandConstant('"' + ExpandConstant('{app}\{#AppPath}\{#MyAppExeName}') + '" "%1"'));
        end
        else
        begin
            RegDeleteValue(HKEY_CLASSES_ROOT, '.rmv\OpenWithProgids', '');
            RegDeleteValue(HKEY_CLASSES_ROOT, '.rmv', '');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.rmv\shell\open\command');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.rmv\DefaultIcon');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.rmv');
        end;

        if MVFCheckbox.Checked then
        begin
            RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}', '','{#MyAppName}');
            RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}', 'FriendlyAppName', '{#MyAppName}');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '.mvf\OpenWithProgids', '', '{#MyAppName}.rmv');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '.mvf', '','{#MyAppName}.mvf');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '{#MyAppName}.mvf\DefaultIcon', '', ExpandConstant('{app}\media\MVF.ico,0'));
            RegWriteStringValue(HKEY_CLASSES_ROOT, '{#MyAppName}.mvf\shell\open\command', '', ExpandConstant('"' + ExpandConstant('{app}\{#AppPath}\{#MyAppExeName}') + '" "%1"'));
        end
        else
        begin
            RegDeleteValue(HKEY_CLASSES_ROOT, '.mvf\OpenWithProgids', '');
            RegDeleteValue(HKEY_CLASSES_ROOT, '.mvf', '');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.mvf\shell\open\command');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.mvf\DefaultIcon');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.mvf');       
        end;
        
        if EVFSCheckbox.Checked then
        begin
            RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}', '','{#MyAppName}');
            RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}', 'FriendlyAppName', '{#MyAppName}');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '.evfs\OpenWithProgids', '', '{#MyAppName}.evfs');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '.evfs', '','{#MyAppName}.evfs');
            RegWriteStringValue(HKEY_CLASSES_ROOT, '{#MyAppName}.evfs\DefaultIcon', '', ExpandConstant('{app}\media\EVF.ico,0'));
            RegWriteStringValue(HKEY_CLASSES_ROOT, '{#MyAppName}.evfs\shell\open\command', '', ExpandConstant('"' + ExpandConstant('{app}\{#AppPath}\{#MyAppExeName}') + '" "%1"'));
        end
        else
        begin
            RegDeleteValue(HKEY_CLASSES_ROOT, '.evfs\OpenWithProgids', '');
            RegDeleteValue(HKEY_CLASSES_ROOT, '.evfs', '');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evfs\shell\open\command');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evfs\DefaultIcon');
            RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evfs');
        end;
    end;
end;
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
    if CurUninstallStep = usPostUninstall then
    begin
        RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, 'SOFTWARE\Classes\Applications\{#MyAppExeName}');

        RegDeleteValue(HKEY_CLASSES_ROOT, '.avf\OpenWithProgids', '');
        RegDeleteValue(HKEY_CLASSES_ROOT, '.avf', '');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.avf\shell\open\command');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.avf\DefaultIcon');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.avf');

        RegDeleteValue(HKEY_CLASSES_ROOT, '.evf\OpenWithProgids', '');
        RegDeleteValue(HKEY_CLASSES_ROOT, '.evf', '');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evf\shell\open\command');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evf\DefaultIcon');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evf');

        RegDeleteValue(HKEY_CLASSES_ROOT, '.rmv\OpenWithProgids', '');
        RegDeleteValue(HKEY_CLASSES_ROOT, '.rmv', '');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.rmv\shell\open\command');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.rmv\DefaultIcon');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.rmv');

        RegDeleteValue(HKEY_CLASSES_ROOT, '.mvf\OpenWithProgids', '');
        RegDeleteValue(HKEY_CLASSES_ROOT, '.mvf', '');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.mvf\shell\open\command');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.mvf\DefaultIcon');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.mvf');
        
        RegDeleteValue(HKEY_CLASSES_ROOT, '.evfs\OpenWithProgids', '');
        RegDeleteValue(HKEY_CLASSES_ROOT, '.evfs', '');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evfs\shell\open\command');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evfs\DefaultIcon');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, '{#MyAppName}.evfs');

    end;
end;
procedure InitializeWizard;
begin
    FileAssociationPage;
end;
