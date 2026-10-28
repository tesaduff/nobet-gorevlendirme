; Nöbetçi Öğretmen Görevlendirme — Windows kurulum betiği (Inno Setup 6)
; GitHub Actions derler: ISCC /DMyAppVersion=1.2.3 installer.iss

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "Nöbetçi Öğretmen Görevlendirme"
#define MyAppExe "NobetGorevlendirme.exe"

[Setup]
AppId={{5C7E2A9B-3F14-4D8A-9B6C-2E81F0A4D3B7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=tesaduff
AppPublisherURL=https://github.com/tesaduff/nobet-gorevlendirme
; Kullanıcı klasörüne kurulur: yönetici izni gerekmez, güncelleme dosyaları yazabilir.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\NobetGorevlendirme
; Tek tıkla kurulum: soru sorulmaz, sayfalar atlanır, kurulum bitince program açılır.
DisableWelcomePage=yes
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
DisableFinishedPage=yes
ShowLanguageDialog=no
SetupIconFile=assets\icon.ico
OutputDir=dist
OutputBaseFilename=NobetGorevlendirme-Kurulum
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[InstallDelete]
; Eski sürümün kütüphaneleri yenileriyle karışmasın
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\NobetGorevlendirme\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"

[Run]
; Kurulum (ve sessiz güncelleme) bitince program kendiliğinden açılır
Filename: "{app}\{#MyAppExe}"; Flags: nowait

[Code]
// Kaldırırken verilerin de silinip silinmeyeceğini sorar. Evet denirse program aynı
// bilgisayara yeniden kurulduğunda sıfırdan başlar.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir, ExcelDir, Msg, NL: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    NL := Chr(13) + Chr(10);
    DataDir := ExpandConstant('{userappdata}\NobetGorevlendirme');
    ExcelDir := ExpandConstant('{userdocs}\Nöbet Görevlendirme');
    Msg := 'Programın verileri de silinsin mi?' + NL + NL +
      'Ders programı, nöbet çizelgeleri, görevlendirme kayıtları, okul bilgileri ve Excel ' +
      'kayıt dosyası silinir. Program yeniden kurulursa sıfırdan başlar.' + NL + NL +
      'Verileri saklamak istiyorsanız Hayır deyin.';
    if (not UninstallSilent) and DirExists(DataDir) then
      if MsgBox(Msg, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
        if DirExists(ExcelDir) then
          DelTree(ExcelDir, True, True, True);
      end;
  end;
end;
