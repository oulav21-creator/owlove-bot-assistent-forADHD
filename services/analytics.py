"""
Сервис для аналитики и визуализации данных.
Генерирует графики через matplotlib.
"""

import io
from datetime import datetime, timedelta
from typing import List, Dict, Any
import matplotlib
matplotlib.use('Agg')  # Для работы без GUI
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['font.size'] = 10


def generate_productivity_heatmap(sessions: List[Dict[str, Any]]) -> io.BytesIO:
    """
    Генерирует тепловую карту продуктивности по часам дня и дням недели.
    
    Args:
        sessions: Список сессий с полями created_at и status
    
    Returns:
        BytesIO объект с изображением
    """
    if not sessions:
        # Создаем пустой график
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'Нет данных для отображения', 
                ha='center', va='center', fontsize=16)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close()
        buf.seek(0)
        return buf
    
    # Подготовка данных
    data = []
    for session in sessions:
        try:
            dt = datetime.fromisoformat(session['created_at'])
            hour = dt.hour
            weekday = dt.weekday()  # 0 = Monday, 6 = Sunday
            is_completed = 1 if session.get('status') == 'completed' else 0
            data.append({'hour': hour, 'weekday': weekday, 'success': is_completed})
        except:
            continue
    
    if not data:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'Нет данных для отображения', 
                ha='center', va='center', fontsize=16)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close()
        buf.seek(0)
        return buf
    
    df = pd.DataFrame(data)
    
    # Создаем сводную таблицу
    pivot = df.groupby(['weekday', 'hour'])['success'].mean().reset_index()
    pivot_table = pivot.pivot(index='weekday', columns='hour', values='success')
    pivot_table = pivot_table.fillna(0)
    
    # Создаем график
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Тепловая карта
    sns.heatmap(
        pivot_table,
        annot=True,
        fmt='.2f',
        cmap='YlOrRd',
        cbar_kws={'label': 'Успешность'},
        ax=ax,
        vmin=0,
        vmax=1
    )
    
    # Настройка осей
    weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    ax.set_yticklabels([weekdays[i] for i in range(7)], rotation=0)
    ax.set_xlabel('Час дня', fontsize=12)
    ax.set_ylabel('День недели', fontsize=12)
    ax.set_title('Тепловая карта продуктивности', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    # Сохраняем в буфер
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    buf.seek(0)
    
    return buf


def generate_stats_charts(sessions: List[Dict[str, Any]]) -> io.BytesIO:
    """
    Генерирует графики статистики: сессии по дням, средняя длительность, процент завершённых.
    
    Args:
        sessions: Список сессий
    
    Returns:
        BytesIO объект с изображением
    """
    if not sessions:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'Нет данных для отображения', 
                ha='center', va='center', fontsize=16)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close()
        buf.seek(0)
        return buf
    
    # Подготовка данных
    data = []
    for session in sessions:
        try:
            dt = datetime.fromisoformat(session['created_at'])
            date = dt.date()
            duration = session.get('actual_minutes') or session.get('duration', 0)
            is_completed = session.get('status') == 'completed'
            data.append({
                'date': date,
                'duration': duration,
                'completed': is_completed
            })
        except:
            continue
    
    if not data:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'Нет данных для отображения', 
                ha='center', va='center', fontsize=16)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close()
        buf.seek(0)
        return buf
    
    df = pd.DataFrame(data)
    
    # Создаем 3 подграфика
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    # 1. Сессии по дням
    sessions_by_date = df.groupby('date').size()
    axes[0].bar(sessions_by_date.index, sessions_by_date.values, color='steelblue')
    axes[0].set_title('Количество сессий по дням', fontweight='bold')
    axes[0].set_xlabel('Дата')
    axes[0].set_ylabel('Количество сессий')
    axes[0].tick_params(axis='x', rotation=45)
    axes[0].grid(True, alpha=0.3)
    
    # 2. Средняя длительность
    avg_duration = df.groupby('date')['duration'].mean()
    axes[1].plot(avg_duration.index, avg_duration.values, marker='o', color='green', linewidth=2)
    axes[1].set_title('Средняя длительность сессий (минуты)', fontweight='bold')
    axes[1].set_xlabel('Дата')
    axes[1].set_ylabel('Минуты')
    axes[1].tick_params(axis='x', rotation=45)
    axes[1].grid(True, alpha=0.3)
    
    # 3. Процент завершённых
    completion_rate = df.groupby('date')['completed'].mean() * 100
    axes[2].bar(completion_rate.index, completion_rate.values, color='orange')
    axes[2].set_title('Процент завершённых сессий', fontweight='bold')
    axes[2].set_xlabel('Дата')
    axes[2].set_ylabel('Процент (%)')
    axes[2].tick_params(axis='x', rotation=45)
    axes[2].grid(True, alpha=0.3)
    axes[2].set_ylim(0, 100)
    
    plt.tight_layout()
    
    # Сохраняем в буфер
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    buf.seek(0)
    
    return buf


def generate_sleep_chart(sleep_records: List[Dict[str, Any]]) -> io.BytesIO:
    """
    Генерирует график сна за неделю/месяц.
    
    Args:
        sleep_records: Список записей сна
    
    Returns:
        BytesIO объект с изображением
    """
    if not sleep_records:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'Нет данных о сне', 
                ha='center', va='center', fontsize=16)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close()
        buf.seek(0)
        return buf
    
    # Подготовка данных
    data = []
    for record in sleep_records:
        if record.get('duration_minutes'):
            try:
                dt = datetime.fromisoformat(record['created_at'])
                date = dt.date()
                duration_hours = record['duration_minutes'] / 60
                data.append({'date': date, 'duration': duration_hours})
            except:
                continue
    
    if not data:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'Нет данных о сне', 
                ha='center', va='center', fontsize=16)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close()
        buf.seek(0)
        return buf
    
    df = pd.DataFrame(data)
    df = df.sort_values('date')
    
    # Создаем график
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.bar(df['date'], df['duration'], color='navy', alpha=0.7)
    ax.axhline(y=7, color='green', linestyle='--', linewidth=2, label='Рекомендуемый минимум (7ч)')
    ax.axhline(y=6, color='orange', linestyle='--', linewidth=2, label='Минимум (6ч)')
    
    ax.set_title('График сна', fontsize=14, fontweight='bold')
    ax.set_xlabel('Дата')
    ax.set_ylabel('Длительность (часы)')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    plt.tight_layout()
    
    # Сохраняем в буфер
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    buf.seek(0)
    
    return buf
