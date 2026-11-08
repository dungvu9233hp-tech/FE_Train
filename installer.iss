[Setup]
AppName=FE Vocab Trainer
AppVersion=1.0
AppPublisher=FE Vocab
DefaultDirName={autopf}\FE Vocab Trainer
DefaultGroupName=FE Vocab Trainer
OutputDir=installer
OutputBaseFilename=FE_Vocab_Trainer_Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\FE_Vocab_Trainer.exe
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\FE_Vocab_Trainer.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\FE Vocab Trainer"; Filename: "{app}\FE_Vocab_Trainer.exe"
Name: "{autodesktop}\FE Vocab Trainer"; Filename: "{app}\FE_Vocab_Trainer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FE_Vocab_Trainer.exe"; Description: "Launch FE Vocab Trainer"; Flags: nowait postinstall skipifsilent
