@echo off



setlocal



set ROOT=%~dp0..



cd /d "%ROOT%"







echo ========================================



echo  JM COLLECTION MDDR Build



echo ========================================



echo.



python scripts\build_jm_collection_mddr.py



if errorlevel 1 (



    echo.



    echo [FAILED] build script error - see mddr_build.log



    pause



    exit /b 1



)







if not exist "data\cases\jm_collection\output_mddr.docx" (



    echo.



    echo [FAILED] output_mddr.docx not found



    pause



    exit /b 1



)







echo.



echo [SUCCESS] Generated:



echo   data\cases\jm_collection\output_mddr.docx



echo.



echo --- mddr_build.log (last 8 lines) ---



powershell -NoProfile -Command "Get-Content 'data\cases\jm_collection\mddr_build.log' -Tail 8"



echo.



echo Word에서 파일을 열어 확인하세요.



pause


