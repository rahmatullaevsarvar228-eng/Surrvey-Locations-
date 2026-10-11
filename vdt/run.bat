@echo off
rem Virtual Double-Track - Windows uchun ishga tushirish (internetsiz).
rem Mualliflar: Saynatov Yodgor, Raxmatullayev Sarvar
cd /d "%~dp0"
python -c "import ortools, fastapi, uvicorn, pydantic" 2>nul || (
  echo Kutubxonalar topilmadi. Bir marta internet bilan ornating: python -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo Virtual Double-Track: http://localhost:8000
start "" http://localhost:8000
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
