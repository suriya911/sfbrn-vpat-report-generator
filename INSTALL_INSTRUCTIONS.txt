=====================================================
 VPAT REVIEWER - INSTALLATION INSTRUCTIONS (FOR USERS)
=====================================================

WHAT THIS APP DOES
------------------
The VPAT Reviewer reads a vendor-submitted VPAT document
(PDF, Word, or text file) and generates a professionally
styled accessibility compliance PDF report. Everything runs
on your own computer - no internet connection, account, or
API key is needed after installation. Your VPAT documents
never leave your machine.

HOW TO INSTALL (SINGLE CLICK)
-----------------------------
1. Double-click  VPAT_Reviewer_Setup.exe
2. Click "Install" (no administrator password needed).
3. That's it. The installer automatically:
   - Installs the app
   - Creates a "VPAT Reviewer" shortcut on your Desktop
   - Creates this folder structure on your Desktop:

        VPAT Reviewer Files\
            VPATs\                  (your uploaded VPATs are copied here)
            VPAT Summary Reports\   (finished reports are saved here)

FIRST TIME YOU OPEN THE APP
---------------------------
A short setup window asks for:
   - Your organization's name and short name/acronym
   - Your name and title (shown as the reviewer on reports)
   - An optional contact line and compliance threshold
   - An optional custom logo image
Answer once - the app remembers. You can change these later
with the "Settings" button at the top of the app.

HOW TO CREATE A REPORT
----------------------
1. Open VPAT Reviewer from the Desktop shortcut.
2. Click "Browse" (or drag a file in) and choose the vendor's
   VPAT file (.pdf, .docx, or .txt).
3. Answer the four quick review-context questions.
4. Click "Generate Report".
5. The finished PDF opens automatically and is saved in
   Desktop\VPAT Reviewer Files\VPAT Summary Reports\
   A compliance score and summary appear in the app.

TROUBLESHOOTING
---------------
- "Folder Error" at startup: the app could not create the
  Desktop folders. Check that your Desktop is not read-only
  (some managed/OneDrive desktops restrict this), then reopen
  the app - it re-creates missing folders automatically.
- Report shows a text "SFBRN" badge instead of a logo: the
  logo file was not found. Open Settings and browse to a
  PNG/JPG logo, or place SFBRN_Logo.png in the app's
  assets folder.
- Duplicate report names are never overwritten - the app
  automatically adds _v2, _v3, and so on.

UNINSTALLING
------------
Windows Settings > Apps > VPAT Reviewer > Uninstall.
Your VPATs and reports on the Desktop are never deleted.
