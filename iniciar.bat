@echo off
echo Iniciando Dashboard Comercial IAF 2026...
echo O navegador abrira automaticamente em http://localhost:8501
echo Para encerrar pressione Ctrl+C nesta janela.
echo.
streamlit run app.py --server.port 8501
