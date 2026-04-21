@echo off
chcp 65001 >nul
title Home Library

cd /d "%~dp0"

echo ========================================
echo    Home Library
echo ========================================
echo.

:: Kill existing server
echo Stopping existing server...
taskkill /f /im python.exe 2>nul

:: Check database
if not exist "library.db" (
    echo Creating database...
    python reset_db.py
) else (
    echo Database found.
)

:: Start server
echo.
echo Starting server...
echo Open: http://localhost:8000
echo.
echo To stop press Ctrl+C
echo ========================================

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
