@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo Erstelle lokale Python-Umgebung...
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv ".venv"
    ) else (
        python --version >nul 2>&1
        if errorlevel 1 (
            echo Python wurde nicht gefunden. Bitte Python 3.11 oder neuer installieren.
            pause
            exit /b 1
        )
        python -m venv ".venv"
    )
    if errorlevel 1 goto :error
)

"%VENV_PY%" -c "import sys; sys.exit(sys.version_info < (3, 11))"
if errorlevel 1 (
    echo Python 3.11 oder neuer ist fuer die installierten Pakete erforderlich.
    goto :error
)

echo Pruefe und installiere benoetigte Pakete...
"%VENV_PY%" -m pip install --disable-pip-version-check -r "requirements.txt"
if errorlevel 1 goto :error

if /i "%~1"=="--check" (
    echo Alle Pakete sind bereit.
    exit /b 0
)

echo Starte DICOM Reader...
"%VENV_PY%" "app.py" %*
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Start fehlgeschlagen. Bitte die Fehlermeldung oben pruefen.
pause
exit /b 1
