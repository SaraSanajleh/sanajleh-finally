@echo off
setlocal
cd /d "%~dp0backend\retriever"
set PY=C:\rt-venv\Scripts\python.exe

if not exist "%PY%" (
  echo Creating C:\rt-venv ...
  py -3.11 -m venv C:\rt-venv
  if errorlevel 1 (
    echo Failed to create C:\rt-venv. Install Python 3.11 first.
    pause
    exit /b 1
  )
)

"%PY%" -c "import uvicorn" 1>nul 2>nul
if errorlevel 1 (
  echo Installing retriever packages. Wait, do not close this window...
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r "%~dp0backend\retriever\requirements.txt"
  "%PY%" -c "import uvicorn" 1>nul 2>nul
  if errorlevel 1 (
    echo uvicorn still missing inside C:\rt-venv
    pause
    exit /b 1
  )
)

"%PY%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3).read()" 1>nul 2>nul
if not errorlevel 1 (
  echo Retriever is already running at http://127.0.0.1:8001
  echo Leave that window open. Do not start a second copy.
  pause
  exit /b 0
)

echo Starting retriever at http://127.0.0.1:8001
echo Keep this window open.
"%PY%" -m uvicorn api.main:app --host 127.0.0.1 --port 8001
if errorlevel 1 (
  echo If you saw port 8001 already in use, the retriever is already running. That is OK.
)
echo Retriever stopped.
pause
