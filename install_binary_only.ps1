# Скрипт для установки зависимостей только из бинарных пакетов (wheels)
# Используйте этот скрипт, если обычная установка не работает

Write-Host "Установка зависимостей только из предкомпилированных пакетов..." -ForegroundColor Cyan
Write-Host ""

# Проверяем, что venv активирован
if (-not $env:VIRTUAL_ENV) {
    Write-Host "ВНИМАНИЕ: Виртуальное окружение не активировано!" -ForegroundColor Yellow
    Write-Host "Активируйте его: .\venv\Scripts\Activate.ps1" -ForegroundColor White
    exit 1
}

Write-Host "Обновление pip, setuptools и wheel..." -ForegroundColor Cyan
python -m pip install --upgrade pip setuptools wheel

Write-Host ""
Write-Host "Установка зависимостей с флагом --only-binary :all:..." -ForegroundColor Cyan
Write-Host "Это заставит pip использовать только предкомпилированные пакеты" -ForegroundColor Yellow
Write-Host ""

# Устанавливаем пакеты по одному, чтобы увидеть, какой именно вызывает проблему
$packages = @(
    "aiogram==3.13.1",
    "python-dotenv==1.0.0",
    "pydantic>=2.0.0",
    "fastapi==0.115.0",
    "uvicorn[standard]==0.32.0",
    "matplotlib==3.10.0",
    "seaborn==0.13.0",
    "pandas==2.2.2",
    "requests==2.32.3",
    "google-api-python-client==2.154.0",
    "duckduckgo-search==6.1.12"
)

$failed = @()

foreach ($package in $packages) {
    Write-Host "Установка $package..." -ForegroundColor Cyan
    pip install --only-binary :all: $package
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ОШИБКА: Не удалось установить $package из бинарных пакетов" -ForegroundColor Red
        $failed += $package
        
        # Для pandas пробуем более старую версию
        if ($package -like "pandas*") {
            Write-Host "Пробуем более старую версию pandas 2.1.4..." -ForegroundColor Yellow
            pip install --only-binary :all: pandas==2.1.4
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Успешно установлен pandas 2.1.4" -ForegroundColor Green
                $failed = $failed | Where-Object { $_ -ne $package }
            }
        }
    } else {
        Write-Host "✓ Установлен: $package" -ForegroundColor Green
    }
}

if ($failed.Count -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Все зависимости установлены успешно!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Не удалось установить следующие пакеты:" -ForegroundColor Red
    foreach ($pkg in $failed) {
        Write-Host "  - $pkg" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Возможные решения:" -ForegroundColor Yellow
    Write-Host "1. Установите Visual C++ Build Tools:" -ForegroundColor White
    Write-Host "   https://visualstudio.microsoft.com/visual-cpp-build-tools/" -ForegroundColor Cyan
    Write-Host "2. Или используйте более старую версию Python (3.11)" -ForegroundColor White
}
