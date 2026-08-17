@echo off

setlocal

set ROOT=%~dp0..

cd /d "%ROOT%"



echo ========================================

echo  JM COLLECTION MDSR Build

echo ========================================

echo.



python scripts\build_jm_collection_mdsr.py

if errorlevel 1 (

    echo.

    echo [FAILED] build script error - see build.log

    pause

    exit /b 1

)



if not exist "data\cases\jm_collection\output_mdsr.docx" (

    echo.

    echo [FAILED] output_mdsr.docx not found

    pause

    exit /b 1

)



echo.

echo [SUCCESS] Generated:

echo   data\cases\jm_collection\output_mdsr.docx

echo.

echo --- build.log (last 8 lines) ---

powershell -NoProfile -Command "Get-Content 'data\cases\jm_collection\build.log' -Tail 8"

echo.

echo Word에서 파일을 열어 확인하세요.

pause

