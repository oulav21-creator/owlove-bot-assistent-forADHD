# Диагностика проблемы с BOT_TOKEN

## Проблема
Бот использует старый токен, хотя в `.env` файле установлен новый.

## Решение

### Шаг 1: Загрузите диагностический скрипт на сервер

```bash
# На вашем компьютере (PowerShell):
cd c:\Users\nenad\OneDrive\Desktop\botFocus
git add check_token_sources.sh bot.py
git commit -m "Add token diagnostic script and fix .env loading"
git push origin main
```

### Шаг 2: На сервере выполните диагностику

```bash
# Подключитесь к серверу через SSH
ssh root@v3032501.hosted-by-vdsina.ru

# Перейдите в директорию бота
cd ~/botfocus

# Обновите код
git pull

# Сделайте скрипт исполняемым
chmod +x check_token_sources.sh

# Запустите диагностику
./check_token_sources.sh
```

### Шаг 3: Проверьте systemd service файл

```bash
# Просмотрите содержимое service файла
cat /etc/systemd/system/bot.service

# Проверьте, нет ли там Environment переменных с BOT_TOKEN
grep -i "BOT_TOKEN\|Environment" /etc/systemd/system/bot.service
```

### Шаг 4: Если в systemd service есть Environment переменные

**ВАЖНО:** Если в `/etc/systemd/system/bot.service` есть строка типа:
```
Environment="BOT_TOKEN=старый_токен"
```

То нужно:
1. Удалить эту строку из service файла
2. Перезагрузить systemd: `systemctl daemon-reload`
3. Перезапустить бота: `systemctl restart bot`

### Шаг 5: Проверьте все .env файлы

```bash
# Найдите все .env файлы
find /root /home -name ".env" -type f 2>/dev/null

# Проверьте содержимое каждого
cat /root/botfocus/.env
cat ~/botfocus/.env  # если отличается от /root/botfocus
```

### Шаг 6: Убедитесь, что .env файл сохранен правильно

```bash
# Проверьте содержимое .env файла
cat /root/botfocus/.env

# Убедитесь, что токен правильный (новый: AAHH-FKUJ...)
# Если токен старый (AAEw_xTbB...), отредактируйте файл:
nano /root/botfocus/.env

# Сохраните: Ctrl+O, Enter, Ctrl+X
```

### Шаг 7: Перезапустите бота с новым кодом

```bash
# Перезагрузите systemd (если меняли service файл)
systemctl daemon-reload

# Перезапустите бота
systemctl restart bot

# Проверьте логи
journalctl -u bot -n 100 --no-pager
```

### Шаг 8: Что искать в логах

После перезапуска в логах должно быть:

```
DEBUG: BOT_TOKEN ДО загрузки .env: ...
DEBUG: .env файл загружен из /root/botfocus/.env (override=True)
DEBUG: Токен из файла .env (raw): 8320459330:AAHH-FKUJ... (длина: 46)
DEBUG: BOT_TOKEN ПОСЛЕ загрузки .env: 8320459330:AAHH-FKUJ...
DEBUG: Токен прочитан НАПРЯМУЮ из файла .env
DEBUG: Токен валиден! Бот: @your_bot_username
✓ Webhook установлен через API: https://...
```

Если токен все еще старый в логах, значит проблема в одном из мест выше.
