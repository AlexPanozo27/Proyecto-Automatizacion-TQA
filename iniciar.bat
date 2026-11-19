@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
if exist .venv\Scripts\python.exe set PY=.venv\Scripts\python.exe
if not exist .env (echo Falta el archivo .env: ejecute primero instalar.bat & pause & exit /b 1)
echo Iniciando QA Lab en http://127.0.0.1:8080 ... no cierre esta ventana mientras lo use.
start "" http://127.0.0.1:8080
%PY% app.py
pause
