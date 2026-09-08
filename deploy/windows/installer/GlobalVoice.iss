#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName "Global Voice"
#define AppExecutable "GlobalVoice.exe"

[Setup]
AppId={{EC382E2B-432A-4978-9C6D-E923EDEF7711}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Global Voice
AppPublisherURL=https://github.com/GlobalVoice-Uni/GlobalVoice-Desktop
AppSupportURL=https://github.com/GlobalVoice-Uni/GlobalVoice-Desktop/issues
AppUpdatesURL=https://github.com/GlobalVoice-Uni/GlobalVoice-Desktop/releases
DefaultDirName={autopf}\Global Voice
DefaultGroupName=Global Voice
DisableProgramGroupPage=auto
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible and not arm64
ArchitecturesInstallIn64BitMode=x64compatible and not arm64
MinVersion=10.0
OutputDir=..\..\..\dist\installer
OutputBaseFilename=GlobalVoice-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
UninstallDisplayIcon={app}\{#AppExecutable}
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}
VersionInfoCompany=Global Voice
VersionInfoDescription=Instalador do Global Voice
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "automatic"; Description: "Instalação recomendada"
Name: "custom"; Description: "Instalação personalizada"; Flags: iscustom

[Components]
Name: "base"; Description: "Aplicação e processamento por CPU (AMD, Intel ou fallback)"; Types: automatic custom; Flags: fixed
Name: "nvidia"; Description: "Aceleração para GPU NVIDIA (CUDA 12/cuBLAS)"; Types: automatic

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\..\dist\GlobalVoice\*"; DestDir: "{app}"; Excludes: "_internal\runtime\nvidia\cuda12\*"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: base
Source: "..\..\..\dist\runtime-profiles\nvidia-cuda12\*"; DestDir: "{app}\_internal\runtime\nvidia\cuda12"; Flags: ignoreversion; Components: nvidia

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal\runtime\nvidia\cuda12"

[Icons]
Name: "{group}\Global Voice"; Filename: "{app}\{#AppExecutable}"
Name: "{autodesktop}\Global Voice"; Filename: "{app}\{#AppExecutable}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExecutable}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
const
  DisplayAdapterClassGuid = '{4D36E968-E325-11CE-BFC1-08002BE10318}';
  PciRegistryPath = 'SYSTEM\CurrentControlSet\Enum\PCI';
  NvidiaVendorId = 'VEN_10DE';

var
  NvidiaDetected: Boolean;

function HasNvidiaDisplayAdapter: Boolean;
var
  DeviceKeys: TArrayOfString;
  InstanceKeys: TArrayOfString;
  DeviceIndex: Integer;
  InstanceIndex: Integer;
  DevicePath: String;
  InstancePath: String;
  ClassGuid: String;
begin
  Result := False;
  if not RegGetSubkeyNames(HKLM, PciRegistryPath, DeviceKeys) then
  begin
    Log('Não foi possível consultar os dispositivos PCI.');
    Exit;
  end;

  for DeviceIndex := 0 to GetArrayLength(DeviceKeys) - 1 do
  begin
    if Pos(NvidiaVendorId, Uppercase(DeviceKeys[DeviceIndex])) = 0 then
      Continue;

    DevicePath := PciRegistryPath + '\' + DeviceKeys[DeviceIndex];
    if not RegGetSubkeyNames(HKLM, DevicePath, InstanceKeys) then
      Continue;

    for InstanceIndex := 0 to GetArrayLength(InstanceKeys) - 1 do
    begin
      InstancePath := DevicePath + '\' + InstanceKeys[InstanceIndex];
      if RegQueryStringValue(HKLM, InstancePath, 'ClassGUID', ClassGuid) and
         (CompareText(ClassGuid, DisplayAdapterClassGuid) = 0) then
      begin
        Log('Adaptador de vídeo NVIDIA detectado em ' + InstancePath + '.');
        Result := True;
        Exit;
      end;
    end;
  end;

  Log('Nenhum adaptador de vídeo NVIDIA foi detectado.');
end;

procedure InitializeWizard;
begin
  if ExpandConstant('{param:COMPONENTS|}') <> '' then
  begin
    Log('Seleção de componentes recebida pela linha de comando.');
    Exit;
  end;

  NvidiaDetected := HasNvidiaDisplayAdapter;
  if NvidiaDetected then
    WizardSelectComponents('base,nvidia')
  else
    WizardSelectComponents('base,!nvidia');
end;
