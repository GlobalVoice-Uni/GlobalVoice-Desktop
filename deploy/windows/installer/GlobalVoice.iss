#ifndef AppVersion
  #define AppVersion "0.4.1"
#endif
#ifndef AppFileVersion
  #define AppFileVersion "0.4.1.0"
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
UninstallDisplayIcon={app}\GlobalVoice-{#AppVersion}.ico
SetupIconFile=..\..\..\frontend\assets\newicon.ico
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppFileVersion}
VersionInfoCompany=Global Voice
VersionInfoDescription=Instalador do Global Voice
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
brazilianportuguese.FinishedRestartLabel=O microfone virtual VB-CABLE foi instalado. Reinicie o computador para usá-lo no Global Voice.
brazilianportuguese.FinishedRestartMessage=O microfone virtual VB-CABLE foi instalado. Reinicie o computador para usá-lo no Global Voice.%n%nDeseja reiniciar agora?
brazilianportuguese.YesRadio=&Reiniciar agora
brazilianportuguese.NoRadio=Reiniciar &depois
english.FinishedRestartLabel=The VB-CABLE virtual microphone is installed. Restart your computer before using it with Global Voice.
english.FinishedRestartMessage=The VB-CABLE virtual microphone is installed. Restart your computer before using it with Global Voice.%n%nRestart now?
english.YesRadio=&Restart now
english.NoRadio=Restart &later

[Types]
Name: "automatic"; Description: "Instalação recomendada"
Name: "custom"; Description: "Instalação personalizada"; Flags: iscustom

[Components]
Name: "base"; Description: "Aplicação e processamento por CPU (AMD, Intel ou fallback)"; Types: automatic custom; Flags: fixed
Name: "nvidia"; Description: "Aceleração para GPU NVIDIA (CUDA 12/cuBLAS)"; Types: automatic
Name: "cable"; Description: "VB-CABLE (Microfone Virtual para Voz Sintetizada)"; Types: automatic custom

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\..\frontend\assets\newicon.ico"; DestDir: "{app}"; DestName: "GlobalVoice-{#AppVersion}.ico"; Flags: ignoreversion; Components: base
Source: "..\..\..\dist\GlobalVoice\*"; DestDir: "{app}"; Excludes: "_internal\runtime\nvidia\cuda12\*"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: base
Source: "..\..\..\dist\runtime-profiles\nvidia-cuda12\*"; DestDir: "{app}\_internal\runtime\nvidia\cuda12"; Flags: ignoreversion; Components: nvidia
Source: "..\..\..\.build\VBCABLE_Driver_Pack45\*"; DestDir: "{app}\drivers\VB-CABLE"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: cable

[INI]
Filename: "{app}\installation.ini"; Section: "Language"; Key: "Base"; String: "{code:GetBaseLanguage}"
Filename: "{app}\installation.ini"; Section: "App"; Key: "Version"; String: "{#AppVersion}"
Filename: "{app}\installation.ini"; Section: "App"; Key: "InstallId"; String: "{code:GetInstallId}"
Filename: "{app}\installation.ini"; Section: "Language"; Key: "Pairs"; String: "{code:GetSelectedPacks}"

[UninstallDelete]
Type: files; Name: "{app}\installation.ini"

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal\runtime\nvidia\cuda12"

[Icons]
Name: "{group}\Global Voice"; Filename: "{app}\{#AppExecutable}"; IconFilename: "{app}\GlobalVoice-{#AppVersion}.ico"
Name: "{autodesktop}\Global Voice"; Filename: "{app}\{#AppExecutable}"; IconFilename: "{app}\GlobalVoice-{#AppVersion}.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExecutable}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runasoriginaluser; Check: CanLaunchAfterSetup

[Code]
const
  DisplayAdapterClassGuid = '{4D36E968-E325-11CE-BFC1-08002BE10318}';
  PciRegistryPath = 'SYSTEM\CurrentControlSet\Enum\PCI';
  NvidiaVendorId = 'VEN_10DE';

var
  NvidiaDetected: Boolean;
  LanguagePage: TWizardPage;
  BasePtRadio: TNewRadioButton;
  BaseEnRadio: TNewRadioButton;
  BaseEsRadio: TNewRadioButton;
  FirstPairCheck: TNewCheckBox;
  SecondPairCheck: TNewCheckBox;
  DownloadPage: TDownloadWizardPage;
  DownloadPairsLabel: TNewStaticText;
  DownloadErrorLabel: TNewStaticText;
  InstallPage: TOutputMarqueeProgressWizardPage;
  CablePage: TOutputMarqueeProgressWizardPage;
  LastPairBase: String;
  VBCableInstalledBySetup: Boolean;
  RemoveVBCableOnUninstall: Boolean;
  VBCableRemovedByUninstall: Boolean;
  InstallFailureMessage: String;
  InstallId: String;

function GetInstallId(Param: String): String;
begin
  if InstallId = '' then
    InstallId := GetDateTimeString('yyyymmddhhnnss', '-', ':');
  Result := InstallId;
end;

function IsVBCableInstalled: Boolean;
var
  DeviceCount: Cardinal;
begin
  { A chave do serviço pode sobreviver à desinstalação. O Enum só contém
    instâncias do dispositivo que ainda estão registradas no Windows. }
  Result := RegQueryDWordValue(HKLM,
    'SYSTEM\CurrentControlSet\Services\VBAudioVACMME\Enum',
    'Count', DeviceCount) and (DeviceCount > 0);
end;

function ShouldInstallVBCable: Boolean;
begin
  Result := not IsVBCableInstalled;
end;

function NeedRestart: Boolean;
begin
  Result := VBCableInstalledBySetup;
end;

function CanLaunchAfterSetup: Boolean;
begin
  Result := (not VBCableInstalledBySetup) and (InstallFailureMessage = '');
end;

function GetCustomSetupExitCode: Integer;
begin
  if InstallFailureMessage <> '' then
    Result := 4
  else
    Result := 0;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and (InstallFailureMessage <> '') then
  begin
    WizardForm.FinishedHeadingLabel.Caption := 'A instalação precisa de atenção';
    WizardForm.FinishedLabel.Caption := InstallFailureMessage;
  end;
end;

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

function GetBaseLanguage(Param: String): String;
begin
  if BaseEnRadio.Checked then Result := 'en'
  else if BaseEsRadio.Checked then Result := 'es'
  else Result := 'pt-br';
end;

function PairCode(Index: Integer): String;
var
  Base: String;
begin
  Base := GetBaseLanguage('');
  if Base = 'pt-br' then
  begin
    if Index = 0 then Result := 'en' else Result := 'es';
  end
  else if Base = 'en' then
  begin
    if Index = 0 then Result := 'en' else Result := 'en-es';
  end
  else
  begin
    if Index = 0 then Result := 'es' else Result := 'en-es';
  end;
end;

function IsPackSelected(Code: String): Boolean;
var
  Requested: String;
  Index: Integer;
begin
  Requested := Lowercase(ExpandConstant('{param:PAIRS|}'));
  if Requested <> '' then
  begin
    Result := Pos(',' + Code + ',', ',' + Requested + ',') > 0;
    Exit;
  end;
  Result := False;
  for Index := 0 to 1 do
    if (PairCode(Index) = Code) and
      (((Index = 0) and FirstPairCheck.Checked) or
       ((Index = 1) and SecondPairCheck.Checked)) then
      Result := True;
end;

function GetSelectedPacks(Param: String): String;
var
  Index: Integer;
  Code: String;
begin
  Result := '';
  for Index := 0 to 1 do
  begin
    Code := PairCode(Index);
    if IsPackSelected(Code) then
    begin
      if Result <> '' then Result := Result + ',';
      Result := Result + Code;
    end;
  end;
end;

function GetTranslationRoot: String;
begin
  if IsAdminInstallMode then
    Result := ExpandConstant('{commonappdata}\GlobalVoice\translation')
  else
    Result := ExpandConstant('{localappdata}\GlobalVoice\translation');
end;

procedure UpdatePairChoices;
var
  Base: String;
  Code: String;
begin
  Base := GetBaseLanguage('');
  if Base = 'pt-br' then
    FirstPairCheck.Caption := 'Inglês ↔ Português — 129,34 MiB'
  else if Base = 'en' then
    FirstPairCheck.Caption := 'Português ↔ Inglês — 129,34 MiB'
  else
    FirstPairCheck.Caption := 'Português ↔ Espanhol — 128,76 MiB';

  Code := PairCode(1);
  if Code = 'es' then
    SecondPairCheck.Caption := 'Espanhol ↔ Português — 128,76 MiB'
  else if Base = 'en' then
    SecondPairCheck.Caption := 'Espanhol ↔ Inglês — 355,45 MiB'
  else
    SecondPairCheck.Caption := 'Inglês ↔ Espanhol — 355,45 MiB';

  if LastPairBase <> Base then
  begin
    FirstPairCheck.Checked := True;
    SecondPairCheck.Checked := False;
    LastPairBase := Base;
  end;
end;

procedure BaseLanguageChanged(Sender: TObject);
begin
  UpdatePairChoices;
end;

procedure AddModelDownload(SourceCode, TargetCode, Version: String);
var
  FileName: String;
begin
  FileName := SourceCode + '-' + TargetCode + '.argosmodel';
  DownloadPage.Add(
    'https://data.argosopentech.com/argospm/v1/translate-' + SourceCode + '_' + TargetCode +
      '-' + Version + '.argosmodel', FileName, '');
end;

procedure AddPackDownloads(Code: String);
begin
  if Code = 'en' then
  begin
    AddModelDownload('en', 'pb', '1_9');
    AddModelDownload('pb', 'en', '1_9');
  end
  else if Code = 'es' then
  begin
    AddModelDownload('es', 'pt', '1_0');
    AddModelDownload('pt', 'es', '1_0');
  end
  else if Code = 'en-es' then
  begin
    AddModelDownload('en', 'es', '1_0');
    AddModelDownload('es', 'en', '1_9');
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Index: Integer;
  Code: String;
begin
  Result := True;
  if CurPageID <> wpReady then Exit;
  DownloadErrorLabel.Hide;
  if GetSelectedPacks('') = '' then Exit;

  DownloadPage.Clear;
  DownloadPairsLabel.Caption := 'Pares escolhidos:';
  for Index := 0 to 1 do
  begin
    Code := PairCode(Index);
    if IsPackSelected(Code) then
    begin
      AddPackDownloads(Code);
      if Index = 0 then
        DownloadPairsLabel.Caption := DownloadPairsLabel.Caption + #13#10 +
          FirstPairCheck.Caption
      else
        DownloadPairsLabel.Caption := DownloadPairsLabel.Caption + #13#10 +
          SecondPairCheck.Caption;
    end;
  end;
  DownloadPage.Show;
  WizardForm.CancelButton.Hide;
  DownloadPage.AbortButton.Show;
  try
    try
      DownloadPage.Download;
    except
      if DownloadPage.AbortedByUser then
      begin
        Log('Download dos idiomas cancelado pelo usuário.');
        DownloadErrorLabel.Caption :=
          'Download cancelado. Nenhum arquivo desta instalação foi aplicado.' + #13#10 +
          'Você pode tentar novamente, mudar os pares ou fechar o instalador.';
      end
      else
      begin
        Log('Falha ao baixar ' + DownloadPage.LastBaseNameOrUrl + ': ' + GetExceptionMessage);
        DownloadErrorLabel.Caption :=
          'Não foi possível baixar um dos idiomas do servidor oficial.' + #13#10 +
          'Nenhum arquivo desta instalação foi aplicado. Clique Instalar para tentar novamente,' + #13#10 +
          'ou volte e desmarque o par para instalá-lo depois nas Configurações.';
      end;
      DownloadErrorLabel.Show;
      Result := False;
    end;
  finally
    DownloadPage.AbortButton.Hide;
    DownloadPage.Hide;
    WizardForm.CancelButton.Show;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Selected: String;
  ResultCode: Integer;
  ErrorText: AnsiString;
  ResultFile: String;
  Params: String;
  CableSetup: String;
  Retry: Integer;
begin
  if CurStep <> ssPostInstall then Exit;
  Selected := GetSelectedPacks('');
  if Selected <> '' then
  begin
    ResultFile := ExpandConstant('{tmp}\argos-install-result.txt');
    Params := '--install-argos-archives "' + ExpandConstant('{tmp}') + '" "' +
      GetTranslationRoot + '" "' + Selected + '" "' + ResultFile + '"';
    try
      InstallPage.Show;
      try
        InstallPage.Animate;
        if not Exec(ExpandConstant('{app}\{#AppExecutable}'), Params,
          ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) or
          (ResultCode <> 0) then
        begin
          if not LoadStringFromFile(ResultFile, ErrorText) then
            ErrorText := 'O aplicativo não conseguiu instalar os pacotes baixados.';
          RaiseException(String(ErrorText));
        end;
      finally
        InstallPage.Hide;
      end;
    except
      InstallFailureMessage :=
        'O Global Voice foi copiado, mas os idiomas não foram instalados.' + #13#10 +
        'Tente instalar os pares em Configurações > Idiomas ou execute o instalador novamente.';
      Log('Falha na instalação dos idiomas: ' + GetExceptionMessage);
      Exit;
    end;
  end;

  if WizardIsComponentSelected('cable') and ShouldInstallVBCable then
  begin
    CableSetup := ExpandConstant('{app}\drivers\VB-CABLE\VBCABLE_Setup_x64.exe');
    try
      CablePage.Show;
      try
        CablePage.Animate;
        ResultCode := -1;
        if not Exec(CableSetup, '-i -h', ExtractFileDir(CableSetup),
          SW_HIDE, ewWaitUntilTerminated, ResultCode) or
          ((ResultCode <> 0) and (ResultCode <> 3010)) then
          RaiseException('Código de retorno do VB-CABLE: ' + IntToStr(ResultCode));
        for Retry := 1 to 20 do
        begin
          if IsVBCableInstalled then Break;
          Sleep(500);
        end;
        if not IsVBCableInstalled then
          Log('O VB-CABLE ainda não aparece como dispositivo. É necessário reiniciar o Windows.');
        VBCableInstalledBySetup := True;
        SetIniString('VirtualCable', 'RestartRequestedAt',
          GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':'),
          ExpandConstant('{app}\installation.ini'));
      finally
        CablePage.Hide;
      end;
    except
      InstallFailureMessage :=
        'O Global Voice e os idiomas foram instalados, mas o microfone virtual falhou.' + #13#10 +
        'Reinicie o Windows e confira o VB-CABLE em Configurações > Voz. Se não aparecer, use Instalar ou Reparar nessa tela.';
      Log('Falha na instalação do VB-CABLE: ' + GetExceptionMessage);
    end;
  end;
end;

function InitializeUninstall: Boolean;
var
  ChoiceForm: TSetupForm;
  Description: TNewStaticText;
  CableCheck: TNewCheckBox;
  ContinueButton: TNewButton;
  CancelButton: TNewButton;
begin
  Result := True;
  RemoveVBCableOnUninstall := False;
  if UninstallSilent or
     not FileExists(ExpandConstant('{app}\drivers\VB-CABLE\VBCABLE_Setup_x64.exe')) or
     not IsVBCableInstalled then Exit;

  ChoiceForm := CreateCustomForm(ScaleX(460), ScaleY(155), False, False);
  try
    if ActiveLanguage = 'english' then
      ChoiceForm.Caption := 'Remove Global Voice'
    else
      ChoiceForm.Caption := 'Desinstalar Global Voice';

    Description := TNewStaticText.Create(ChoiceForm);
    Description.Parent := ChoiceForm;
    Description.SetBounds(ScaleX(16), ScaleY(16), ScaleX(425), ScaleY(42));
    Description.WordWrap := True;
    if ActiveLanguage = 'english' then
      Description.Caption := 'Choose whether to remove the virtual microphone too.' + #13#10 +
        'Other apps may use VB-CABLE.'
    else
      Description.Caption := 'Escolha se deseja remover também o microfone virtual.' + #13#10 +
        'Outros aplicativos podem usar o VB-CABLE.';

    CableCheck := TNewCheckBox.Create(ChoiceForm);
    CableCheck.Parent := ChoiceForm;
    CableCheck.SetBounds(ScaleX(16), ScaleY(67), ScaleX(425), ScaleY(28));
    if ActiveLanguage = 'english' then
      CableCheck.Caption := 'Uninstall VB-CABLE driver'
    else
      CableCheck.Caption := 'Desinstalar driver VB-CABLE';
    CableCheck.Checked := False;
    CableCheck.TabOrder := 1;

    ContinueButton := TNewButton.Create(ChoiceForm);
    ContinueButton.Parent := ChoiceForm;
    ContinueButton.SetBounds(ScaleX(268), ScaleY(112), ScaleX(82), ScaleY(27));
    if ActiveLanguage = 'english' then
      ContinueButton.Caption := 'Continue'
    else
      ContinueButton.Caption := 'Continuar';
    ContinueButton.ModalResult := mrOk;
    ContinueButton.Default := True;
    ContinueButton.TabOrder := 0;

    CancelButton := TNewButton.Create(ChoiceForm);
    CancelButton.Parent := ChoiceForm;
    CancelButton.SetBounds(ScaleX(360), ScaleY(112), ScaleX(82), ScaleY(27));
    if ActiveLanguage = 'english' then
      CancelButton.Caption := 'Cancel'
    else
      CancelButton.Caption := 'Cancelar';
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;
    CancelButton.TabOrder := 2;

    ChoiceForm.ActiveControl := ContinueButton;
    Result := ChoiceForm.ShowModal = mrOk;
    if Result then
      RemoveVBCableOnUninstall := CableCheck.Checked;
  finally
    ChoiceForm.Free;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  CableSetup: String;
  ResultCode: Integer;
begin
  if (CurUninstallStep <> usUninstall) or not RemoveVBCableOnUninstall then Exit;
  CableSetup := ExpandConstant('{app}\drivers\VB-CABLE\VBCABLE_Setup_x64.exe');
  ResultCode := -1;
  if not Exec(CableSetup, '-u -h', ExtractFileDir(CableSetup),
    SW_HIDE, ewWaitUntilTerminated, ResultCode) or
    ((ResultCode <> 0) and (ResultCode <> 3010)) then
  begin
    Log('Falha ao remover VB-CABLE. Código: ' + IntToStr(ResultCode));
    if ActiveLanguage = 'english' then
      MsgBox('Global Voice will be removed, but VB-CABLE could not be uninstalled. Remove it separately in Windows Settings.', mbError, MB_OK)
    else
      MsgBox('O Global Voice será removido, mas não foi possível desinstalar o VB-CABLE. Remova-o separadamente nas Configurações do Windows.', mbError, MB_OK);
    Exit;
  end;
  VBCableRemovedByUninstall := True;
end;

function UninstallNeedRestart: Boolean;
begin
  Result := VBCableRemovedByUninstall;
end;

procedure InitializeWizard;
var
  SectionLabel: TNewStaticText;
  HelpLabel: TNewStaticText;
  CableCreditLabel: TNewStaticText;
  SurfaceWidth: Integer;
  RequestedBase: String;
begin
  LanguagePage := CreateCustomPage(
    wpWelcome, 'Idiomas', 'Escolha o idioma principal e os pares de tradução.'
  );
  SurfaceWidth := LanguagePage.SurfaceWidth - ScaleX(16);

  SectionLabel := TNewStaticText.Create(LanguagePage);
  SectionLabel.Parent := LanguagePage.Surface;
  SectionLabel.SetBounds(ScaleX(8), ScaleY(6), SurfaceWidth, ScaleY(23));
  SectionLabel.Caption := 'Idioma Principal';

  BasePtRadio := TNewRadioButton.Create(LanguagePage);
  BasePtRadio.Parent := LanguagePage.Surface;
  BasePtRadio.SetBounds(ScaleX(8), ScaleY(30), SurfaceWidth, ScaleY(23));
  BasePtRadio.Caption := 'Português (Brasil)';
  BasePtRadio.OnClick := @BaseLanguageChanged;

  BaseEnRadio := TNewRadioButton.Create(LanguagePage);
  BaseEnRadio.Parent := LanguagePage.Surface;
  BaseEnRadio.SetBounds(ScaleX(8), ScaleY(58), SurfaceWidth, ScaleY(23));
  BaseEnRadio.Caption := 'Inglês';
  BaseEnRadio.OnClick := @BaseLanguageChanged;

  BaseEsRadio := TNewRadioButton.Create(LanguagePage);
  BaseEsRadio.Parent := LanguagePage.Surface;
  BaseEsRadio.SetBounds(ScaleX(8), ScaleY(86), SurfaceWidth, ScaleY(23));
  BaseEsRadio.Caption := 'Espanhol';
  BaseEsRadio.OnClick := @BaseLanguageChanged;

  SectionLabel := TNewStaticText.Create(LanguagePage);
  SectionLabel.Parent := LanguagePage.Surface;
  SectionLabel.SetBounds(ScaleX(8), ScaleY(129), SurfaceWidth, ScaleY(23));
  SectionLabel.Caption := 'Pares de tradução para o idioma principal';

  FirstPairCheck := TNewCheckBox.Create(LanguagePage);
  FirstPairCheck.Parent := LanguagePage.Surface;
  FirstPairCheck.SetBounds(ScaleX(8), ScaleY(157), SurfaceWidth, ScaleY(24));

  SecondPairCheck := TNewCheckBox.Create(LanguagePage);
  SecondPairCheck.Parent := LanguagePage.Surface;
  SecondPairCheck.SetBounds(ScaleX(8), ScaleY(187), SurfaceWidth, ScaleY(24));

  HelpLabel := TNewStaticText.Create(LanguagePage);
  HelpLabel.Parent := LanguagePage.Surface;
  HelpLabel.SetBounds(ScaleX(8), ScaleY(225), SurfaceWidth, ScaleY(48));
  HelpLabel.WordWrap := True;
  HelpLabel.Caption := 'Cada par traduz nos dois sentidos. Os modelos selecionados serão baixados durante a instalação.';

  RequestedBase := Lowercase(ExpandConstant('{param:BASELANGUAGE|}'));
  if RequestedBase = 'en' then BaseEnRadio.Checked := True
  else if RequestedBase = 'es' then BaseEsRadio.Checked := True
  else BasePtRadio.Checked := True;
  UpdatePairChoices;
  DownloadPage := CreateDownloadPage('Baixando idiomas',
    'Os pares escolhidos são baixados nesta página.', nil);
  DownloadPage.ShowBaseNameInsteadOfUrl := True;
  DownloadPage.AbortButton.Parent := WizardForm.CancelButton.Parent;
  DownloadPage.AbortButton.SetBounds(
    WizardForm.CancelButton.Left, WizardForm.CancelButton.Top,
    WizardForm.CancelButton.Width, WizardForm.CancelButton.Height);
  DownloadPage.AbortButton.Caption := 'Cancelar';
  DownloadPage.AbortButton.Style := WizardForm.CancelButton.Style;
  DownloadPage.AbortButton.Font.Assign(WizardForm.CancelButton.Font);
  DownloadPage.AbortButton.Hide;
  DownloadPairsLabel := TNewStaticText.Create(DownloadPage);
  DownloadPairsLabel.Parent := DownloadPage.Surface;
  DownloadPairsLabel.SetBounds(
    DownloadPage.Msg1Label.Left, DownloadPage.Msg1Label.Top,
    DownloadPage.SurfaceWidth, ScaleY(58));
  DownloadPairsLabel.WordWrap := True;
  DownloadPage.Msg1Label.Top := DownloadPage.Msg1Label.Top + ScaleY(62);
  DownloadPage.Msg2Label.Top := DownloadPage.Msg2Label.Top + ScaleY(62);
  DownloadPage.ProgressBar.Top := DownloadPage.ProgressBar.Top + ScaleY(62);
  WizardForm.ReadyMemo.Height := WizardForm.ReadyMemo.Height - ScaleY(70);
  DownloadErrorLabel := TNewStaticText.Create(WizardForm.ReadyMemo.Parent);
  DownloadErrorLabel.Parent := WizardForm.ReadyMemo.Parent;
  DownloadErrorLabel.SetBounds(
    WizardForm.ReadyMemo.Left,
    WizardForm.ReadyMemo.Top + WizardForm.ReadyMemo.Height + ScaleY(8),
    WizardForm.ReadyMemo.Width, ScaleY(62));
  DownloadErrorLabel.WordWrap := True;
  DownloadErrorLabel.Font.Color := clRed;
  DownloadErrorLabel.Hide;
  InstallPage := CreateOutputMarqueeProgressPage('Instalando idiomas',
    'Validando e preparando os modelos de tradução.');
  CablePage := CreateOutputMarqueeProgressPage('Instalando microfone virtual',
    'Preparando o VB-CABLE. Isso pode levar alguns instantes.');

  WizardForm.ComponentsList.Height := WizardForm.ComponentsList.Height - ScaleY(32);
  CableCreditLabel := TNewStaticText.Create(WizardForm.SelectComponentsPage);
  CableCreditLabel.Parent := WizardForm.SelectComponentsPage;
  CableCreditLabel.SetBounds(
    WizardForm.ComponentsList.Left,
    WizardForm.ComponentsList.Top + WizardForm.ComponentsList.Height + ScaleY(5),
    WizardForm.ComponentsList.Width, ScaleY(28));
  CableCreditLabel.WordWrap := True;
  CableCreditLabel.Caption :=
    'VB-CABLE é da VB-Audio e donationware. Contribuições: vb-cable.com';

  if ExpandConstant('{param:COMPONENTS|}') <> '' then
  begin
    Log('Seleção de componentes recebida pela linha de comando.');
    Exit;
  end;

  NvidiaDetected := HasNvidiaDisplayAdapter;
  if NvidiaDetected then
    WizardSelectComponents('base,nvidia,cable')
  else
    WizardSelectComponents('base,!nvidia,cable');
end;
