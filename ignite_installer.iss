; ignite_installer.iss
; Inno Setup Skript für "IGNITE Medical Imaging Suite"
; Entwickelt von Jona Noack

[Setup]
; Einzigartige AppId
AppId={{928C6EFA-C40C-46C4-AE4B-0FEA0388B2A6}}
AppName=IGNITE Medical Imaging Suite
AppVersion=1.0.0
AppPublisher=Jona Noack
AppPublisherURL=https://github.com/JonaNoack/ignite
AppSupportURL=https://github.com/JonaNoack/ignite/issues
DefaultDirName={autopf}\IGNITE Medical Imaging
DefaultGroupName=IGNITE Medical Imaging
AllowNoIcons=yes
PrivilegesRequired=lowest

; 64-Bit System-Enforcement
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; Versionierung und Metadaten für die Installer-EXE
VersionInfoVersion=1.0.0
VersionInfoCompany=Jona Noack
VersionInfoDescription=IGNITE Medical Imaging Suite – Thermografische Entzündungsdetektion
VersionInfoCopyright=Copyright (C) 2026 Jona Noack
VersionInfoProductName=IGNITE Medical Imaging Suite
VersionInfoProductVersion=1.0.0

; Pfad zur Icon-Datei für den Installer selbst
SetupIconFile=icon\LogoRund.ico
; Speicherort und Name des fertigen Installers
OutputDir=.
OutputBaseFilename=IGNITE_Setup_v1.0.0
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
