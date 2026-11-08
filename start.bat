@echo off
echo ========================================
echo   Telegram Survey Bot - Quick Start
echo ========================================
echo.

REM Проверка существования venv
if not exist "venv\" (
    echo [1/3] Создаю виртуальное окружение...
    python -m venv venv
    if errorlevel 1 (
        echo ОШИБКА: Не удалось создать venv
        echo Установите Python с python.org
        pause
        exit /b 1
    )
    echo Готово!
    echo.
)

REM Активация venv и установка зависимостей
echo [2/3] Устанавливаю зависимости...
call venv\Scripts\activate.bat
pip install -q --upgrade pip
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ОШИБКА: Не удалось установить зависимости
    pause
    exit /b 1
)
echo Готово!
echo.

REM Проверка .env файла
if not exist ".env" (
    echo [!] Файл .env не найден
    echo.
    echo Создайте файл .env и добавьте:
    echo BOT_TOKEN=ваш_токен_от_BotFather
    echo ADMIN_PASSWORD=ваш_пароль
    echo.
    pause
    exit /b 1
)

REM Запуск бота
echo [3/3] Запускаю бота...
echo.
python main.py

pause
