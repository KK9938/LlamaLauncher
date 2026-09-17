@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/2] Checking / installing dependencies...
py -3 -m pip install pyinstaller pystray pillow

echo [2/2] Building exe...
py -3 -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "LlamaLauncher" ^
    --hidden-import pystray ^
    --hidden-import PIL ^
    --noconfirm ^
    llama_launcher.py

echo.
echo Done. Output: dist\LlamaLauncher.exe
pause