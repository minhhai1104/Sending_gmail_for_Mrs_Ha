@echo off
chcp 65001 >nul
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw -3 main.py & exit /b)
where pythonw >nul 2>nul && (start "" pythonw main.py & exit /b)
echo Chua cai Python tren may nay.
echo Hay tai Python tai https://www.python.org/downloads/ (nho tick "Add python.exe to PATH") roi chay lai file nay.
pause
