# Исправление проблемы с токеном

## Проблема
Systemd service файл содержит старый токен в Environment переменных, который переопределяет `.env` файл.

## Решение

### Вариант 1: Автоматическое исправление (рекомендуется)

```bash
# На сервере:
cd ~/botfocus
git pull
chmod +x fix_systemd_service.sh
./fix_systemd_service.sh
systemctl daemon-reload
systemctl restart bot
journalctl -u bot -n 50 --no-pager
```

### Вариант 2: Ручное исправление

```bash
# 1. Откройте service файл
nano /etc/systemd/system/bot.service

# 2. Найдите и УДАЛИТЕ ВСЕ строки, содержащие BOT_TOKEN:
#    Environment="BOT_TOKEN=..."
#    или
#    Environment="PATH=... BOT_TOKEN=..."

# 3. Сохраните: Ctrl+O, Enter, Ctrl+X

# 4. Перезагрузите systemd
systemctl daemon-reload

# 5. Перезапустите бота
systemctl restart bot

# 6. Проверьте логи
journalctl -u bot -n 50 --no-pager
```

### Вариант 3: Полностью пересоздать service файл

```bash
# 1. Остановите бота
systemctl stop bot

# 2. Удалите старый service файл
rm /etc/systemd/system/bot.service

# 3. Создайте новый service файл
nano /etc/systemd/system/bot.service
```

Вставьте следующее содержимое (БЕЗ Environment переменных для BOT_TOKEN):

```ini
[Unit]
Description=Telegram Bot Напарник
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/botfocus
Environment="PATH=/root/botfocus/venv/bin"
ExecStart=/root/botfocus/venv/bin/python /root/botfocus/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**ВАЖНО:** НЕ добавляйте `Environment="BOT_TOKEN=..."` - бот будет читать токен из `.env` файла!

```bash
# 4. Сохраните: Ctrl+O, Enter, Ctrl+X

# 5. Перезагрузите systemd
systemctl daemon-reload

# 6. Включите автозапуск
systemctl enable bot

# 7. Запустите бота
systemctl start bot

# 8. Проверьте логи
journalctl -u bot -n 50 --no-pager
```

## Проверка результата

В логах должно быть:
```
DEBUG: Токен из переменных окружения: 8320459330:AAEw_xTbB... (старый)
DEBUG: Токен из файла .env: 8320459330:AAHH-FKUJ... (новый)
DEBUG: Используется токен из файла .env (принудительно)
DEBUG: Токен валиден! Бот: @your_bot_username
✓ Webhook установлен через API: https://...
```

## Нужен ли systemd?

**ДА, systemd нужен** для:
- Автозапуска бота при перезагрузке сервера
- Автоматического перезапуска при сбоях
- Управления процессом (start/stop/restart/status)

**НО** не нужно хранить токен в systemd service файле - бот сам читает его из `.env` файла.
