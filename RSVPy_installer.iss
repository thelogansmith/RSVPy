; ============================================================
;  RSVPy Installer — Inno Setup Script
;
;  Open this file in Inno Setup Compiler and click
;  Build > Compile (or Ctrl+F9).
;
;  Expects the PyInstaller output at dist\RSVPy\ relative to
;  this file. Run PyInstaller first (see guide).
;
;  Output: Output\Setup_RSVPy_0.1.0-beta.exe
; ============================================================

#define MyAppName "RSVPy"
#define MyAppVersion "0.1.0-beta"
#define MyAppPublisher "thelogansmith"
#define MyAppURL "https://github.com/thelogansmith/RSVPy"
#define MyAppExeName "RSVPy.exe"

[Setup]
AppId={{7A3F8E2C-B4D1-4F6A-9E5C-1D2A3B4C5D6E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=Output
OutputBaseFilename=Setup_{#MyAppName}_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayName={#MyAppName}
ArchitecturesInstallIn64BitMode=x64compatible
; Uncomment if you add an icon file:
; SetupIconFile=icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenu"; Description: "Create a Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "dist\RSVPy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenu
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; Tasks: startmenu
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
