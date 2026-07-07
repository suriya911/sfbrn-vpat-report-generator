; ============================================================
;  SFBRN VPAT Reviewer v10 - Inno Setup installer script
;  Open this file in Inno Setup (free: https://jrsoftware.org)
;  and click Build > Compile. Output: Output\VPAT_Reviewer_Setup.exe
;
;  What the installer does (single click, no technical questions):
;   - Installs the app to the user's LocalAppData folder
;     (no administrator rights required)
;   - Creates Desktop\VPAT Reviewer Files\VPATs
;   - Creates Desktop\VPAT Reviewer Files\VPAT Summary Reports
;   - Adds a Desktop shortcut and Start Menu entry
;   - Works fully offline after installation
; ============================================================

[Setup]
AppName=VPAT Reviewer
AppVersion=10.0
AppPublisher=San Francisco Bay Region Network (SFBRN)
DefaultDirName={localappdata}\VPAT_Reviewer
DefaultGroupName=VPAT Reviewer
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
DisableDirPage=yes
OutputBaseFilename=VPAT_Reviewer_Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayName=VPAT Reviewer

[Files]
; Everything PyInstaller produced, including the assets subfolder
Source: "dist\VPAT_Reviewer\*"; DestDir: "{app}"; \
    Flags: recursesubdirs createallsubdirs ignoreversion

[Dirs]
; Required Desktop folder structure (also re-verified at app startup)
Name: "{userdesktop}\VPAT Reviewer Files"
Name: "{userdesktop}\VPAT Reviewer Files\VPATs"
Name: "{userdesktop}\VPAT Reviewer Files\VPAT Summary Reports"

[Icons]
Name: "{userdesktop}\VPAT Reviewer"; Filename: "{app}\VPAT_Reviewer.exe"; \
    Comment: "VPAT Accessibility Compliance Reviewer"
Name: "{group}\VPAT Reviewer"; Filename: "{app}\VPAT_Reviewer.exe"

[Run]
Filename: "{app}\VPAT_Reviewer.exe"; Description: "Launch VPAT Reviewer now"; \
    Flags: postinstall nowait skipifsilent
