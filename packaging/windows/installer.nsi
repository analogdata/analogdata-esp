; NSIS installer script for analogdata-esp
; Requires NSIS 3.x: https://nsis.sourceforge.io
;
; Build:
;   makensis packaging/windows/installer.nsi
;
; Or from GitHub Actions (version injected via version.nsh):
;   Set-Content version.nsh '!define VERSION "0.1.0"'
;   makensis packaging/windows/installer.nsi

Unicode True

; Include version (written by CI or manually)
!ifdef VERSION
  ; already defined via /D or version.nsh
!else
  !include "version.nsh"
!endif

!define APP_NAME     "analogdata-esp"
!define APP_VENDOR   "Analog Data"
!define APP_EXE      "analogdata-esp.exe"
!define INSTALL_DIR  "$PROGRAMFILES64\${APP_VENDOR}\${APP_NAME}"
!define REG_KEY      "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

;--------------------------------
; General
Name            "${APP_NAME} ${VERSION}"
OutFile         "${APP_NAME}-setup.exe"
InstallDir      "${INSTALL_DIR}"
InstallDirRegKey HKLM "${REG_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor   /SOLID lzma

;--------------------------------
; Pages
!include "MUI2.nsh"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Install section
Section "Install" SecMain
  SetOutPath "$INSTDIR"

  ; Copy the PyInstaller-built binary (built before NSIS runs)
  File "..\..\dist\analogdata-esp.exe"

  ; Write uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Add to system PATH
  EnVar::AddValue "PATH" "$INSTDIR"
  Pop $0   ; 0 = success

  ; Add Add/Remove Programs entry
  WriteRegStr   HKLM "${REG_KEY}" "DisplayName"      "${APP_NAME} ${VERSION}"
  WriteRegStr   HKLM "${REG_KEY}" "DisplayVersion"   "${VERSION}"
  WriteRegStr   HKLM "${REG_KEY}" "Publisher"        "${APP_VENDOR}"
  WriteRegStr   HKLM "${REG_KEY}" "InstallLocation"  "$INSTDIR"
  WriteRegStr   HKLM "${REG_KEY}" "UninstallString"  '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "${REG_KEY}" "NoModify"         1
  WriteRegDWORD HKLM "${REG_KEY}" "NoRepair"         1

  ; Broadcast PATH change so existing terminals pick it up
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
SectionEnd

;--------------------------------
; Uninstall section
Section "Uninstall"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\uninstall.exe"
  RMDir  "$INSTDIR"
  RMDir  "$PROGRAMFILES64\${APP_VENDOR}"

  ; Remove from PATH
  EnVar::DeleteValue "PATH" "$INSTDIR"
  Pop $0

  ; Remove registry entry
  DeleteRegKey HKLM "${REG_KEY}"

  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
SectionEnd
