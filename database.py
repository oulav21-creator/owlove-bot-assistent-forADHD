
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


class Database:
    
    def __init__(self, db_path: str = "naparnik.db"):
        self.db_path = db_path
        self._init_db()
        self._migrate_add_user_id()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица сессий фокуса (с поддержкой многопользовательности)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS focus_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                date TEXT NOT NULL,
                direction TEXT NOT NULL,
                duration INTEGER NOT NULL,
                focus_status TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица разгрузок головы
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS brain_dumps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                date TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица заметок об обучении
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                date TEXT NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица детального трекинга сессий (v1.1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detailed_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                date TEXT NOT NULL,
                domain TEXT NOT NULL,
                task_type TEXT NOT NULL,
                planned_minutes INTEGER NOT NULL,
                actual_minutes INTEGER,
                status TEXT NOT NULL,
                focus_status TEXT,
                description TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица SRS для английского (v1.1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS english_srs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                phrase_en TEXT NOT NULL,
                phrase_ru TEXT NOT NULL,
                example TEXT,
                interval_days INTEGER DEFAULT 1,
                last_reviewed TEXT,
                next_review TEXT,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                ease_factor REAL DEFAULT 2.5,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, phrase_en)
            )
        """)
        
        # Таблица истории изучения английского (v1.1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS english_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                phrase_id INTEGER NOT NULL,
                user_answer TEXT,
                is_correct INTEGER NOT NULL,
                reviewed_at TEXT NOT NULL,
                FOREIGN KEY (phrase_id) REFERENCES english_srs(id)
            )
        """)
        
        # Таблица сна (v1.1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sleep_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                date TEXT NOT NULL,
                sleep_start TEXT NOT NULL,
                sleep_end TEXT,
                duration_minutes INTEGER,
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица планов тренировок на неделю
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workout_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                day_of_week INTEGER NOT NULL,
                exercises TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, day_of_week)
            )
        """)
        
        # Таблица выполнения тренировок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workout_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                date TEXT NOT NULL,
                day_of_week INTEGER NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица неправильных глаголов (общая для всех пользователей - справочник)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS irregular_verbs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verb_form1 TEXT NOT NULL UNIQUE,
                verb_form2 TEXT NOT NULL,
                verb_form3 TEXT NOT NULL,
                translation TEXT NOT NULL,
                example_form2 TEXT,
                example_form3 TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица задач для сессий фокуса
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS focus_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                task_name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица для отслеживания первого использования и уведомлений (per-user)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                first_session_date TEXT,
                last_heatmap_notification_date TEXT,
                last_sleep_chart_notification_date TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица для изучения слов с SRS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                word TEXT NOT NULL,
                explanation TEXT NOT NULL,
                translation TEXT NOT NULL,
                ease_factor REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 1,
                repetitions INTEGER DEFAULT 0,
                next_review_date TEXT,
                last_review_date TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Индексы для производительности
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_detailed_sessions_date ON detailed_sessions(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_detailed_sessions_domain ON detailed_sessions(domain)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_english_srs_next_review ON english_srs(next_review)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sleep_records_date ON sleep_records(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workout_completions_date ON workout_completions(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workout_completions_day ON workout_completions(day_of_week)")
        
        # Индексы для user_id (для быстрой фильтрации по пользователю)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_sessions_user ON focus_sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_brain_dumps_user ON brain_dumps(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_notes_user ON learning_notes(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_detailed_sessions_user ON detailed_sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_english_srs_user ON english_srs(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sleep_records_user ON sleep_records(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workout_plans_user ON workout_plans(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workout_completions_user ON workout_completions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_tasks_user ON focus_tasks(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocabulary_words_user ON vocabulary_words(user_id)")
        
        conn.commit()
        conn.close()
    
    def _migrate_add_user_id(self):
        """Миграция: добавление user_id в существующие таблицы для многопользовательской поддержки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Список таблиц, которым нужен user_id
        tables_to_migrate = [
            'focus_sessions',
            'brain_dumps', 
            'learning_notes',
            'detailed_sessions',
            'english_srs',
            'english_reviews',
            'sleep_records',
            'workout_plans',
            'workout_completions',
            'focus_tasks',
            'vocabulary_words'
        ]
        
        for table in tables_to_migrate:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0")
                print(f"Миграция: добавлен user_id в таблицу {table}")
            except sqlite3.OperationalError:
                pass  # Колонка уже существует
        
        conn.commit()
        conn.close()
    
    def add_focus_session(
        self,
        user_id: int,
        direction: str,
        duration: int,
        focus_status: str,
        description: Optional[str] = None
    ) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO focus_sessions (user_id, date, direction, duration, focus_status, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, today, direction, duration, focus_status, description, now)
        )
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return session_id
    
    def get_today_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute(
            "SELECT * FROM focus_sessions WHERE user_id = ? AND date = ? ORDER BY created_at DESC",
            (user_id, today)
        )
        
        sessions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return sessions
    
    def add_brain_dump(self, user_id: int, content: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO brain_dumps (user_id, date, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, today, content, now)
        )
        
        dump_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return dump_id
    
    def add_learning_note(self, user_id: int, note: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO learning_notes (user_id, date, note, created_at) VALUES (?, ?, ?, ?)",
            (user_id, today, note, now)
        )
        
        note_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return note_id
    
    def get_all_brain_dumps(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM brain_dumps WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        
        dumps = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return dumps
    
    def get_brain_dump_by_id(self, user_id: int, dump_id: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM brain_dumps WHERE user_id = ? AND id = ?",
            (user_id, dump_id)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def update_brain_dump(self, user_id: int, dump_id: int, content: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE brain_dumps SET content = ? WHERE user_id = ? AND id = ?",
            (content, user_id, dump_id)
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_brain_dump(self, user_id: int, dump_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM brain_dumps WHERE user_id = ? AND id = ?",
            (user_id, dump_id)
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def get_all_learning_notes(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM learning_notes WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        
        notes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return notes
    
    def get_learning_note_by_id(self, user_id: int, note_id: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM learning_notes WHERE user_id = ? AND id = ?",
            (user_id, note_id)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def update_learning_note(self, user_id: int, note_id: int, note: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE learning_notes SET note = ? WHERE user_id = ? AND id = ?",
            (note, user_id, note_id)
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_learning_note(self, user_id: int, note_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM learning_notes WHERE user_id = ? AND id = ?",
            (user_id, note_id)
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    # ========== Детальный трекинг сессий (v1.1) ==========
    
    def add_detailed_session(
        self,
        user_id: int,
        domain: str,
        task_type: str,
        planned_minutes: int,
        actual_minutes: Optional[int] = None,
        status: str = "completed",
        focus_status: Optional[str] = None,
        description: Optional[str] = None
    ) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO detailed_sessions (user_id, date, domain, task_type, planned_minutes, actual_minutes, status, focus_status, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, today, domain, task_type, planned_minutes, actual_minutes, status, focus_status, description, now)
        )
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return session_id
    
    def get_detailed_sessions(
        self,
        user_id: int,
        domain: Optional[str] = None,
        task_type: Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM detailed_sessions WHERE user_id = ? AND date >= date('now', '-' || ? || ' days')"
        params = [user_id, days]
        
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if task_type:
            query += " AND task_type = ?"
            params.append(task_type)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        sessions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return sessions
    
    def get_average_focus_duration(self, user_id: int, domain: str, task_type: str) -> Optional[float]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT AVG(actual_minutes) FROM detailed_sessions WHERE user_id = ? AND domain = ? AND task_type = ? AND status = 'completed' AND actual_minutes IS NOT NULL",
            (user_id, domain, task_type)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    
    # ========== SRS для английского (v1.1) ==========
    
    def add_english_phrase(
        self,
        user_id: int,
        phrase_en: str,
        phrase_ru: str,
        example: Optional[str] = None
    ) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        next_review = datetime.now().isoformat()
        
        try:
            cursor.execute(
                "INSERT INTO english_srs (user_id, phrase_en, phrase_ru, example, next_review, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, phrase_en, phrase_ru, example, next_review, now)
            )
            phrase_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return phrase_id
        except sqlite3.IntegrityError:
            # Фраза уже существует для этого пользователя
            conn.close()
            return 0
    
    def get_phrase_for_review(self, user_id: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute(
            "SELECT * FROM english_srs WHERE user_id = ? AND next_review <= ? ORDER BY next_review ASC LIMIT 1",
            (user_id, now)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def update_phrase_review(
        self,
        user_id: int,
        phrase_id: int,
        is_correct: bool,
        user_answer: Optional[str] = None
    ):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Получаем текущие данные фразы
        cursor.execute(
            "SELECT interval_days, success_count, fail_count, ease_factor FROM english_srs WHERE user_id = ? AND id = ?",
            (user_id, phrase_id)
        )
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return
        
        # Преобразуем значения в числа (на случай, если они строки)
        interval_days_current = float(result[0]) if result[0] is not None else 1.0
        success_count_current = int(result[1]) if result[1] is not None else 0
        fail_count_current = int(result[2]) if result[2] is not None else 0
        ease_factor_current = float(result[3]) if result[3] is not None else 2.5
        
        # Обновляем статистику
        if is_correct:
            success_count = success_count_current + 1
            fail_count = fail_count_current
            ease_factor = min(ease_factor_current + 0.15, 2.5)  # Увеличиваем ease factor
            interval_days = max(1, int(interval_days_current * ease_factor))
        else:
            success_count = success_count_current
            fail_count = fail_count_current + 1
            ease_factor = max(1.3, ease_factor_current - 0.2)  # Уменьшаем ease factor
            interval_days = 1  # Сбрасываем интервал
        
        next_review = (datetime.now() + timedelta(days=interval_days)).isoformat()
        
        # Обновляем фразу
        cursor.execute(
            "UPDATE english_srs SET interval_days = ?, last_reviewed = ?, next_review = ?, success_count = ?, fail_count = ?, ease_factor = ? WHERE user_id = ? AND id = ?",
            (interval_days, now, next_review, success_count, fail_count, ease_factor, user_id, phrase_id)
        )
        
        cursor.execute(
            "INSERT INTO english_reviews (user_id, phrase_id, user_answer, is_correct, reviewed_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, phrase_id, user_answer, 1 if is_correct else 0, now)
        )
        
        conn.commit()
        conn.close()
    
    def get_all_english_phrases(self, user_id: int) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM english_srs WHERE user_id = ? ORDER BY phrase_en", (user_id,))
        phrases = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return phrases
    
    # ========== Трекинг сна (v1.1) ==========
    
    def add_sleep_start(self, user_id: int, sleep_start_time: Optional[datetime] = None) -> int:
        """Добавляет запись начала сна. Если sleep_start_time не указан, используется текущее время."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if sleep_start_time is None:
            sleep_start_time = datetime.now()
        
        today = sleep_start_time.strftime("%Y-%m-%d")
        now = datetime.now().isoformat()
        sleep_start_iso = sleep_start_time.isoformat()
        
        cursor.execute(
            "INSERT INTO sleep_records (user_id, date, sleep_start, created_at) VALUES (?, ?, ?, ?)",
            (user_id, today, sleep_start_iso, now)
        )
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return record_id
    
    def complete_sleep(self, user_id: int, record_id: int) -> Optional[int]:
        """Завершает запись сна. Возвращает длительность в минутах или None при ошибке."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute("SELECT sleep_start FROM sleep_records WHERE user_id = ? AND id = ?", (user_id, record_id))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return None
        
        sleep_start = datetime.fromisoformat(result[0])
        sleep_end = datetime.now()
        duration = int((sleep_end - sleep_start).total_seconds() / 60)
        
        cursor.execute(
            "UPDATE sleep_records SET sleep_end = ?, duration_minutes = ? WHERE user_id = ? AND id = ?",
            (now, duration, user_id, record_id)
        )
        
        conn.commit()
        conn.close()
        
        return duration
    
    def get_sleep_records(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM sleep_records WHERE user_id = ? AND date >= date('now', '-' || ? || ' days') ORDER BY created_at DESC",
            (user_id, days)
        )
        
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return records
    
    def get_average_sleep(self, user_id: int, days: int = 7) -> Optional[float]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT AVG(duration_minutes) FROM sleep_records WHERE user_id = ? AND date >= date('now', '-' || ? || ' days') AND duration_minutes IS NOT NULL",
            (user_id, days)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    
    def get_latest_sleep_record(self, user_id: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM sleep_records WHERE user_id = ? AND sleep_end IS NULL ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def has_completed_sleep_today(self, user_id: int) -> bool:
        """Есть ли сегодня хотя бы одна завершённая запись сна."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            "SELECT 1 FROM sleep_records WHERE user_id = ? AND date = ? AND sleep_end IS NOT NULL LIMIT 1",
            (user_id, today)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def delete_latest_sleep_record(self, user_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM sleep_records WHERE user_id = ? AND sleep_end IS NULL ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        result = cursor.fetchone()
        
        if result:
            record_id = result[0]
            cursor.execute("DELETE FROM sleep_records WHERE user_id = ? AND id = ?", (user_id, record_id))
            conn.commit()
            conn.close()
            return True
        
        conn.close()
        return False
    
    def delete_all_sleep_records(self, user_id: int) -> bool:
        """Удаляет все записи о сне для пользователя."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM sleep_records WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.close()
            return False

    # Методы для тренировок
    def set_workout_plan(self, user_id: int, day_of_week: int, exercises: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        # Проверяем, существует ли уже план для этого пользователя и дня
        cursor.execute(
            "SELECT id, created_at FROM workout_plans WHERE user_id = ? AND day_of_week = ?",
            (user_id, day_of_week)
        )
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute(
                "UPDATE workout_plans SET exercises = ?, updated_at = ? WHERE user_id = ? AND day_of_week = ?",
                (exercises, now, user_id, day_of_week)
            )
        else:
            cursor.execute(
                "INSERT INTO workout_plans (user_id, day_of_week, exercises, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, day_of_week, exercises, now, now)
            )
        
        conn.commit()
        conn.close()
        return True
    
    def get_workout_plan(self, user_id: int, day_of_week: int) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT exercises FROM workout_plans WHERE user_id = ? AND day_of_week = ?", (user_id, day_of_week))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def get_all_workout_plans(self, user_id: int) -> list:
        """Возвращает список планов в формате [{'day_of_week': int, 'exercises': str}, ...]"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT day_of_week, exercises FROM workout_plans WHERE user_id = ?", (user_id,))
        results = cursor.fetchall()
        conn.close()
        
        return [{'day_of_week': row[0], 'exercises': row[1]} for row in results]
    
    def delete_workout_plan(self, user_id: int, day_of_week: int) -> bool:
        """Удалить план тренировки на конкретный день"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM workout_plans WHERE user_id = ? AND day_of_week = ?",
            (user_id, day_of_week)
        )
        
        conn.commit()
        conn.close()
        return True
    
    def mark_workout_completed(self, user_id: int, date: str, day_of_week: int, completed: bool = True) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        # Проверяем, существует ли уже запись
        cursor.execute(
            "SELECT id FROM workout_completions WHERE user_id = ? AND date = ? AND day_of_week = ?",
            (user_id, date, day_of_week)
        )
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute(
                "UPDATE workout_completions SET completed = ? WHERE user_id = ? AND date = ? AND day_of_week = ?",
                (1 if completed else 0, user_id, date, day_of_week)
            )
        else:
            cursor.execute(
                "INSERT INTO workout_completions (user_id, date, day_of_week, completed, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, date, day_of_week, 1 if completed else 0, now)
            )
        
        conn.commit()
        conn.close()
        return True
    
    def get_workout_completions(self, user_id: int, days: int = 14) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM workout_completions WHERE user_id = ? AND date >= date('now', '-' || ? || ' days') ORDER BY date DESC",
            (user_id, days)
        )
        
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records
    
    # Методы для неправильных глаголов
    def add_irregular_verb(
        self,
        form1: str,
        form2: str,
        form3: str,
        translation: str,
        example_form2: Optional[str] = None,
        example_form3: Optional[str] = None
    ) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        try:
            cursor.execute(
                "INSERT INTO irregular_verbs (verb_form1, verb_form2, verb_form3, translation, example_form2, example_form3, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (form1, form2, form3, translation, example_form2, example_form3, now)
            )
            
            verb_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return verb_id
        except sqlite3.IntegrityError:
            conn.close()
            return -1
    
    def get_all_irregular_verbs(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM irregular_verbs ORDER BY verb_form1")
        verbs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return verbs
    
    def get_irregular_verb_by_id(self, verb_id: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM irregular_verbs WHERE id = ?", (verb_id,))
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    # Методы для задач сессий фокуса
    def add_focus_task(self, user_id: int, task_name: str, description: Optional[str] = None) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO focus_tasks (user_id, task_name, description, created_at) VALUES (?, ?, ?, ?)",
            (user_id, task_name, description, now)
        )
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id
    
    def get_all_focus_tasks(self, user_id: int) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM focus_tasks WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tasks
    
    def get_focus_task_by_id(self, user_id: int, task_id: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM focus_tasks WHERE user_id = ? AND id = ?", (user_id, task_id))
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def update_focus_task(self, user_id: int, task_id: int, task_name: str, description: Optional[str] = None) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE focus_tasks SET task_name = ?, description = ? WHERE user_id = ? AND id = ?",
            (task_name, description, user_id, task_id)
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def delete_focus_task(self, user_id: int, task_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM focus_tasks WHERE user_id = ? AND id = ?", (user_id, task_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    # Методы для отслеживания первого использования и уведомлений (per-user)
    def set_first_session_date(self, user_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Проверяем, есть ли уже запись для этого пользователя
        cursor.execute("SELECT id, first_session_date FROM user_metadata WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(
                "INSERT INTO user_metadata (user_id, first_session_date, created_at) VALUES (?, ?, ?)",
                (user_id, today, now)
            )
        elif not exists[1]:  # first_session_date is NULL
            cursor.execute(
                "UPDATE user_metadata SET first_session_date = ? WHERE user_id = ?",
                (today, user_id)
            )
        
        conn.commit()
        conn.close()
        return True
    
    def get_first_session_date(self, user_id: int) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT first_session_date FROM user_metadata WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    
    def get_days_since_first_session(self, user_id: int) -> Optional[int]:
        first_date = self.get_first_session_date(user_id)
        if not first_date:
            return None
        
        try:
            first = datetime.fromisoformat(first_date + "T00:00:00")
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            days = (today - first).days
            return days
        except:
            return None
    
    def mark_heatmap_notification_sent(self, user_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()
        
        cursor.execute("SELECT id FROM user_metadata WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(
                "INSERT INTO user_metadata (user_id, last_heatmap_notification_date, created_at) VALUES (?, ?, ?)",
                (user_id, today, now)
            )
        else:
            cursor.execute(
                "UPDATE user_metadata SET last_heatmap_notification_date = ? WHERE user_id = ?",
                (today, user_id)
            )
        
        conn.commit()
        conn.close()
        return True
    
    def get_last_heatmap_notification_date(self, user_id: int) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT last_heatmap_notification_date FROM user_metadata WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    
    def mark_sleep_chart_notification_sent(self, user_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()
        
        cursor.execute("SELECT id FROM user_metadata WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(
                "INSERT INTO user_metadata (user_id, last_sleep_chart_notification_date, created_at) VALUES (?, ?, ?)",
                (user_id, today, now)
            )
        else:
            cursor.execute(
                "UPDATE user_metadata SET last_sleep_chart_notification_date = ? WHERE user_id = ?",
                (today, user_id)
            )
        
        conn.commit()
        conn.close()
        return True
    
    def get_last_sleep_chart_notification_date(self, user_id: int) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT last_sleep_chart_notification_date FROM user_metadata WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    
    def get_all_users(self) -> List[int]:
        """Получает список всех user_id из user_metadata"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT user_id FROM user_metadata WHERE user_id IS NOT NULL")
        results = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in results]
    
    # Методы для изучения слов с SRS
    def add_vocabulary_word(self, user_id: int, word: str, explanation: str, translation: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        today = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute(
            "INSERT INTO vocabulary_words (user_id, word, explanation, translation, next_review_date, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, word, explanation, translation, today, now)
        )
        
        word_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return word_id
    
    def get_all_vocabulary_words(self, user_id: int) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM vocabulary_words WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_vocabulary_word_by_id(self, user_id: int, word_id: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM vocabulary_words WHERE user_id = ? AND id = ?", (user_id, word_id))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_words_for_review(self, user_id: int) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Получаем слова, которые нужно повторить сегодня или ранее
        # Приоритет: слова с ошибками (низкий ease_factor) показываем чаще
        cursor.execute(
            "SELECT * FROM vocabulary_words WHERE user_id = ? AND (next_review_date <= ? OR next_review_date IS NULL) ORDER BY CASE WHEN repetitions = 0 THEN 1 WHEN ease_factor < 2.0 THEN 2 ELSE 3 END, next_review_date ASC",
            (user_id, today)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_word_review(self, user_id: int, word_id: int, success: bool) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        today = datetime.now()
        
        # Получаем текущие данные слова
        word_data = self.get_vocabulary_word_by_id(user_id, word_id)
        if not word_data:
            conn.close()
            return False
        
        ease_factor = float(word_data.get('ease_factor', 2.5))
        interval_days = int(word_data.get('interval_days', 1))
        repetitions = int(word_data.get('repetitions', 0))
        
        if success:
            # Успешное повторение - увеличиваем интервал и ease_factor
            if repetitions == 0:
                interval_days = 1
            elif repetitions == 1:
                interval_days = 6
            else:
                interval_days = int(interval_days * ease_factor)
            
            ease_factor = max(1.3, ease_factor + 0.1 - (5 - 3) * 0.08)
            repetitions += 1
        else:
            # Ошибка - сбрасываем интервал и уменьшаем ease_factor
            interval_days = 1
            repetitions = 0
            ease_factor = max(1.3, ease_factor - 0.2)
        
        next_review = (today + timedelta(days=interval_days)).strftime("%Y-%m-%d")
        
        cursor.execute(
            "UPDATE vocabulary_words SET ease_factor = ?, interval_days = ?, repetitions = ?, next_review_date = ?, last_review_date = ? WHERE user_id = ? AND id = ?",
            (ease_factor, interval_days, repetitions, next_review, now, user_id, word_id)
        )
        
        update_success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return update_success
    
    def delete_vocabulary_word(self, user_id: int, word_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM vocabulary_words WHERE user_id = ? AND id = ?", (user_id, word_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def export_vocabulary_to_csv(self, user_id: int) -> str:
        import csv
        import io
        
        words = self.get_all_vocabulary_words(user_id)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовки
        writer.writerow(['word', 'explanation', 'translation', 'ease_factor', 'interval_days', 'repetitions', 'next_review_date'])
        
        # Данные
        for word in words:
            writer.writerow([
                word.get('word', ''),
                word.get('explanation', ''),
                word.get('translation', ''),
                word.get('ease_factor', 2.5),
                word.get('interval_days', 1),
                word.get('repetitions', 0),
                word.get('next_review_date', '')
            ])
        
        return output.getvalue()
    
    def import_vocabulary_from_csv(self, user_id: int, csv_content: str) -> int:
        import csv
        import io
        
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            print(f"Ошибка при чтении CSV: {e}")
            return 0
        
        count = 0
        
        for row in reader:
            word = (row.get('word', '') or row.get('Word', '') or row.get('WORD', '') or 
                   row.get('en', '') or row.get('english', '')).strip()
            
            explanation = (row.get('explanation', '') or row.get('Explanation', '') or 
                          row.get('explanation_en', '') or row.get('example', '') or 
                          row.get('Example', '')).strip()
            
            translation = (row.get('translation', '') or row.get('Translation', '') or 
                          row.get('translation_ru', '') or row.get('ru', '') or 
                          row.get('russian', '') or row.get('Russian', '')).strip()
            
            if word:
                try:
                    if not explanation:
                        explanation = word
                    if not translation:
                        translation = ''
                    
                    self.add_vocabulary_word(user_id, word, explanation, translation)
                    count += 1
                except Exception as e:
                    print(f"Ошибка при добавлении слова '{word}': {e}")
                    pass
        
        return count
    
    def delete_all_stats(self, user_id: int) -> bool:
        """Удаляет всю статистику для конкретного пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM focus_sessions WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM detailed_sessions WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM sleep_records WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM workout_plans WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM workout_completions WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM brain_dumps WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM learning_notes WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM focus_tasks WHERE user_id = ?", (user_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"Ошибка при удалении статистики: {e}")
            return False