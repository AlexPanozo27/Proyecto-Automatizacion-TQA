@echo off
cd /d %~dp0
echo Instalando la plataforma de automatizacion TQA...
python -m pip install -r requirements.txt || goto :error
python -m playwright install chromium || goto :error
if not exist .env copy config\config.example.env .env
echo.
echo Listo. Revise el archivo .env (correo SMTP) y luego ejecute iniciar.bat
pause
exit /b 0
:error
echo Hubo un error en la instalacion.
pause
