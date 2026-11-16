@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo 古物商対応・物販管理Webアプリを起動しています...
python -m streamlit run app.py
pause
