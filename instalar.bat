@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  QA Lab SIBIO-RFID - instalacion (solo la primera vez)
echo ============================================================
where python >nul 2>nul || (echo No se encontro Python. Instale Python 3.11 o superior marcando "Add python.exe to PATH". & goto :error)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" || (echo Se necesita Python 3.11 o superior. & python --version & goto :error)
echo [1/4] Creando el entorno virtual .venv ...
if not exist .venv\Scripts\python.exe python -m venv .venv || goto :error
echo [2/4] Instalando librerias (requirements.txt) ...
.venv\Scripts\python -m pip install --upgrade pip >nul
.venv\Scripts\python -m pip install -r requirements.txt || goto :error
echo [3/4] Descargando el navegador Chromium de Playwright ...
.venv\Scripts\python -m playwright install chromium || goto :error
echo [4/4] Preparando el archivo de configuracion .env ...
if not exist .env (copy config\config.example.env .env >nul & echo     Se creo .env a partir de config\config.example.env) else (echo     .env ya existe: no se modifica)
echo.
echo Listo. Ahora:
echo   1. Abra .env y complete las claves demo de SIBIO y el correo SMTP (ver README, paso 3).
echo   2. Con SIBIO-RFID encendido, ejecute iniciar.bat
pause
exit /b 0
:error
echo.
echo Hubo un error en la instalacion. Revise el mensaje de arriba y la seccion "Solucion de problemas" del README.
pause
exit /b 1
