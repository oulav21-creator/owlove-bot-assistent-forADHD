# Использование wrapper скрипта для запуска бота

## Проблема
Systemd устанавливает переменные окружения ДО запуска Python, и они переопределяют `.env` файл.

## Решение
Используем bash wrapper скрипт, который загружает `.env` файл и запускает Python. Systemd запускает скрипт, а не напрямую Python.

## Установка

### Шаг 1: Запушьте изменения

```powershell
cd c:\Users\nenad\OneDrive\Desktop\botFocus
git add bot.py start_bot.sh bot.service.clean USE_WRAPPER_SCRIPT.md
git commit -m "Add wrapper script to load .env before Python startup"
git push origin main
```

### Шаг 2: На сервере установите wrapper скрипт

```bash
cd ~/botfocus
git pull

# Сделайте скрипт исполняемым
chmod +x start_bot.sh

# Проверьте, что скрипт работает
./start_bot.sh
# (Остановите через Ctrl+C после проверки)
```

### Шаг 3: Обновите systemd service файл

```bash
# Остановите бота
systemctl stop bot

# Создайте резервную копию старого service файла
cp /etc/systemd/system/bot.service /etc/systemd/system/bot.service.backup

# Скопируйте новый service файл
cp ~/botfocus/bot.service.clean /etc/systemd/system/bot.service

# ИЛИ отредактируйте вручную:
nano /etc/systemd/system/bot.service
```

Вставьте следующее содержимое:

```ini
[Unit]
Description=Telegram Bot Напарник
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/botfocus
# НЕ устанавливаем Environment переменные здесь
# Они будут загружены из .env через start_bot.sh
ExecStart=/root/botfocus/start_bot.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**ВАЖНО:** 
- `ExecStart` теперь указывает на `/root/botfocus/start_bot.sh`, а не на `python bot.py`
- НЕТ строк `Environment="BOT_TOKEN=..."` - все переменные загружаются из `.env` через скрипт

```bash
# Сохраните: Ctrl+O, Enter, Ctrl+X

# Перезагрузите systemd
systemctl daemon-reload

# Включите автозапуск (если еще не включен)
systemctl enable bot

# Запустите бота
systemctl start bot

# Проверьте статус
systemctl status bot

# Проверьте логи
journalctl -u bot -n 50 --no-pager
```

## Как это работает

1. **Systemd** запускает `start_bot.sh`
2. **start_bot.sh**:
   - Переходит в директорию бота
   - Очищает все переменные окружения (unset)
   - Загружает переменные из `.env` файла через `source`
   - Активирует виртуальное окружение
   - Запускает `python bot.py`
3. **bot.py** получает переменные из окружения, которые были загружены скриптом из `.env`

## Преимущества

✅ Systemd не может переопределить переменные - они загружаются скриптом  
✅ Все переменные в одном месте - `.env` файл  
✅ Легко отлаживать - можно запустить скрипт вручную  
✅ Работает независимо от конфигурации systemd  

## Проверка

В логах должно быть:
```
DEBUG: Загружаем переменные из .env файла: /root/botfocus/.env
DEBUG: BOT_TOKEN загружен: 8320459330:AAHH-FKUJ... (длина: 46)
DEBUG: WEBHOOK_URL: https://v3032501.hosted-by-vdsina.ru/webhook
DEBUG: Запускаем bot.py...
DEBUG: Токен из переменных окружения: 8320459330:AAHH-FKUJ...
DEBUG: Токен из файла .env: 8320459330:AAHH-FKUJ...
DEBUG: Используется токен из файла .env (принудительно)
DEBUG: Токен валиден! Бот: @your_bot_username
✓ Webhook установлен
```

## Отладка

Если что-то не работает:

```bash
# Запустите скрипт вручную для проверки
cd ~/botfocus
./start_bot.sh

# Проверьте права на файл
ls -la start_bot.sh
# Должно быть: -rwxr-xr-x

# Проверьте содержимое .env
cat ~/botfocus/.env

# Проверьте, что скрипт исполняемый
file start_bot.sh
# Должно быть: Bourne-Again shell script
```
