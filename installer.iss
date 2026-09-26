; Inno Setup script per RiotAccountsManager By Gabry
; Per buildare: apri questo file con Inno Setup Compiler e clicca Compila
; Download Inno Setup: https://jrsoftware.org/isdl.php
;
; PREREQUISITO: buildare prima il .exe con PyInstaller:
;   pyinstaller RiotAccountsManager.spec
; I file saranno in dist\RiotAccountsManager By Gabry\

#define AppName "RiotAccountsManager By Gabry"
#define AppVersion "0.0.1"
#define AppPublisher "Gabry"
#define AppURL "https://github.com/Gabryhh/League-Of-Legends-Cred-Manager-"
#define AppExeName "RiotAccountsManager By Gabry.exe"
#define SourceDir "dist\RiotAccountsManager By Gabry"

[Setup]
AppId={{A3F7B2C1-D4E5-4F6A-B7C8-D9E0F1A2B3C4}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
LicenseFile=
OutputDir=installer_output
OutputBaseFilename=RiotAccountsManager_Setup_v{#AppVersion}
SetupIconFile=info\ico\256x256.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardResizable=no
UninstallDisplayIcon={app}\{#AppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul Desktop"; GroupDescription: "Icone aggiuntive:"

[Files]
; Tutti i file buildati da PyInstaller
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Collegamento nel menu Start
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\info\ico\256x256.ico"
; Collegamento sul desktop (opzionale, abilitato di default)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\info\ico\256x256.ico"; Tasks: desktopicon
; Voce disinstalla nel menu Start
Name: "{group}\Disinstalla {#AppName}"; Filename: "{uninstallexe}"

[Run]
; Avvia l'app dopo l'installazione
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Rimuove i file creati dall'app (config, dati cifrati, chiave)
; ATTENZIONE: questo elimina anche gli account salvati. Commentare le righe
; sottostanti se si vuole mantenere i dati dopo la disinstallazione.
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\accounts.enc"
Type: files; Name: "{app}\key.key"
