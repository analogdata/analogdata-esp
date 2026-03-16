; packaging/windows/installer.nsi
; NSIS installer script for analogdata-esp (PyInstaller onedir build)
;
; Requires NSIS 3.x: https://nsis.sourceforge.io
; Install on Windows: choco install nsis
;
; Build manually (from repo root):
;   makensis /DVERSION="0.2.0" packaging\windows\installer.nsi
;
; PyInstaller onedir output layout expected before running this script:
;   dist\analogdata-esp\analogdata-esp.exe   the real binary
;   dist\analogdata-esp\_internal\           shared libs and .pyc files
;   (both must be installed together — binary looks for _internal\ at runtime)

Unicode True

; Version is injected via the command line: makensis /DVERSION="0.2.0"
; Falls back to reading version.nsh if /DVERSION is not given.
!ifndef VERSION
  !include "version.nsh"
!endif

!define APP_NAME    "analogdata-esp"
!define APP_VENDOR  "Analog Data"
!define APP_EXE     "analogdata-esp.exe"
!define REG_UNINSTALL "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
!define REG_ENV       "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

Name            "${APP_NAME} ${VERSION}"
OutFile         "${APP_NAME}-setup.exe"
InstallDir      "$PROGRAMFILES64\${APP_VENDOR}\${APP_NAME}"
InstallDirRegKey HKLM "${REG_UNINSTALL}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor   /SOLID lzma

!include "MUI2.nsh"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

; ── Install ───────────────────────────────────────────────────────────────────
Section "Install" SecMain

  ; Copy the binary (PyInstaller onedir: exe is inside the bundle directory)
  SetOutPath "$INSTDIR"
  File "..\..\dist\analogdata-esp\${APP_EXE}"

  ; Copy _internal\ — must sit beside the binary so PyInstaller can find it
  SetOutPath "$INSTDIR\_internal"
  File /r "..\..\dist\analogdata-esp\_internal\*.*"

  ; Write uninstaller
  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Add $INSTDIR to the system PATH via registry (no plugin required)
  ReadRegStr $R0 HKLM "${REG_ENV}" "Path"
  WriteRegExpandStr HKLM "${REG_ENV}" "Path" "$R0;$INSTDIR"

  ; Add/Remove Programs entry
  WriteRegStr   HKLM "${REG_UNINSTALL}" "DisplayName"      "${APP_NAME} ${VERSION}"
  WriteRegStr   HKLM "${REG_UNINSTALL}" "DisplayVersion"   "${VERSION}"
  WriteRegStr   HKLM "${REG_UNINSTALL}" "Publisher"        "${APP_VENDOR}"
  WriteRegStr   HKLM "${REG_UNINSTALL}" "InstallLocation"  "$INSTDIR"
  WriteRegStr   HKLM "${REG_UNINSTALL}" "UninstallString"  '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "${REG_UNINSTALL}" "NoModify"         1
  WriteRegDWORD HKLM "${REG_UNINSTALL}" "NoRepair"         1

  ; Broadcast PATH change so open terminals pick it up
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

SectionEnd

; ── Uninstall ─────────────────────────────────────────────────────────────────
Section "Uninstall"

  RMDir /r "$INSTDIR\_internal"
  Delete   "$INSTDIR\${APP_EXE}"
  Delete   "$INSTDIR\uninstall.exe"
  RMDir    "$INSTDIR"
  RMDir    "$PROGRAMFILES64\${APP_VENDOR}"

  ; Remove registry entries
  DeleteRegKey HKLM "${REG_UNINSTALL}"

  ; Broadcast so terminals reflect the removal
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

SectionEnd
