@echo off
echo Building ContextForge.exe...

pip install pyinstaller --quiet

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "ContextForge" ^
    --icon "assets/icon.ico" ^
    --add-data "assets;assets" ^
    main.py

echo.
echo Build complete. Executable is at dist/ContextForge.exe
pause
