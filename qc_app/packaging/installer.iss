; Установщик Windows (Inno Setup 6). Сборка: iscc /DAppVersion=1.0.0 packaging\installer.iss
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Контроль качества анкет"
#define AppExe "AnketaQC.exe"

[Setup]
AppId={{6E1B7C52-3F0A-4C8E-9D2B-5A7F41C3E9D1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=AnketaQC
DefaultDirName={localappdata}\Programs\AnketaQC
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Установка без прав администратора — в профиль пользователя
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=AnketaQC-Setup-{#AppVersion}
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"

[Files]
Source: "..\dist\AnketaQC\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Запустить {#AppName}"; Flags: nowait postinstall skipifsilent
