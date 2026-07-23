#ifndef AppVersion
  #define AppVersion "0.9.0-beta.1"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\SmartFile"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\release\windows"
#endif

#define AppName "SmartFile"
#define AppPublisher "SmartFile contributors"
#define AppExeName "SmartFile.exe"

[Setup]
AppId={{D9B3B0D8-4D8A-4FC3-A6A3-7E2A46CCBCA1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\SmartFile
DefaultGroupName=SmartFile
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
SetupIconFile=..\..\assets\icons\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir={#OutputDir}
OutputBaseFilename=SmartFile-{#AppVersion}-Windows-x64-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=no
ChangesEnvironment=no
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=0.9.0.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Instalador beta do SmartFile
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SmartFile"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\SmartFile"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Iniciar o SmartFile"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
