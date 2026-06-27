; ignite_installer.iss
; Inno Setup Skript für das Jugend-forscht-Projekt "Ignite" (Entzündungsdetektion)
; Entwickelt von Jona Noack

[Setup]
; Einzigartige AppId (Generiert für das Projekt)
AppId={{928C6EFA-C40C-46C4-AE4B-0FEA0388B2A6}}
AppName=Ignite - Entzündungsdetektion
AppVersion=0.1.0
AppPublisher=Jona Noack
DefaultDirName={autopf}\Ignite
DefaultGroupName=Ignite
AllowNoIcons=yes
; Pfad zur Icon-Datei für den Installer selbst
SetupIconFile=icon\LogoRund.ico
; Speicherort und Name des fertigen Installers
OutputDir=.
OutputBaseFilename=Ignite_Setup_v0.1.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "german"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Hauptanwendung (die von PyInstaller erstellte EXE)
Source: "dist\Ignite.exe"; DestDir: "{app}"; Flags: ignoreversion
; Logos/Icons für eventuelle Verknüpfungs-Referenzen mitinstallieren
Source: "icon\LogoRund.ico"; DestDir: "{app}\icon"; Flags: ignoreversion
Source: "icon\LogoRund.png"; DestDir: "{app}\icon"; Flags: ignoreversion

[Icons]
; Startmenü-Verknüpfung
Name: "{group}\Ignite"; Filename: "{app}\Ignite.exe"; IconFilename: "{app}\icon\LogoRund.ico"
; Desktop-Verknüpfung (optional)
Name: "{autodesktop}\Ignite"; Filename: "{app}\Ignite.exe"; IconFilename: "{app}\icon\LogoRund.ico"; Tasks: desktopicon

[Run]
; Option zum direkten Starten nach der Installation
Filename: "{app}\Ignite.exe"; Description: "{cm:LaunchProgram,Ignite}"; Flags: nowait postinstall skipifsilent
