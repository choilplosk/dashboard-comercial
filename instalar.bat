@echo off
echo ============================================
echo  Dashboard Comercial IAF 2026 - Instalacao
echo ============================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado.
    echo Acesse https://www.python.org/downloads/
    echo IMPORTANTE: marque "Add Python to PATH" na instalacao.
    pause
    exit /b 1
)
echo [1/2] Instalando dependencias...
pip install -r requirements.txt
echo.
echo [2/2] Concluido! Execute iniciar.bat para abrir o dashboard.
pause
