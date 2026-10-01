@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "EDITOR_PYTHON=%~dp0.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "EDITOR_PYTHON=%~dp0..\.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python was not found. Install Python and enable "Add Python to PATH".
        pause
        exit /b 1
    )
    python -m venv .venv
    if errorlevel 1 (
        echo Could not create the Python environment.
        pause
        exit /b 1
    )
    set "EDITOR_PYTHON=%~dp0.venv\Scripts\python.exe"
)

"%EDITOR_PYTHON%" -c "import pymupdf" >nul 2>nul
if errorlevel 1 (
    echo Installing required packages...
    "%EDITOR_PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Package installation failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

echo Open http://127.0.0.1:8000 in your browser.
echo Keep this window open. Press Ctrl+C to stop the app.
"%EDITOR_PYTHON%" pdf_editor.py
if errorlevel 1 (
    echo The application stopped. If port 8000 is already in use, close the existing app first.
    pause
)
