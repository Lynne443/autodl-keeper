@echo off
echo ============================================
echo  AutoDL Keeper - Build Script
echo ============================================

echo.
echo [1/4] Building React UI...
cd ui
call npm install
call npm run build
cd ..
if errorlevel 1 ( echo ERROR: React build failed & pause & exit /b 1 )
echo OK: React UI built

echo.
echo [2/4] Installing Python deps...
pip install flask pywebview playwright pyinstaller pystray Pillow -q
if errorlevel 1 ( echo ERROR: pip install failed & pause & exit /b 1 )

echo.
echo [3/4] Finding Playwright Chromium...
set "CHROMIUM_PATH="
set "CHROMIUM_NAME="
for /d %%i in ("%LOCALAPPDATA%\ms-playwright\chromium-*") do (
    set "CHROMIUM_PATH=%%i"
    set "CHROMIUM_NAME=%%~nxi"
)
if not defined CHROMIUM_PATH (
    echo Chromium not found, installing...
    playwright install chromium
    for /d %%i in ("%LOCALAPPDATA%\ms-playwright\chromium-*") do (
        set "CHROMIUM_PATH=%%i"
        set "CHROMIUM_NAME=%%~nxi"
    )
)
if not defined CHROMIUM_PATH ( echo ERROR: Chromium install failed & pause & exit /b 1 )
echo Found: %CHROMIUM_PATH%

echo.
echo [4/4] Packaging EXE...
pyinstaller --onedir --windowed ^
  --name "AutoDL" ^
  --add-data "ui/dist;ui/dist" ^
  --add-data "autodl_keeper.py;." ^
  --add-data "get_token.py;." ^
  --add-data "monitor.py;." ^
  --add-data "%CHROMIUM_PATH%;playwright/driver/package/.local-browsers/%CHROMIUM_NAME%" ^
  --hidden-import webview.platforms.edgechromium ^
  --hidden-import webview.platforms.winforms ^
  --hidden-import flask ^
  --hidden-import engineio.async_drivers.threading ^
  --hidden-import playwright ^
  --hidden-import playwright.async_api ^
  --hidden-import pystray._impl.win32 ^
  --hidden-import PIL ^
  main.py
if errorlevel 1 ( echo ERROR: PyInstaller failed & pause & exit /b 1 )

echo.
echo ============================================
echo  Done! EXE: dist\AutoDL\AutoDL.exe
echo ============================================
pause
