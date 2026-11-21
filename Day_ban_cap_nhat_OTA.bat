@echo off
rem Tu dong kiem thu, dong goi va day phien ban moi len GitHub Releases (OTA)
chcp 65001 >nul
cd /d "%~dp0"
python scripts\publish_release.py --build %*
if errorlevel 1 (echo Day ban cap nhat that bai! & pause & exit /b 1)
pause
