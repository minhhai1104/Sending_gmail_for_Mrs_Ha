@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Dong goi Gmail Auto Mailer v3.0 (--onedir + updater.exe + Bo cai 1-Click Setup.exe) ===
python scripts\build_exe.py
if errorlevel 1 (
    echo [LOI] Dong goi that bai!
    pause
    exit /b 1
)
echo.
echo [HOAN TAT] Bo cai 1-Click va thu muc App nam trong Ban_phat_hanh\
pause
