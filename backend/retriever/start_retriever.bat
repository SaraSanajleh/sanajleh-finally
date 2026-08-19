@echo off
REM Run from Command Prompt:  cd backend\retriever  then  start_retriever.bat
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_retriever.ps1"
pause
