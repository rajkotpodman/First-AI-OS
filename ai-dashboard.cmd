@echo off
echo [*] Starting AI OS Web Testing Dashboard...
start http://localhost:8888
python "%~dp0src\web_dashboard.py"
