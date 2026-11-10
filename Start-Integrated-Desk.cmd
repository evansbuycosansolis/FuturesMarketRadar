@echo off
setlocal
cd /d "%~dp0"
python scripts/start_integrated_desk.py
if errorlevel 1 pause
