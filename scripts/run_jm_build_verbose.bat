@echo off
setlocal
set ROOT=%~dp0..
set OUT=%TEMP%\jm_build_status.txt
echo START %DATE% %TIME% > "%OUT%"
cd /d "%ROOT%"
python scripts\build_jm_collection_mdsr.py >> "%OUT%" 2>&1
echo BUILD_EXIT %ERRORLEVEL% >> "%OUT%"
python scripts\mdsr_gap_analysis_run.py >> "%OUT%" 2>&1
echo GAP_EXIT %ERRORLEVEL% >> "%OUT%"
echo FINISH %DATE% %TIME% >> "%OUT%"
if exist "%ROOT%\data\cases\jm_collection\output_mdsr.docx" (
    echo OUTPUT_OK >> "%OUT%"
) else (
    echo OUTPUT_MISSING >> "%OUT%"
)
