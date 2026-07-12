;由 Inno Setup Script Wizard 生成的脚本。
;有关创建 INNO SETUP 脚本文件的详细信息，请参阅文档
; 将Inno Setup 的安装目录添加到环境变量中 在命令行使用 ISCC "{xxx.iss}" 全路径 进行编译
; 或者 cd 到Inno Setup 的安装目录，然后在命令行中使用 iscc "{xxx.iss}" 进行编译
; 安装程序生成在该脚本的根目录下的Output目录下 
; 程序名称
#define MyAppName "Metasweeper"
; 程序版本
#define MyAppVersion "3.3.2"
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

english.UninstallKeepDataMsg=Do you want to keep your personal data?%n%nGame settings, replays, and game data will be preserved.%n%nYes - Keep my data%nNo  - Delete everything

chinese.UninstallKeepDataMsg=是否保留您的个人数据？%n%n游戏配置、录像和数据将被保留。%n%n是 - 保留我的数据%n否 - 全部删除

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkablealone

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
    KeepUserData: Boolean;

function InitializeUninstall: Boolean;
begin
    Result := True;
    KeepUserData := MsgBox(CustomMessage('UninstallKeepDataMsg'), mbConfirmation, MB_YESNO) = IDYES;
end;
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

procedure SaveAndWipe(AppDir: string);
var
    BackupDir, ScriptPath: string;
    ResultCode: Integer;
    RoboFlags: string;
begin
    BackupDir := ExpandConstant('{tmp}') + '\MS_Backup';
    ScriptPath := ExpandConstant('{tmp}') + '\MS_Uninstall.ps1';
    RoboFlags := '/NDL /NFL /NJH /NJS';

    SaveStringToFile(ScriptPath,
        '$src = ''' + AppDir + ''';'#13#10 +
        '$dst = ''' + BackupDir + ''';'#13#10 +
        '# check if personal data exists inside app dir'#13#10 +
        '$appExeDir = "$src\' + '{#AppPath}"'#13#10 +
        '$hasData = (Test-Path "$appExeDir\gameSetting.ini") -or ' + 
            '(Test-Path "$appExeDir\replay")'#13#10 +
        'if (-not $hasData) {'#13#10 +
        '    Remove-Item $src -Recurse -Force; exit }'#13#10 +
        '# backup personal files'#13#10 +
        'if (Test-Path $dst) { Remove-Item $dst -Recurse -Force };'#13#10 +
        'New-Item $dst -ItemType Directory -Force | Out-Null;'#13#10 +
        'New-Item "$dst\' + '{#AppPath}" -ItemType Directory -Force | Out-Null;'#13#10 +
        'foreach ($f in @("gameSetting.ini","record.ini","scoreBoardSetting.ini")) {'#13#10 +
        '    $fp = "$appExeDir\$f"'#13#10 +
        '    if (Test-Path $fp) { Copy-Item $fp "$dst\' + '{#AppPath}\$f" -Force }'#13#10 +
        '};'#13#10 +
        'if (Test-Path "$appExeDir\replay") { ' +
            'robocopy "$appExeDir\replay" "$dst\' + '{#AppPath}\replay" ' + RoboFlags + ' /E };'#13#10 +
        'if (Test-Path "$appExeDir\data") { ' +
            'robocopy "$appExeDir\data" "$dst\' + '{#AppPath}\data" ' + RoboFlags + ' /E };'#13#10 +
        '# wipe app dir, then restore'#13#10 +
        'Remove-Item $src -Recurse -Force;'#13#10 +
        'New-Item $src -ItemType Directory -Force | Out-Null;'#13#10 +
        'robocopy $dst $src ' + RoboFlags + ' /E;'#13#10 +
        'Remove-Item $dst -Recurse -Force',
        False);
    Exec('powershell.exe', '-ExecutionPolicy Bypass -File "' + ScriptPath + '"', '',
        SW_HIDE, ewWaitUntilTerminated, ResultCode);
    DeleteFile(ScriptPath);
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

        if KeepUserData then
        begin
            SaveAndWipe(ExpandConstant('{app}'));
        end
        else
        begin
            DelTree('\\?\' + ExpandConstant('{app}'), True, True, True);
        end;
    end;
end;
procedure InitializeWizard;
begin
    FileAssociationPage;
end;
