; packaging/windows/installer.nsi
; NSIS installer script for analogdata-esp (PyInstaller onedir build)
;
; Requires NSIS 3.x: https://nsis.sourceforge.io
; Install on Windows: choco install nsis
;
; Build manually (from repo root):
;   makensis /DVERSION="0.2.0" packaging\windows\installer.nsi
;
; Or let GitHub Actions build it automatically on every release tag push.
;
; PyInstaller onedir output layout expected BEFORE running this script:
;   dist\analogdata-esp\analogdata-esp.exe   ← the real binary
;   dist\analogdata-esp\_internal\           ← shared libs and .pyc files
;   (both must be installed together — binary looks for _internal\ at runtime)

Unicode True

; ── Version ──────────────────────────────────────────────────────────────────
; Version is injected via the command line: makensis /DVERSION="0.2.0" ...
; Falls back to reading version.nsh if /DVERSION is not given.
!ifndef VERSION
  !include "version.nsh"   ; version.nsh contains: !define VERSION "0.x.x"
!endif

; ── Constants ─────────────────────────────────────────────────────────────────
!define APP_NAME     "analogdata-esp"
!define APP_VENDOR   "Analog Data"
!define APP_EXE      "analogdata-esp.exe"
; Install to C:\Program Files\Analog Data\analogdata-esp\
!define INSTALL_DIR  "$PROGRAMFILES64\${APP_VENDOR}\${APP_NAME}"
!define REG_KEY      "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

; ── Installer settings ────────────────────────────────────────────────────────
Name            "${APP_NAME} ${VERSION}"
OutFile         "${APP_NAME}-setup.exe"     ; output filename (goes to repo root)
InstallDir      "${INSTALL_DIR}"
InstallDirRegKey HKLM "${REG_KEY}" "InstallLocation"
RequestExecutionLevel admin                 ; needs admin to write to Program Files + PATH
SetCompressor   /SOLID lzma                 ; best compression ratio

; ── UI pages ─────────────────────────────────────────────────────────────────
!include "MUI2.nsh"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ── Install section ───────────────────────────────────────────────────────────
Section "Install" SecMain

  ; ── Copy the binary to $INSTDIR ──────────────────────────────────────────
  SetOutPath "$INSTDIR"
  ; The real binary (PyInstaller onedir: binary is inside the bundle directory)
  File "..\..\dist\analogdata-esp\${APP_EXE}"

  ; ── Copy _internal\ (PyInstaller libs — must be beside the binary) ────────
  ; SetOutPath changes the destination for the next File commands.
  SetOutPath "$INSTDIR\_internal"
  ; /r copies the directory recursively including all subdirectories
  File /r "..\..\dist\analogdata-esp\_internal\*.*"

  ; ── Write uninstaller ─────────────────────────────────────────────────────
  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; ── Add $INSTDIR to the system PATH ──────────────────────────────────────
  ; EnVar plugin is bundled with recent NSIS installations
  EnVar::AddValue "PATH" "$INSTDIR"
  Pop $0   ; 0 = success, non-zero = error (PATH was already set, or access denied)

  ; ── Add Add/Remove Programs registry entry ────────────────────────────────
  WriteRegStr   HKLM "${REG_KEY}" "DisplayName"      "${APP_NAME} ${VERSION}"
  WriteRegStr   HKLM "${REG_KEY}" "DisplayVersion"   "${VERSION}"
  WriteRegStr   HKLM "${REG_KEY}" "Publisher"        "${APP_VENDOR}"
  WriteRegStr   HKLM "${REG_KEY}" "InstallLocation"  "$INSTDIR"
  WriteRegStr   HKLM "${REG_KEY}" "UninstallString"  '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "${REG_KEY}" "NoModify"         1
  WriteRegDWORD HKLM "${REG_KEY}" "NoRepair"         1

  ; Broadcast PATH change so open terminals see the new entry without restarting
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

SectionEnd

; ── Uninstall section ─────────────────────────────────────────────────────────
Section "Uninstall"

  ; Remove _internal\ directory and all its contents
  RMDir /r "$INSTDIR\_internal"

  ; Remove the binary and uninstaller
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\uninstall.exe"

  ; Remove (now empty) install directories
  RMDir "$INSTDIR"
  RMDir "$PROGRAMFILES64\${APP_VENDOR}"

  ; Remove from system PATH
  EnVar::DeleteValue "PATH" "$INSTDIR"
  Pop $0

  ; Remove Add/Remove Programs entry
  DeleteRegKey HKLM "${REG_KEY}"

  ; Broadcast PATH change so open terminals see the removal
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

SectionEnd
