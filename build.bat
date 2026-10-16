@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PY=py -3"
) else (
    set "PY=python"
)
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name TypeForgeStudio app.py
if errorlevel 1 goto :error
echo.
echo SUCCESS! dist\TypeForgeStudio.exe
pause
exit /b 0
:error
echo Build failed. Install Python 3.10+ from python.org and try again.
pause
exit /b 1