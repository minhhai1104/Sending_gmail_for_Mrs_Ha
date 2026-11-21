; Bộ cài đặt 1-Click (Per-User, Không cần quyền Admin) cho Gmail Auto Mailer v3.0 — Haesung Vina
; Biên dịch bằng Inno Setup 6: iscc /DAppVersion=3.0.0 /DSourceDir=... /DOutputDir=... installer\setup.iss

#ifndef AppVersion
  #define AppVersion "3.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\Ban_phat_hanh\App"
#endif
#ifndef OutputDir
  #define OutputDir "..\Ban_phat_hanh"
#endif

[Setup]
AppId={{7E8E6D2F-92B4-4F91-A72E-52C0D94B8012}
AppName=Gmail Auto Mailer — Haesung Vina
AppVersion={#AppVersion}
AppVerName=Gmail Auto Mailer v{#AppVersion}
AppPublisher=Haesung Vina Co., Ltd.
AppPublisherURL=https://github.com/minhhai1104/Sending_gmail_for_Mrs_Ha
DefaultDirName={localappdata}\Programs\HaesungVina\GmailAutoMailer
DefaultGroupName=Gmail Auto Mailer (Haesung Vina)
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
DisableWelcomePage=yes
UsePreviousAppDir=yes
CloseApplications=yes
CloseApplicationsFilter=Gui_mail_nha_cung_cap.exe
RestartApplications=no
SetupIconFile=..\assets\app_icon.ico
UninstallDisplayIcon={app}\Gui_mail_nha_cung_cap.exe
UninstallDisplayName=Gmail Auto Mailer — Haesung Vina
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
OutputDir={#OutputDir}
OutputBaseFilename=Cai_dat_Gui_mail_Haesung_Vina_v{#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài màn hình chính (Desktop)"; GroupDescription: "Tiện ích:"; Flags: checkablealone

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Gmail Auto Mailer"; Filename: "{app}\Gui_mail_nha_cung_cap.exe"; IconFilename: "{app}\Gui_mail_nha_cung_cap.exe"
Name: "{group}\Gỡ cài đặt Gmail Auto Mailer"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Gmail Auto Mailer"; Filename: "{app}\Gui_mail_nha_cung_cap.exe"; IconFilename: "{app}\Gui_mail_nha_cung_cap.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Gui_mail_nha_cung_cap.exe"; Description: "Mở Gmail Auto Mailer ngay bây giờ"; Flags: nowait postinstall skipifsilent

[Code]
function IsWebView2Installed(): Boolean;
var
  pv: String;
begin
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', pv) and (pv <> '')) or
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', pv) and (pv <> '')) or
    (RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', pv) and (pv <> ''));
end;

function InitializeSetup(): Boolean;
var
  ErrCode: Integer;
begin
  Result := True;
  if not IsWebView2Installed() then
  begin
    if MsgBox(
      'Máy tính chưa có Microsoft Edge WebView2 Runtime (thành phần giao diện chuẩn của Windows 10/11).' + #13#10 +
      'Bạn có muốn mở trang tải chính thức của Microsoft ngay bây giờ không?' + #13#10 +
      '(Bấm No để vẫn tiếp tục cài đặt ứng dụng)',
      mbConfirmation, MB_YESNO
    ) = IDYES then
    begin
      ShellExec('open', 'https://developer.microsoft.com/en-us/microsoft-edge/webview2/', '', '', SW_SHOWNORMAL, ewNoWait, ErrCode);
    end;
  end;
end;
