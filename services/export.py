"""
Сервис для экспорта данных в CSV.
"""

import csv
import io
from typing import List, Dict, Any
from datetime import datetime


def export_sessions_to_csv(sessions: List[Dict[str, Any]]) -> str:
    """
    Экспортирует сессии в CSV формат.
    
    Args:
        sessions: Список сессий
    
    Returns:
        CSV строка
    """
    if not sessions:
        return "date,domain,task_type,planned_minutes,actual_minutes,status,focus_status,description,created_at\n"
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'date', 'domain', 'task_type', 'planned_minutes', 'actual_minutes',
        'status', 'focus_status', 'description', 'created_at'
    ])
    
    writer.writeheader()
    for session in sessions:
        writer.writerow({
            'date': session.get('date', ''),
            'domain': session.get('domain', ''),
            'task_type': session.get('task_type', ''),
            'planned_minutes': session.get('planned_minutes', ''),
            'actual_minutes': session.get('actual_minutes', ''),
            'status': session.get('status', ''),
            'focus_status': session.get('focus_status', ''),
            'description': session.get('description', ''),
            'created_at': session.get('created_at', '')
        })
    
    return output.getvalue()


def export_english_to_csv(phrases: List[Dict[str, Any]], reviews: List[Dict[str, Any]]) -> str:
    """
    Экспортирует прогресс по английскому в CSV.
    
    Args:
        phrases: Список фраз
        reviews: Список повторений
    
    Returns:
        CSV строка
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'phrase_en', 'phrase_ru', 'success_count', 'fail_count',
        'interval_days', 'last_reviewed', 'next_review'
    ])
    
    writer.writeheader()
    for phrase in phrases:
        writer.writerow({
            'phrase_en': phrase.get('phrase_en', ''),
            'phrase_ru': phrase.get('phrase_ru', ''),
            'success_count': phrase.get('success_count', 0),
            'fail_count': phrase.get('fail_count', 0),
            'interval_days': phrase.get('interval_days', 1),
            'last_reviewed': phrase.get('last_reviewed', ''),
            'next_review': phrase.get('next_review', '')
        })
    
    return output.getvalue()


def export_sleep_to_csv(sleep_records: List[Dict[str, Any]]) -> str:
    """
    Экспортирует данные о сне в CSV.
    
    Args:
        sleep_records: Список записей сна
    
    Returns:
        CSV строка
    """
    if not sleep_records:
        return "date,sleep_start,sleep_end,duration_minutes,created_at\n"
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'date', 'sleep_start', 'sleep_end', 'duration_minutes', 'created_at'
    ])
    
    writer.writeheader()
    for record in sleep_records:
        writer.writerow({
            'date': record.get('date', ''),
            'sleep_start': record.get('sleep_start', ''),
            'sleep_end': record.get('sleep_end', ''),
            'duration_minutes': record.get('duration_minutes', ''),
            'created_at': record.get('created_at', '')
        })
    
    return output.getvalue()
