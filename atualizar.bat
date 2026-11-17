@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo Warumby Properties - Atualizacao v0.3.4 local
echo IMPORTANTE: feche o servidor e faca backup antes de continuar.
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado. Criando agora...
  python -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py makemigrations core
if errorlevel 1 goto erro
python manage.py migrate
if errorlevel 1 goto erro

echo.
echo Atualizacao concluida.
echo Seus dados em db.sqlite3, media e backups nao foram apagados.
echo Execute iniciar_servidor.bat para abrir o sistema.
echo.
pause
exit /b 0

:erro
echo.
echo ERRO durante a atualizacao. Nao inicie osistema antes de verificar a mensagem acima.
echo Seu backup permanece intacto.
pause
exit /b 1
