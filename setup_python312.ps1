# Скрипт для настройки виртуального окружения с Python 3.12

Write-Host "Проверка установленных версий Python..." -ForegroundColor Cyan
Write-Host ""

# Проверяем доступные версии Python
py -0

Write-Host ""
Write-Host "Попытка найти Python 3.12..." -ForegroundColor Cyan

# Пробуем разные способы вызова Python 3.12
$python312 = $null

# Способ 1: через py launcher
try {
    $version = py -3.12 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $python312 = "py -3.12"
        Write-Host "Найден Python 3.12 через py launcher" -ForegroundColor Green
    }
} catch {}

# Способ 2: прямой путь (обычные места установки)
if (-not $python312) {
    $possiblePaths = @(
        "C:\Python312\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe"
    )
    
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $python312 = $path
            Write-Host "Найден Python 3.12: $path" -ForegroundColor Green
            break
        }
    }
}

if (-not $python312) {
    Write-Host ""
    Write-Host "Python 3.12 не найден автоматически." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Пожалуйста, установите Python 3.12:" -ForegroundColor Cyan
    Write-Host "1. Скачайте с https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "2. При установке отметьте 'Add Python to PATH'" -ForegroundColor White
    Write-Host "3. Запустите этот скрипт снова" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "Удаление старого виртуального окружения (если есть)..." -ForegroundColor Cyan
if (Test-Path "venv") {
    Remove-Item -Recurse -Force venv
    Write-Host "Старое окружение удалено." -ForegroundColor Green
} else {
    Write-Host "Старое окружение не найдено." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Создание нового виртуального окружения с Python 3.12..." -ForegroundColor Cyan

if ($python312 -like "py -3.12") {
    & py -3.12 -m venv venv
} else {
    & $python312 -m venv venv
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "Виртуальное окружение создано успешно!" -ForegroundColor Green
} else {
    Write-Host "Ошибка при создании виртуального окружения." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Активация виртуального окружения..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Виртуальное окружение активировано!" -ForegroundColor Green
} else {
    Write-Host "Ошибка активации. Попробуйте вручную: .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Обновление pip, setuptools и wheel..." -ForegroundColor Cyan
python -m pip install --upgrade pip setuptools wheel

if ($LASTEXITCODE -eq 0) {
    Write-Host "Инструменты обновлены!" -ForegroundColor Green
} else {
    Write-Host "Ошибка при обновлении инструментов." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Установка зависимостей из requirements.txt..." -ForegroundColor Cyan
Write-Host "Сначала пробуем установить только бинарные пакеты..." -ForegroundColor Yellow

# Пробуем сначала с --only-binary
pip install --only-binary :all: -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Не удалось установить только бинарные пакеты." -ForegroundColor Yellow
    Write-Host "Пробуем установить без ограничений (может потребоваться компилятор)..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Установка завершена успешно!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Для активации окружения в будущем используйте:" -ForegroundColor Cyan
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "Для запуска бота:" -ForegroundColor Cyan
    Write-Host "  python bot.py" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Ошибка при установке зависимостей." -ForegroundColor Red
    Write-Host "Проверьте логи выше для деталей." -ForegroundColor Yellow
    exit 1
}
