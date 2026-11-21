@echo off
rem Dong goi ung dung 2 tien trinh (Gui_mail_nha_cung_cap.exe + updater.exe) qua file spec chuan
chcp 65001 >nul
cd /d "%~dp0"
echo [1/2] Dang dong goi Gui_mail_nha_cung_cap.exe...
python -m PyInstaller Gui_mail_nha_cung_cap.spec --noconfirm --clean ^
  --distpath "Ban_phat_hanh" --workpath "%TEMP%\gmail_mailer_build\main"
if errorlevel 1 (echo Dong goi Gui_mail_nha_cung_cap.exe that bai & pause & exit /b 1)

echo [2/2] Dang dong goi tien trinh cap nhat OTA updater.exe...
python -m PyInstaller updater.spec --noconfirm --clean ^
  --distpath "Ban_phat_hanh" --workpath "%TEMP%\gmail_mailer_build\updater"
if errorlevel 1 (echo Dong goi updater.exe that bai & pause & exit /b 1)

echo.
echo Xong! Bo 2 file Gui_mail_nha_cung_cap.exe va updater.exe da nam trong thu muc Ban_phat_hanh.
pause
