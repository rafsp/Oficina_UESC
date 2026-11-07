@echo off
cd /d "%~dp0"
echo === Oficina UESC: coleta de anuncios (VivaReal, ZAP, Chaves na Mao) ===
python --version || (echo Python nao encontrado. Instale em python.org e marque "Add to PATH". & pause & exit /b 1)
python -m pip install -q requests beautifulsoup4 lxml pandas matplotlib
if "%1"=="" (python oficina_coleta.py) else (python oficina_coleta.py %1)
echo.
echo Arquivos gerados nesta pasta: anuncios_limpo.csv e g1..g4.png
pause
