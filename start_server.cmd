@echo off
chcp 65001 >nul
title Домашний библиотекарь

cd /d "%~dp0"

echo ========================================
echo    Домашний библиотекарь
echo ========================================
echo.

:: Kill existing server
echo Остановка существующего сервера...
taskkill /f /im python.exe 2>nul

:: Check database
if not exist "library.db" (
    echo Создание базы данных...
    python reset_db.py
) else (
    echo База данных найдена.
)

:: Start server
echo.
echo Запуск сервера...
echo Откройте: http://localhost:8000
echo.
echo Для остановки нажмите Ctrl+C
echo ========================================

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
