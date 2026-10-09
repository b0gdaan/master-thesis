@echo off
cd /d "%~dp0"
python run_all.py --skip-latex --skip-tests %*
pause
