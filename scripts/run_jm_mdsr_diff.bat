@echo off
setlocal
cd /d "%~dp0.."
python scripts\build_jm_collection_mdsr.py
if errorlevel 1 exit /b 1
python scripts\mdsr_filled_vs_output_diff.py
exit /b %errorlevel%
