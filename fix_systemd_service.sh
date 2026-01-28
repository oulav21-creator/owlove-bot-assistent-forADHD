#!/bin/bash
# Скрипт для удаления Environment переменных из systemd service файла

SERVICE_FILE="/etc/systemd/system/bot.service"

echo "=== ИСПРАВЛЕНИЕ SYSTEMD SERVICE ФАЙЛА ==="
echo ""

if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Файл $SERVICE_FILE не найден!"
    exit 1
fi

echo "Текущее содержимое service файла:"
echo "---"
cat "$SERVICE_FILE"
echo "---"
echo ""

# Создаем резервную копию
cp "$SERVICE_FILE" "${SERVICE_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
echo "✓ Резервная копия создана"

# Удаляем все строки с Environment="BOT_TOKEN=..."
# Используем sed для удаления строк
sed -i '/^[[:space:]]*Environment="BOT_TOKEN=/d' "$SERVICE_FILE"

# Также удаляем, если BOT_TOKEN в одной строке с другими Environment
sed -i 's/Environment="[^"]*BOT_TOKEN=[^"]*"//g' "$SERVICE_FILE"
sed -i 's/BOT_TOKEN=[^" ]*//g' "$SERVICE_FILE"

# Удаляем пустые строки Environment
sed -i '/^[[:space:]]*Environment="[^"]*"$/d' "$SERVICE_FILE"

# Очищаем лишние пробелы
sed -i 's/Environment="[[:space:]]*"/Environment="/g' "$SERVICE_FILE"

echo ""
echo "Обновленное содержимое service файла:"
echo "---"
cat "$SERVICE_FILE"
echo "---"
echo ""

# Проверяем, остались ли BOT_TOKEN
if grep -q "BOT_TOKEN" "$SERVICE_FILE"; then
    echo "⚠️  ВНИМАНИЕ: В файле все еще есть упоминания BOT_TOKEN!"
    echo "   Нужно отредактировать вручную:"
    echo "   nano $SERVICE_FILE"
else
    echo "✓ Все упоминания BOT_TOKEN удалены из service файла"
fi

echo ""
echo "=== СЛЕДУЮЩИЕ ШАГИ ==="
echo "1. Перезагрузите systemd: systemctl daemon-reload"
echo "2. Перезапустите бота: systemctl restart bot"
echo "3. Проверьте логи: journalctl -u bot -n 50 --no-pager"
