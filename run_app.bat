@echo off
setlocal

:: Ir a la carpeta donde está este .bat
set "APP_DIR=%~dp0"
pushd "%APP_DIR%"

title Guiones App - Streamlit (global Python)
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

:: Asegura que Python pueda importar 'ui' desde la raiz del proyecto
set "PYTHONPATH=%APP_DIR%"

:: Config de servidor (ajusta si quieres)
set "PORT=8501"

echo ==========================================
echo  Guiones App - Iniciando Streamlit
echo  Carpeta: %APP_DIR%
echo  URL:     http://localhost:%PORT%/
echo ==========================================
echo.

:: 1) Intentar usar el ejecutable "streamlit" del PATH
where streamlit >nul 2>nul
if %ERRORLEVEL%==0 (
  streamlit run "ui\main_app.py"  --server.port=%PORT%
  goto :end
)

:: 2) Si no existe "streamlit" en PATH, usar "python -m streamlit"
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python -m streamlit run "ui\main_app.py" --server.port=%PORT%
  goto :end
)

echo [ERROR] No se encontro "streamlit" ni "python" en el PATH del sistema.
echo Asegurate de tener Python y Streamlit instalados globalmente.
echo Por ejemplo:  pip install streamlit
echo.

:end
set "RC=%ERRORLEVEL%"
popd
endlocal

:: Mantener ventana abierta solo si hubo error
if not "%RC%"=="0" (
  echo.
  echo [ERROR] Streamlit cerro con codigo %RC%.
  pause
)
