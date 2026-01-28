#!/bin/bash
# Скрипт для проверки всех возможных источников BOT_TOKEN

echo "=== ПРОВЕРКА ВСЕХ ИСТОЧНИКОВ BOT_TOKEN ==="
echo ""

echo "1. Проверка .env файла в рабочей директории:"
if [ -f ~/botfocus/.env ]; then
    echo "   Файл существует: ~/botfocus/.env"
    echo "   Содержимое BOT_TOKEN:"
    grep BOT_TOKEN ~/botfocus/.env | head -1
    echo "   Полный путь: $(readlink -f ~/botfocus/.env)"
    echo "   Размер файла: $(stat -c%s ~/botfocus/.env) байт"
else
    echo "   ❌ Файл НЕ найден: ~/botfocus/.env"
fi
echo ""

echo "2. Проверка .env файла в /root/botfocus:"
if [ -f /root/botfocus/.env ]; then
    echo "   Файл существует: /root/botfocus/.env"
    echo "   Содержимое BOT_TOKEN:"
    grep BOT_TOKEN /root/botfocus/.env | head -1
    echo "   Полный путь: $(readlink -f /root/botfocus/.env)"
    echo "   Размер файла: $(stat -c%s /root/botfocus/.env) байт"
else
    echo "   ❌ Файл НЕ найден: /root/botfocus/.env"
fi
echo ""

echo "3. Проверка systemd service файла:"
if [ -f /etc/systemd/system/bot.service ]; then
    echo "   Файл существует: /etc/systemd/system/bot.service"
    echo "   Environment переменные:"
    grep -i "BOT_TOKEN\|Environment" /etc/systemd/system/bot.service || echo "   Нет Environment переменных"
else
    echo "   ❌ Файл НЕ найден: /etc/systemd/system/bot.service"
fi
echo ""

echo "4. Проверка переменных окружения в текущей shell:"
if [ -n "$BOT_TOKEN" ]; then
    echo "   BOT_TOKEN установлен в shell: ${BOT_TOKEN:0:20}..."
else
    echo "   BOT_TOKEN НЕ установлен в shell"
fi
echo ""

echo "5. Проверка всех .env файлов в системе (поиск):"
find /root /home -name ".env" -type f 2>/dev/null | head -10
echo ""

echo "6. Проверка переменных окружения systemd для bot.service:"
systemctl show bot.service --property=Environment 2>/dev/null || echo "   Не удалось получить информацию"
echo ""

echo "7. Проверка рабочей директории из systemd service:"
systemctl show bot.service --property=WorkingDirectory 2>/dev/null || echo "   Не удалось получить информацию"
echo ""

echo "8. Проверка ExecStart из systemd service:"
systemctl show bot.service --property=ExecStart 2>/dev/null || echo "   Не удалось получить информацию"
echo ""

echo "9. Проверка содержимого .env файла (hex dump первых 200 байт):"
if [ -f /root/botfocus/.env ]; then
    head -c 200 /root/botfocus/.env | xxd | head -20
fi
echo ""

echo "10. Проверка кодировки .env файла:"
if [ -f /root/botfocus/.env ]; then
    file /root/botfocus/.env
    echo "   Первые 100 символов (raw):"
    head -c 100 /root/botfocus/.env | od -c | head -10
fi
echo ""

echo "=== КОНЕЦ ПРОВЕРКИ ==="
