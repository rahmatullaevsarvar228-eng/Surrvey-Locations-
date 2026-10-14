@echo off
REM GreenCredit.exe ni Windows kompyuterda yig'ish (Python 3.10+ o'rnatilgan bo'lishi kerak).
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || goto :xato
python -m PyInstaller --noconfirm --onefile --windowed --name GreenCredit --collect-submodules reportlab run_app.py || goto :xato
echo.
echo Tayyor: dist\GreenCredit.exe
pause
exit /b 0
:xato
echo.
echo Xatolik yuz berdi. Python o'rnatilganini tekshiring: https://www.python.org/downloads/
pause
exit /b 1
