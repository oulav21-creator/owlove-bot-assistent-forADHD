# Скрипт для настройки виртуального окружения с Python 3.13

Write-Host "Проверка установленных версий Python..." -ForegroundColor Cyan
Write-Host ""

# Проверяем доступные версии Python
py -0

Write-Host ""
Write-Host "Попытка найти Python 3.13..." -ForegroundColor Cyan

# Пробуем разные способы вызова Python 3.13
$python313 = $null

# Способ 1: через py launcher
try {
    $version = py -3.13 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $python313 = "py -3.13"
        Write-Host "Найден Python 3.13 через py launcher" -ForegroundColor Green
    }
} catch {}

# Способ 2: прямой путь (обычные места установки)
if (-not $python313) {
    $possiblePaths = @(
        "C:\Python313\python.exe",
        "C:\Program Files\Python313\python.exe",
        "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python313\python.exe"
    )
    
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $python313 = $path
            Write-Host "Найден Python 3.13: $path" -ForegroundColor Green
            break
        }
    }
}

if (-not $python313) {
    Write-Host ""
    Write-Host "Python 3.13 не найден автоматически." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Пожалуйста, выполните вручную:" -ForegroundColor Cyan
    Write-Host "1. Удалите старое виртуальное окружение (если есть):" -ForegroundColor White
    Write-Host "   Remove-Item -Recurse -Force venv" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Создайте новое виртуальное окружение:" -ForegroundColor White
    Write-Host "   py -3.13 -m venv venv" -ForegroundColor Gray
    Write-Host "   # или если Python 3.13 в PATH:" -ForegroundColor Gray
    Write-Host "   python3.13 -m venv venv" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. Активируйте окружение:" -ForegroundColor White
    Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "4. Установите зависимости:" -ForegroundColor White
    Write-Host "   pip install -r requirements.txt" -ForegroundColor Gray
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
Write-Host "Создание нового виртуального окружения с Python 3.13..." -ForegroundColor Cyan

if ($python313 -like "py -3.13") {
    & py -3.13 -m venv venv
} else {
    & $python313 -m venv venv
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "Виртуальное окружение создано успешно!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Теперь активируйте его:" -ForegroundColor Cyan
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "И установите зависимости:" -ForegroundColor Cyan
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Yellow
} else {
    Write-Host "Ошибка при создании виртуального окружения." -ForegroundColor Red
    Write-Host "Попробуйте выполнить вручную:" -ForegroundColor Yellow
    Write-Host "  py -3.13 -m venv venv" -ForegroundColor Gray
}
