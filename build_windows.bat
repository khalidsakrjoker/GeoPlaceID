@echo off
echo ===================================================
echo     GeoPlaceID - Windows Build Script
echo ===================================================
echo.
echo Installing requirements...
pip install -r requirements.txt

echo.
echo Installing Playwright browsers...
playwright install chromium

echo.
echo Building Windows EXE...
pyinstaller --noconfirm --onedir --windowed --name "GeoPlaceID" --add-data "venv\Lib\site-packages\customtkinter;customtkinter\" app.py

echo.
echo ===================================================
echo Done! Check the 'dist\GeoPlaceID' folder.
echo You can zip this folder and send it to the user.
echo ===================================================
pause
