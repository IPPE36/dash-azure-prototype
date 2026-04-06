@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo [ERROR] .venv not found at "%PYTHON_EXE%".
  echo Please create the virtual environment first.
  exit /b 1
)

"%PYTHON_EXE%" "%SCRIPT_DIR%ml\scripts\train_all.py"
