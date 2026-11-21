@echo off
rem Dong goi ung dung 2 tien trinh tren o dia cuc bo (%TEMP%) de tranh Google Drive khoa file khi PyInstaller nhung PKG archive
chcp 65001 >nul
cd /d "%~dp0"
set "LOCAL_DIST=%TEMP%\gmail_mailer_build\dist"
if not exist "%LOCAL_DIST%" mkdir "%LOCAL_DIST%"
if not exist "Ban_phat_hanh" mkdir "Ban_phat_hanh"

echo [1/3] Dang dong goi Gui_mail_nha_cung_cap.exe...
python -m PyInstaller Gui_mail_nha_cung_cap.spec --noconfirm --clean ^
  --distpath "%LOCAL_DIST%" --workpath "%TEMP%\gmail_mailer_build\main"
if errorlevel 1 (echo Dong goi Gui_mail_nha_cung_cap.exe that bai & pause & exit /b 1)

echo [2/3] Dang dong goi tien trinh cap nhat OTA updater.exe...
python -m PyInstaller updater.spec --noconfirm --clean ^
  --distpath "%LOCAL_DIST%" --workpath "%TEMP%\gmail_mailer_build\updater"
if errorlevel 1 (echo Dong goi updater.exe that bai & pause & exit /b 1)

echo [3/3] Dang kiem tra toan ven PKG archive va sao chep sang Ban_phat_hanh...
copy /Y "%LOCAL_DIST%\Gui_mail_nha_cung_cap.exe" "Ban_phat_hanh\Gui_mail_nha_cung_cap.exe" >nul
copy /Y "%LOCAL_DIST%\updater.exe" "Ban_phat_hanh\updater.exe" >nul
python -c "from PyInstaller.archive.readers import CArchiveReader; CArchiveReader('Ban_phat_hanh/Gui_mail_nha_cung_cap.exe'); CArchiveReader('Ban_phat_hanh/updater.exe'); print('OK: PKG archive hop le 100%%')"
if errorlevel 1 (echo Loi toan ven PKG archive! & pause & exit /b 1)

echo.
echo Xong! Bo 2 file Gui_mail_nha_cung_cap.exe va updater.exe da nam trong thu muc Ban_phat_hanh.
pause
