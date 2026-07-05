@echo off
setlocal
cd /d "%~dp0"
echo Starting BiliClaw Backend Server...
set "PYTHONPATH=%CD%\src"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
"%PYTHON%" -m openbiliclaw.cli serve-api --host 0.0.0.0 --port 8420
pause
