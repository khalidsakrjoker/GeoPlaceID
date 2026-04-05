@echo off
echo ==========================================
echo 1. Setting Playwright to local environment
echo ==========================================
set PLAYWRIGHT_BROWSERS_PATH=0

echo ==========================================
echo 2. Installing Chromium for Playwright...
echo ==========================================
playwright install chromium

echo ==========================================
echo 3. Building the application as ONE FILE...
echo ==========================================
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --add-data "docs;docs" ^
    --collect-all customtkinter ^
    --collect-all s2sphere ^
    --collect-all playwright ^
    app.py

echo ==========================================
echo Build completed successfully!
echo ==========================================
pause