@echo off
chcp 65001 > nul
setlocal

cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo [ERRO] Ambiente virtual 'venv' nao encontrado!
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

:MENU
cls
echo ======================================================
echo           SISTEMA DE ESCALAS E ADERENCIA (WFM)       
echo ======================================================
echo 1. Iniciar Servidor FastAPI (Uvicorn Reload)
echo 2. Executar Bateria de Testes (Pytest)
echo 3. Iniciar Servidor e Abrir Swagger no Navegador
echo 4. Sair
echo ======================================================
set /p opt="Escolha uma opcao [1-4]: "

if "%opt%"=="1" goto START_SERVER
if "%opt%"=="2" goto RUN_TESTS
if "%opt%"=="3" goto START_SWAGGER
if "%opt%"=="4" goto END

echo Opcao invalida!
timeout /t 2 > nul
goto MENU

:START_SERVER
cls
echo Iniciando Uvicorn na porta 8000...
uvicorn app.main:app --reload
goto MENU

:RUN_TESTS
cls
echo Rodando Pytest...
pytest -v tests/test_adherence.py
echo.
pause
goto MENU

:START_SWAGGER
cls
echo Iniciando Uvicorn e abrindo documentacao...
start http://127.0.0.1:8000/docs
uvicorn app.main:app --reload
goto MENU

:END
exit /b 0
