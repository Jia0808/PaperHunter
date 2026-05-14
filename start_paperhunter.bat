@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=python"

where python >nul 2>nul
if errorlevel 1 (
  if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PYTHON=%LocalAppData%\Programs\Python\Python312\python.exe"
  )
)

if exist "%ROOT%venv\Lib\site-packages" (
  set "PYTHONPATH=%ROOT%venv\Lib\site-packages"
)

cd /d "%ROOT%"
"%PYTHON%" app.py

endlocal
