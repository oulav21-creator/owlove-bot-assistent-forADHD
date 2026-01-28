#!/bin/bash
# Wrapper скрипт для запуска бота
# Загружает .env файл и запускает bot.py
# Это гарантирует, что переменные окружения из systemd не переопределят .env

# Переходим в директорию бота
cd "$(dirname "$0")" || exit 1

# Путь к .env файлу
ENV_FILE="$(pwd)/.env"

# Проверяем существование .env файла
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env файл не найден: $ENV_FILE"
    exit 1
fi

echo "DEBUG: Загружаем переменные из .env файла: $ENV_FILE"

# Очищаем все переменные окружения, которые могут быть установлены systemd
unset BOT_TOKEN
unset WEBHOOK_URL
unset PORT
unset YOUTUBE_API_KEY

# Загружаем переменные из .env файла
# Используем set -a для автоматического экспорта всех переменных
set -a
source "$ENV_FILE"
set +a

# Проверяем, что BOT_TOKEN загружен
if [ -z "$BOT_TOKEN" ]; then
    echo "ERROR: BOT_TOKEN не найден в .env файле"
    echo "DEBUG: Содержимое .env файла:"
    cat "$ENV_FILE"
    exit 1
fi

echo "DEBUG: BOT_TOKEN загружен: ${BOT_TOKEN:0:20}... (длина: ${#BOT_TOKEN})"
echo "DEBUG: WEBHOOK_URL: ${WEBHOOK_URL:-не установлен}"
echo "DEBUG: PORT: ${PORT:-не установлен}"

# Активируем виртуальное окружение, если оно существует
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "DEBUG: Виртуальное окружение активировано"
fi

# Запускаем бота
echo "DEBUG: Запускаем bot.py..."
exec python bot.py
