; Inno Setup script for Container Damage Detection.
; Compile with: ISCC.exe installer.iss /DDistDir="<path to PyInstaller onedir output>" /DOutputDir="<path>"
;
; Installs per-user (no admin rights required) so it works on machines
; where the end user isn't a local administrator.

#ifndef DistDir
  #define DistDir "C:\cdd_build\dist\ContainerDamageDetection"
#endif
#ifndef OutputDir
  #define OutputDir "D:\FreeLancer\Container_detect_damage\installer_output"
#endif

[Setup]
AppId={{B7B7C6F0-6C1B-4B1E-9C3D-2F1E2C7D6A11}}
AppName=Container Damage Detection
AppVersion=1.0.0
AppPublisher=ICT Software
DefaultDirName={localappdata}\Programs\ContainerDamageDetection
DefaultGroupName=Container Damage Detection
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=ContainerDamageDetection-Setup
; Using fast zip instead of solid lzma2: two prior lzma2 compiles (each
; ~38 min) silently dropped thousands of files (including the model
; weights!) from the output, almost certainly due to Windows Defender
; real-time scanning locking source files mid-read during the long
; compression window. A much shorter compile reduces that exposure.
Compression=zip
SolidCompression=no
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo shortcut ngoài Desktop"; GroupDescription: "Shortcut bổ sung:"

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Container Damage Detection"; Filename: "{app}\ContainerDamageDetection.exe"
Name: "{group}\Gỡ cài đặt"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Container Damage Detection"; Filename: "{app}\ContainerDamageDetection.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ContainerDamageDetection.exe"; Description: "Khởi chạy Container Damage Detection"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\ContainerDamageDetection"
