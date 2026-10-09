@echo off
cd /d "%~dp0"
python run_all.py --tests-only %*
pause
