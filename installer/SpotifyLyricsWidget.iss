#define MyAppName "Spotify Lyrics Widget"
#define MyAppVersion "3.2.2"
#define MyAppPublisher "Spotify Lyrics Widget"
#define MyAppExeName "SpotifyLyricsWidget.exe"

[Setup]
AppId={{C9A481B4-A950-4B2A-8B41-7C297C3D6F64}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=SpotifyLyricsWidgetSetup
SetupIconFile=..\assets\app-icon.ico
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Dirs]
Name: "{userappdata}\spotify-lyrics-widget"

[Files]
Source: "..\dist\SpotifyLyricsWidget\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{sysnative}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden nowait skipifdoesntexist
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  LanguagePage: TInputOptionWizardPage;

function SelectedAppLanguage: String;
begin
  if LanguagePage.Values[1] then
    Result := 'zh_TW'
  else
    Result := 'english';
end;

procedure InitializeWizard;
begin
  LanguagePage := CreateInputOptionPage(
    wpWelcome,
    'Language / 語言',
    'Choose first setup language / 選擇首次設定語言',
    'This controls the Spotify Client ID setup window after installation.',
    True,
    False
  );
  LanguagePage.Add('English');
  LanguagePage.Add('繁體中文');
  LanguagePage.Values[0] := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    ForceDirectories(ExpandConstant('{userappdata}\spotify-lyrics-widget'));
    SetIniString(
      'Install',
      'Language',
      SelectedAppLanguage,
      ExpandConstant('{userappdata}\spotify-lyrics-widget\install.ini')
    );
  end;
end;
