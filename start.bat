@echo off
setlocal
cd /d "%~dp0"
python server.py
if errorlevel 1 (
  echo.
  echo Qwen bridge stopped with an error.
  pause
)
endlocal
