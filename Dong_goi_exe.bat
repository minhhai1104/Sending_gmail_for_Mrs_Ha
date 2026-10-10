@echo off
rem Dong goi ung dung thanh 1 file exe duy nhat (can cai: pip install pyinstaller)
chcp 65001 >nul
cd /d "%~dp0"
python -m PyInstaller main.py --noconfirm --clean --onefile --windowed ^
  --name "Gui_mail_nha_cung_cap" ^
  --paths vendor ^
  --distpath "Ban_phat_hanh" --workpath "build" --specpath "build"
if errorlevel 1 (echo Dong goi that bai & pause & exit /b 1)
echo.
echo Xong! File exe nam trong thu muc Ban_phat_hanh. Chi can copy file nay sang may khac.
pause
