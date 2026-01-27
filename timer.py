"""
Модуль для управления таймерами сессий фокуса.
Использует asyncio для асинхронной работы таймеров.
"""

import asyncio
from typing import Callable, Optional
from datetime import datetime


class FocusTimer:
    """Класс для управления таймером сессии фокуса."""
    
    def __init__(self, duration_minutes: int = 20):
        """
        Инициализация таймера.
        
        Args:
            duration_minutes: Длительность сессии в минутах
        """
        self.duration_minutes = duration_minutes
        self.duration_seconds = duration_minutes * 60
        self.start_time: Optional[datetime] = None
        self.task: Optional[asyncio.Task] = None
        self.callback: Optional[Callable] = None
        self.is_paused: bool = False
        self.paused_at: Optional[datetime] = None
        self.paused_seconds: int = 0  # Сколько секунд уже прошло до паузы
    
    async def start(self, callback: Callable):
        """
        Запустить таймер.
        
        Args:
            callback: Функция, которая будет вызвана по истечении времени
        """
        self.start_time = datetime.now()
        self.callback = callback
        
        # Отменяем предыдущий таймер, если он был
        if self.task and not self.task.done():
            self.task.cancel()
        
        # Создаем новую задачу таймера
        self.task = asyncio.create_task(self._timer())
    
    async def _timer(self):
        """Внутренний метод таймера."""
        try:
            await asyncio.sleep(self.duration_seconds)
            if self.callback:
                await self.callback()
        except asyncio.CancelledError:
            # Таймер был отменен
            pass
    
    def cancel(self):
        """Отменить таймер."""
        if self.task and not self.task.done():
            self.task.cancel()
    
    def is_running(self) -> bool:
        """
        Проверить, работает ли таймер.
        
        Returns:
            True если таймер активен
        """
        return self.task is not None and not self.task.done()
    
    def pause(self):
        """Поставить таймер на паузу."""
        if not self.is_paused:
            self.is_paused = True
            self.paused_at = datetime.now()
    
    def resume(self):
        """Возобновить таймер."""
        if self.is_paused and self.paused_at:
            # Вычисляем сколько секунд прошло во время паузы
            pause_duration = (datetime.now() - self.paused_at).total_seconds()
            self.paused_seconds += int(pause_duration)
            self.is_paused = False
            self.paused_at = None
