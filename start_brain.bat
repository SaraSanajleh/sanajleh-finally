@echo off
setlocal
cd /d "%~dp0"
echo Starting Brain at http://127.0.0.1:8000
echo Keep this window open.
py -3 -m uvicorn app.main:app --reload --reload-exclude "case_capture/^*" --reload-exclude "^*.json" --host 127.0.0.1 --port 8000
echo Brain stopped.
pause
