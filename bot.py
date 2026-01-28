"""
Telegram-бот «Напарник» v2.0 для личной эффективности (СДВГ).
Помогает выстраивать дисциплину через короткие сессии фокуса и простые инструменты.

Версия 2.0 включает:
- Минималистичный интерфейс (ReplyKeyboard)
- WORKOUT: тренировки, анализ нагрузки, сон
- ENG: неправильные глаголы (200 глаголов)
- ANAL: аналитика и графики
- FOCUS: сессии фокуса, разгрузка головы
- SEARCH: поиск информации (YouTube, Habr)
"""

import asyncio
import os
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
import uvicorn
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Update, ReplyKeyboardMarkup, KeyboardButton, FSInputFile, BufferedInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from database import Database
from timer import FocusTimer
from services import (
    generate_productivity_heatmap,
    generate_stats_charts,
    generate_sleep_chart,
    search_info,
    export_sessions_to_csv,
    export_english_to_csv,
    export_sleep_to_csv
)
from irregular_verbs import IRREGULAR_VERBS

# Загружаем переменные окружения из .env файла
# Используем явный путь к .env файлу для работы через systemd
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"DEBUG: .env файл загружен из {env_path}")
else:
    print(f"DEBUG: .env файл не найден по пути {env_path}")


# Состояния FSM для диалогов
class FocusStates(StatesGroup):
    """Состояния для команды /focus"""
    waiting_task_name = State()
    waiting_task_description = State()
    waiting_task_edit = State()
    waiting_focus_status = State()
    waiting_description = State()
    waiting_task_selection = State()




class VocabularyStates(StatesGroup):
    """Состояния для изучения слов"""
    waiting_word = State()
    waiting_explanation = State()
    waiting_translation = State()
    waiting_file = State()


class DumpStates(StatesGroup):
    """Состояния для команды /dump"""
    waiting_content = State()
    waiting_choice = State()
    viewing_list = State()
    editing = State()
    waiting_edit_text = State()


class EnglishStates(StatesGroup):
    """Состояния для команды /english"""
    waiting_answer = State()


class SearchStates(StatesGroup):
    """Состояния для команды /search"""
    waiting_query = State()


class SleepStates(StatesGroup):
    """Состояния для команды /sleep"""
    waiting_confirmation = State()


class WorkoutStates(StatesGroup):
    """Состояния для тренировок"""
    waiting_plan_monday = State()
    waiting_plan_tuesday = State()
    waiting_plan_wednesday = State()
    waiting_plan_thursday = State()
    waiting_plan_friday = State()
    waiting_plan_saturday = State()
    waiting_plan_sunday = State()
    editing_plan = State()


# Инициализация
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен. Создайте файл .env или установите переменную окружения.")

# Очищаем токен от пробелов и переносов строк
BOT_TOKEN = BOT_TOKEN.strip()
print(f"DEBUG: BOT_TOKEN длина: {len(BOT_TOKEN)}, первые 20 символов: {BOT_TOKEN[:20]}...")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()

# Хранилище активных таймеров (user_id -> FocusTimer)
active_timers: dict[int, FocusTimer] = {}

# Хранилище данных активных сессий (user_id -> {direction, ...})
active_sessions: dict[int, dict] = {}


# Вспомогательные функции
def get_focus_tasks_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру управления задачами для /focus"""
    buttons = [
        [InlineKeyboardButton(text="добавить задачи", callback_data="focus_add_task")],
        [InlineKeyboardButton(text="начать сессию", callback_data="focus_start_session")],
        [InlineKeyboardButton(text="редактировать задачи", callback_data="focus_edit_tasks")],
        [InlineKeyboardButton(text="удалить задачи", callback_data="focus_delete_tasks")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_focus_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_task_type_keyboard(domain: str) -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора типа задачи"""
    if domain == "QA":
        buttons = [
            [InlineKeyboardButton(text="Теория", callback_data="task_theory")],
            [InlineKeyboardButton(text="Примеры", callback_data="task_examples")],
            [InlineKeyboardButton(text="Чтение", callback_data="task_reading")]
        ]
    elif domain == "Python":
        buttons = [
            [InlineKeyboardButton(text="Теория", callback_data="task_theory")],
            [InlineKeyboardButton(text="Практика", callback_data="task_practice")]
        ]
    elif domain == "Английский":
        buttons = [
            [InlineKeyboardButton(text="Ввод", callback_data="task_input")],
            [InlineKeyboardButton(text="Повтор", callback_data="task_review")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="Теория", callback_data="task_theory")],
            [InlineKeyboardButton(text="Практика", callback_data="task_practice")]
        ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_focus_status_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора статуса фокуса"""
    buttons = [
        [InlineKeyboardButton(text="удержал", callback_data="focus_ok")],
        [InlineKeyboardButton(text="частично", callback_data="focus_partial")],
        [InlineKeyboardButton(text="потерял", callback_data="focus_lost")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создать главную клавиатуру (ReplyKeyboard)"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="WORKOUT"), KeyboardButton(text="SEARCH")],
            [KeyboardButton(text="ENG"), KeyboardButton(text="ANALYTICS")],
            [KeyboardButton(text="FOCUS")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру с кнопкой возврата в главное меню"""
    buttons = [
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_workout_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру с кнопкой возврата в меню WORKOUT"""
    buttons = [
        [InlineKeyboardButton(text="Назад", callback_data="back_to_workout")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_dump_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру с кнопкой возврата в меню 'Разгрузка головы'"""
    buttons = [
        [InlineKeyboardButton(text="Назад", callback_data="focus_dump")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_focus_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру с кнопкой возврата в меню FOCUS"""
    buttons = [
        [InlineKeyboardButton(text="Назад", callback_data="back_to_focus_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Эта функция больше не используется напрямую, 
# callback встроен в process_focus_direction


# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    # Сохраняем дату первого использования и user_id, если еще не сохранены
    first_session = db.get_first_session_date()
    if not first_session:
        db.set_first_session_date(user_id)
    
    # Получаем username или используем имя
    username = message.from_user.username
    if username:
        greeting = f"Привет @{username}, приступим?"
    else:
        # Если username нет, используем имя или "друг"
        name = message.from_user.first_name or "друг"
        greeting = f"Привет {name}, приступим?"
    
    await message.answer(
        text=greeting,
        reply_markup=get_main_keyboard()
    )


# Обработчики главного меню (ReplyKeyboard)
@dp.message(F.text == "WORKOUT")
async def cmd_workout(message: Message):
    """Обработчик кнопки WORKOUT"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Тренировки", callback_data="workout_training")],
        [InlineKeyboardButton(text="Анализ", callback_data="workout_analysis")],
        [InlineKeyboardButton(text="Сон", callback_data="workout_sleep")]
    ])
    
    # Пробуем workout.png, если нет - workout.jpg
    try:
        import os
        if os.path.exists("images/workout.png"):
            photo = FSInputFile("images/workout.png")
        else:
            photo = FSInputFile("images/workout.jpg")
        await message.answer_photo(photo=photo, reply_markup=keyboard)
    except Exception as e:
        # Если картинка не найдена, отправляем текст
        await message.answer("WORKOUT", reply_markup=keyboard)


@dp.message(F.text == "SEARCH")
async def cmd_search_main(message: Message, state: FSMContext):
    """Обработчик кнопки SEARCH"""
    try:
        photo = FSInputFile("images/search.jpeg")
        await message.answer_photo(photo=photo, caption="Что искать?", reply_markup=get_back_to_menu_keyboard())
    except Exception as e:
        await message.answer("Что искать?", reply_markup=get_back_to_menu_keyboard())
    await state.set_state(SearchStates.waiting_query)


@dp.message(F.text == "ENG")
async def cmd_eng_main(message: Message):
    """Обработчик кнопки ENG - выбор между неправильными глаголами и изучением слов"""
    try:
        photo = FSInputFile("images/eng.jpg")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Неправильные глаголы", callback_data="eng_verbs")],
            [InlineKeyboardButton(text="Учить слова", callback_data="eng_vocabulary")]
        ])
        await message.answer_photo(photo=photo, reply_markup=keyboard)
    except Exception as e:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Неправильные глаголы", callback_data="eng_verbs")],
            [InlineKeyboardButton(text="Учить слова", callback_data="eng_vocabulary")]
        ])
        await message.answer("ENG", reply_markup=keyboard)


@dp.message(F.text == "ANALYTICS")
async def cmd_anal_main(message: Message):
    """Обработчик кнопки ANALYTICS - аналитика"""
    try:
        photo = FSInputFile("images/anal.jpg")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Продуктивность", callback_data="anal_productivity")],
            [InlineKeyboardButton(text="Статистика", callback_data="anal_stats")]
        ])
        await message.answer_photo(photo=photo, reply_markup=keyboard)
    except Exception as e:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Продуктивность", callback_data="anal_productivity")],
            [InlineKeyboardButton(text="Статистика", callback_data="anal_stats")]
        ])
        await message.answer("АНАЛИТИКА", reply_markup=keyboard)


def get_focus_main_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру главного меню FOCUS"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сессия фокуса", callback_data="focus_start")],
        [InlineKeyboardButton(text="Разгрузка головы", callback_data="focus_dump")],
        [InlineKeyboardButton(text="Delete stats", callback_data="focus_delete_stats")]
    ])


@dp.message(F.text == "FOCUS")
async def cmd_focus_main(message: Message, state: FSMContext):
    """Обработчик кнопки FOCUS"""
    try:
        photo = FSInputFile("images/focus.jpg")
        keyboard = get_focus_main_keyboard()
        await message.answer_photo(photo=photo, reply_markup=keyboard)
    except Exception as e:
        keyboard = get_focus_main_keyboard()
        await message.answer("FOCUS", reply_markup=keyboard)


@dp.callback_query(F.data == "back_to_focus_main")
async def back_to_focus_main_handler(callback: CallbackQuery):
    """Обработчик возврата в главное меню FOCUS"""
    await callback.answer()
    keyboard = get_focus_main_keyboard()
    try:
        photo = FSInputFile("images/focus.jpg")
        await callback.message.answer_photo(photo=photo, reply_markup=keyboard)
    except:
        try:
            await callback.message.edit_text("FOCUS", reply_markup=keyboard)
        except:
            await callback.message.answer("FOCUS", reply_markup=keyboard)


@dp.callback_query(F.data == "back_to_focus_tasks_menu")
async def back_to_focus_tasks_menu_handler(callback: CallbackQuery):
    """Обработчик возврата в меню 'Управление задачами'"""
    await callback.answer()
    # Пытаемся отредактировать фото с кнопками управления задачами
    try:
        photo = FSInputFile("images/focus.jpg")
        await callback.message.edit_media(
            media=InputMediaPhoto(media=photo),
            reply_markup=get_focus_tasks_keyboard()
        )
    except:
        # Если не удалось отредактировать, отправляем новое фото с кнопками
        try:
            photo = FSInputFile("images/focus.jpg")
            await callback.message.answer_photo(
                photo=photo,
                reply_markup=get_focus_tasks_keyboard()
            )
        except:
            # Если фото не найдено, отправляем текст
            try:
                await callback.message.edit_text(
                    "Управление задачами:",
                    reply_markup=get_focus_tasks_keyboard()
                )
            except:
                await callback.message.answer(
                    "Управление задачами:",
                    reply_markup=get_focus_tasks_keyboard()
                )


# Обработчики callback для подразделов ENG
@dp.callback_query(F.data == "eng_verbs")
async def eng_verbs_handler(callback: CallbackQuery):
    """Обработчик неправильных глаголов"""
    await callback.answer()
    # Инициализируем базу глаголов, если пуста
    verbs = db.get_all_irregular_verbs()
    if len(verbs) < 50:
        # Загружаем глаголы
        for form1, form2, form3, translation, example2, example3 in IRREGULAR_VERBS:
            try:
                db.add_irregular_verb(form1, form2, form3, translation, example2, example3)
            except:
                pass  # Глагол уже существует
    
    # Получаем случайный глагол
    import random
    verbs = db.get_all_irregular_verbs()
    if verbs:
        verb = random.choice(verbs)
        text = f"{verb['verb_form1']} – {verb['verb_form2']} – {verb['verb_form3']}\n"
        text += f"{verb['translation']}\n\n"
        if verb.get('example_form2'):
            text += f"{verb['example_form2']}\n"
        if verb.get('example_form3'):
            text += f"{verb['example_form3']}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Дальше", callback_data="eng_next")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_eng_main")]
        ])
        # Редактируем caption фото-сообщения
        try:
            await callback.message.edit_caption(caption=text, reply_markup=keyboard)
        except:
            # Если не получилось (например, это текстовое сообщение), редактируем текст
            await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_eng_main")]
        ])
        await callback.message.edit_text("База глаголов пуста.", reply_markup=keyboard)


@dp.callback_query(F.data == "eng_next")
async def eng_next_verb(callback: CallbackQuery):
    """Следующий неправильный глагол"""
    await callback.answer()
    import random
    verbs = db.get_all_irregular_verbs()
    if verbs:
        verb = random.choice(verbs)
        text = f"{verb['verb_form1']} – {verb['verb_form2']} – {verb['verb_form3']}\n"
        text += f"{verb['translation']}\n\n"
        if verb.get('example_form2'):
            text += f"{verb['example_form2']}\n"
        if verb.get('example_form3'):
            text += f"{verb['example_form3']}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Дальше", callback_data="eng_next")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_eng_main")]
        ])
        # Редактируем caption фото-сообщения
        try:
            await callback.message.edit_caption(caption=text, reply_markup=keyboard)
        except:
            # Если не получилось (например, это текстовое сообщение), редактируем текст
            await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_eng_main")]
        ])
        try:
            await callback.message.edit_caption(caption="База глаголов пуста.", reply_markup=keyboard)
        except:
            await callback.message.edit_text("База глаголов пуста.", reply_markup=keyboard)


@dp.callback_query(F.data == "eng_vocabulary")
async def eng_vocabulary_handler(callback: CallbackQuery):
    """Обработчик меню 'Учить слова'"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить слово", callback_data="vocab_add")],
        [InlineKeyboardButton(text="Начать обучение", callback_data="vocab_start")],
        [InlineKeyboardButton(text="Удалить слова", callback_data="vocab_delete")],
        [InlineKeyboardButton(text="Загрузить файл", callback_data="vocab_upload")],
        [InlineKeyboardButton(text="Выгрузить все слова", callback_data="vocab_export")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_eng_main")]
    ])
    
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except:
        try:
            photo = FSInputFile("images/eng.jpg")
            await callback.message.answer_photo(photo=photo, reply_markup=keyboard)
        except:
            await callback.message.edit_text("Учить слова", reply_markup=keyboard)


@dp.callback_query(F.data == "back_to_eng_main")
async def back_to_eng_main(callback: CallbackQuery):
    """Возврат в главное меню ENG"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Неправильные глаголы", callback_data="eng_verbs")],
        [InlineKeyboardButton(text="Учить слова", callback_data="eng_vocabulary")]
    ])
    
    # Отправляем новое фото без caption, чтобы очистить старый текст
    try:
        photo = FSInputFile("images/eng.jpg")
        await callback.message.answer_photo(photo=photo, reply_markup=keyboard)
    except Exception:
        await callback.message.answer("ENG", reply_markup=keyboard)


@dp.callback_query(F.data == "vocab_add")
async def vocab_add_handler(callback: CallbackQuery, state: FSMContext):
    """Начать добавление слова"""
    await callback.answer()
    await state.set_state(VocabularyStates.waiting_word)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="vocab_cancel")]
    ])
    
    try:
        await callback.message.edit_caption(caption="Введи слово на английском:", reply_markup=keyboard)
    except:
        await callback.message.edit_text("Введи слово на английском:", reply_markup=keyboard)


@dp.message(VocabularyStates.waiting_word)
async def process_vocab_word(message: Message, state: FSMContext):
    """Обработка ввода слова"""
    await state.update_data(word=message.text.strip())
    await state.set_state(VocabularyStates.waiting_explanation)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="vocab_cancel")]
    ])
    
    await message.answer("Введи объяснение слова на английском:", reply_markup=keyboard)


@dp.message(VocabularyStates.waiting_explanation)
async def process_vocab_explanation(message: Message, state: FSMContext):
    """Обработка ввода объяснения"""
    await state.update_data(explanation=message.text.strip())
    await state.set_state(VocabularyStates.waiting_translation)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="vocab_cancel")]
    ])
    
    await message.answer("Введи перевод слова:", reply_markup=keyboard)


@dp.message(VocabularyStates.waiting_translation)
async def process_vocab_translation(message: Message, state: FSMContext):
    """Обработка ввода перевода и сохранение слова"""
    data = await state.get_data()
    word = data.get('word', '').strip()
    explanation = data.get('explanation', '').strip()
    translation = message.text.strip()
    
    if word and explanation and translation:
        try:
            db.add_vocabulary_word(word, explanation, translation)
            await message.answer(f"Слово '{word}' добавлено в словарь!")
            
            # Показываем меню "Учить слова" после успешного добавления
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Добавить слово", callback_data="vocab_add")],
                [InlineKeyboardButton(text="Начать обучение", callback_data="vocab_start")],
                [InlineKeyboardButton(text="Загрузить файл", callback_data="vocab_upload")],
                [InlineKeyboardButton(text="Выгрузить все слова", callback_data="vocab_export")],
                [InlineKeyboardButton(text="Назад", callback_data="back_to_eng_main")]
            ])
            
            try:
                photo = FSInputFile("images/eng.jpg")
                await message.answer_photo(photo=photo, reply_markup=keyboard)
            except:
                await message.answer("Учить слова", reply_markup=keyboard)
        except Exception as e:
            await message.answer(f"Ошибка при добавлении слова: {e}")
    else:
        await message.answer("Ошибка: не все поля заполнены.")
    
    await state.clear()


@dp.callback_query(F.data == "vocab_cancel")
async def vocab_cancel_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления слова"""
    await callback.answer()
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить слово", callback_data="vocab_add")],
        [InlineKeyboardButton(text="Начать обучение", callback_data="vocab_start")],
        [InlineKeyboardButton(text="Удалить слова", callback_data="vocab_delete")],
        [InlineKeyboardButton(text="Загрузить файл", callback_data="vocab_upload")],
        [InlineKeyboardButton(text="Выгрузить все слова", callback_data="vocab_export")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_eng_main")]
    ])
    
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except:
        try:
            photo = FSInputFile("images/eng.jpg")
            await callback.message.answer_photo(photo=photo, reply_markup=keyboard)
        except:
            await callback.message.edit_text("Учить слова", reply_markup=keyboard)


@dp.callback_query(F.data == "vocab_start")
async def vocab_start_handler(callback: CallbackQuery):
    """Начать обучение словам"""
    await callback.answer()
    
    words = db.get_words_for_review()
    
    if not words:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="eng_vocabulary")]
        ])
        try:
            await callback.message.edit_caption(caption="Нет слов для повторения. Добавь слова в словарь!", reply_markup=keyboard)
        except:
            await callback.message.edit_text("Нет слов для повторения. Добавь слова в словарь!", reply_markup=keyboard)
        return
    
    # Берем первое слово из списка (приоритет у слов с ошибками)
    word = words[0]
    
    # Показываем карточку: слово - объяснение
    text = f"**{word['word']}**\n\n{word['explanation']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перевернуть", callback_data=f"vocab_flip_{word['id']}")],
        [InlineKeyboardButton(text="Пропустить", callback_data=f"vocab_skip_{word['id']}")]
    ])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="Markdown")
    except:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("vocab_flip_"))
async def vocab_flip_handler(callback: CallbackQuery):
    """Перевернуть карточку - показать перевод"""
    await callback.answer()
    
    word_id = int(callback.data.split("_")[-1])
    word = db.get_vocabulary_word_by_id(word_id)
    
    if not word:
        await callback.message.edit_text("Слово не найдено.")
        return
    
    # Показываем перевод
    text = f"**{word['word']}**\n\n{word['translation']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Правильно", callback_data=f"vocab_correct_{word_id}")],
        [InlineKeyboardButton(text="Неправильно", callback_data=f"vocab_incorrect_{word_id}")]
    ])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="Markdown")
    except:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("vocab_correct_"))
async def vocab_correct_handler(callback: CallbackQuery):
    """Пользователь ответил правильно"""
    await callback.answer("Правильно! ✓")
    
    word_id = int(callback.data.split("_")[-1])
    db.update_word_review(word_id, success=True)
    
    # Показываем следующее слово
    words = db.get_words_for_review()
    
    if not words:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="eng_vocabulary")]
        ])
        try:
            await callback.message.edit_caption(caption="Все слова изучены! Отлично!", reply_markup=keyboard)
        except:
            await callback.message.edit_text("Все слова изучены! Отлично!", reply_markup=keyboard)
        return
    
    word = words[0]
    text = f"**{word['word']}**\n\n{word['explanation']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перевернуть", callback_data=f"vocab_flip_{word['id']}")],
        [InlineKeyboardButton(text="Пропустить", callback_data=f"vocab_skip_{word['id']}")]
    ])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="Markdown")
    except:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("vocab_incorrect_"))
async def vocab_incorrect_handler(callback: CallbackQuery):
    """Пользователь ответил неправильно"""
    await callback.answer("Неправильно. Повторим позже.")
    
    word_id = int(callback.data.split("_")[-1])
    db.update_word_review(word_id, success=False)
    
    # Показываем следующее слово (это слово будет показано чаще из-за низкого ease_factor)
    words = db.get_words_for_review()
    
    if not words:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="eng_vocabulary")]
        ])
        try:
            await callback.message.edit_caption(caption="Все слова изучены!", reply_markup=keyboard)
        except:
            await callback.message.edit_text("Все слова изучены!", reply_markup=keyboard)
        return
    
    word = words[0]
    text = f"**{word['word']}**\n\n{word['explanation']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перевернуть", callback_data=f"vocab_flip_{word['id']}")],
        [InlineKeyboardButton(text="Пропустить", callback_data=f"vocab_skip_{word['id']}")]
    ])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="Markdown")
    except:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("vocab_skip_"))
async def vocab_skip_handler(callback: CallbackQuery):
    """Пропустить слово"""
    await callback.answer()
    
    word_id = int(callback.data.split("_")[-1])
    
    # Показываем следующее слово
    words = db.get_words_for_review()
    
    # Фильтруем текущее слово
    words = [w for w in words if w['id'] != word_id]
    
    if not words:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="eng_vocabulary")]
        ])
        try:
            await callback.message.edit_caption(caption="Больше нет слов для повторения.", reply_markup=keyboard)
        except:
            await callback.message.edit_text("Больше нет слов для повторения.", reply_markup=keyboard)
        return
    
    word = words[0]
    text = f"**{word['word']}**\n\n{word['explanation']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перевернуть", callback_data=f"vocab_flip_{word['id']}")],
        [InlineKeyboardButton(text="Пропустить", callback_data=f"vocab_skip_{word['id']}")]
    ])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="Markdown")
    except:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "vocab_delete")
async def vocab_delete_handler(callback: CallbackQuery):
    """Меню удаления слов - первая страница"""
    await callback.answer()
    await show_vocab_delete_page(callback, page=0)


@dp.callback_query(F.data.startswith("vocab_delete_page_"))
async def vocab_delete_page_handler(callback: CallbackQuery):
    """Переключение страницы при удалении слов"""
    await callback.answer()
    
    try:
        page = int(callback.data.split("_")[-1])
    except:
        page = 0
    
    await show_vocab_delete_page(callback, page)


async def show_vocab_delete_page(callback: CallbackQuery, page: int = 0):
    """Показать страницу со словами для удаления"""
    words = db.get_all_vocabulary_words()
    words_per_page = 10
    
    if not words:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="eng_vocabulary")]
        ])
        try:
            await callback.message.edit_caption(caption="Словарь пуст. Нечего удалять.", reply_markup=keyboard)
        except:
            await callback.message.edit_text("Словарь пуст. Нечего удалять.", reply_markup=keyboard)
        return
    
    total_pages = (len(words) + words_per_page - 1) // words_per_page
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    # Получаем слова для текущей страницы
    start_idx = page * words_per_page
    end_idx = start_idx + words_per_page
    page_words = words[start_idx:end_idx]
    
    # Формируем текст с информацией о странице
    text = f"Выбери слово для удаления:\nСтраница {page + 1} из {total_pages}\n\n"
    keyboard_buttons = []
    
    # Добавляем слова текущей страницы
    for i, word in enumerate(page_words):
        global_idx = start_idx + i + 1
        word_text = f"{global_idx}. {word['word']} - {word['translation']}"
        if len(word_text) > 50:
            word_text = word_text[:47] + "..."
        keyboard_buttons.append([InlineKeyboardButton(
            text=word_text,
            callback_data=f"vocab_delete_word_{word['id']}"
        )])
    
    # Кнопки навигации (если больше одной страницы)
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◄", callback_data=f"vocab_delete_page_{page - 1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="►", callback_data=f"vocab_delete_page_{page + 1}"))
        
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)
    
    # Кнопка "Удалить все"
    keyboard_buttons.append([InlineKeyboardButton(
        text="Удалить все слова",
        callback_data="vocab_delete_all_confirm"
    )])
    
    # Кнопка "Назад"
    keyboard_buttons.append([InlineKeyboardButton(
        text="Назад",
        callback_data="eng_vocabulary"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except:
        await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data.startswith("vocab_delete_word_"))
async def vocab_delete_word_handler(callback: CallbackQuery):
    """Удаление одного слова"""
    await callback.answer()
    
    word_id = int(callback.data.split("_")[-1])
    word = db.get_vocabulary_word_by_id(word_id)
    
    if not word:
        await callback.message.edit_text("Слово не найдено.")
        return
    
    # Определяем текущую страницу для возврата
    # Получаем все слова и находим индекс удаленного
    all_words = db.get_all_vocabulary_words()
    word_index = None
    for i, w in enumerate(all_words):
        if w['id'] == word_id:
            word_index = i
            break
    
    current_page = 0
    if word_index is not None:
        current_page = word_index // 10
    
    # Удаляем слово
    success = db.delete_vocabulary_word(word_id)
    
    if success:
        # После удаления возвращаемся на ту же страницу (или предыдущую, если удалили последнее слово)
        # Проверяем, остались ли слова на текущей странице
        remaining_words = db.get_all_vocabulary_words()
        words_per_page = 10
        total_pages = (len(remaining_words) + words_per_page - 1) // words_per_page if remaining_words else 0
        
        # Если страница стала пустой, переходим на предыдущую
        if current_page >= total_pages and total_pages > 0:
            current_page = total_pages - 1
        
        # Если словарь пуст, возвращаемся в меню
        if not remaining_words:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="eng_vocabulary")]
            ])
            try:
                await callback.message.edit_caption(
                    caption=f"Слово '{word['word']}' удалено.\nСловарь пуст.",
                    reply_markup=keyboard
                )
            except:
                await callback.message.edit_text(f"Слово '{word['word']}' удалено.\nСловарь пуст.", reply_markup=keyboard)
        else:
            # Возвращаемся на страницу со словами
            await show_vocab_delete_page(callback, page=current_page)
    else:
        await callback.message.edit_text("Ошибка при удалении слова.")


@dp.callback_query(F.data == "vocab_delete_all_confirm")
async def vocab_delete_all_confirm_handler(callback: CallbackQuery):
    """Подтверждение удаления всех слов"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, удалить все", callback_data="vocab_delete_all")],
        [InlineKeyboardButton(text="Отмена", callback_data="vocab_delete")]
    ])
    
    try:
        await callback.message.edit_caption(
            caption="⚠️ Ты уверен? Это действие нельзя отменить!\n\nВсе слова будут удалены из словаря.",
            reply_markup=keyboard
        )
    except:
        await callback.message.edit_text(
            "⚠️ Ты уверен? Это действие нельзя отменить!\n\nВсе слова будут удалены из словаря.",
            reply_markup=keyboard
        )


@dp.callback_query(F.data == "vocab_delete_all")
async def vocab_delete_all_handler(callback: CallbackQuery):
    """Удаление всех слов"""
    await callback.answer()
    
    words = db.get_all_vocabulary_words()
    count = len(words)
    
    # Удаляем все слова
    for word in words:
        db.delete_vocabulary_word(word['id'])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="eng_vocabulary")]
    ])
    
    try:
        await callback.message.edit_caption(
            caption=f"✅ Удалено {count} слов из словаря.",
            reply_markup=keyboard
        )
    except:
        await callback.message.edit_text(f"✅ Удалено {count} слов из словаря.", reply_markup=keyboard)


@dp.callback_query(F.data == "vocab_export")
async def vocab_export_handler(callback: CallbackQuery):
    """Выгрузить все слова в CSV"""
    await callback.answer()
    
    try:
        csv_content = db.export_vocabulary_to_csv()
        
        # Отправляем файл
        from io import BytesIO
        file = BufferedInputFile(csv_content.encode('utf-8'), filename="vocabulary.csv")
        await callback.message.answer_document(document=file, caption="Все слова из словаря")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="eng_vocabulary")]
        ])
        await callback.message.answer("Файл выгружен!", reply_markup=keyboard)
    except Exception as e:
        await callback.message.answer(f"Ошибка при выгрузке: {e}")


@dp.callback_query(F.data == "vocab_upload")
async def vocab_upload_handler(callback: CallbackQuery, state: FSMContext):
    """Начать загрузку файла"""
    await callback.answer()
    await state.set_state(VocabularyStates.waiting_file)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="vocab_cancel")]
    ])
    
    try:
        await callback.message.edit_caption(
            caption="Отправь CSV файл со словами.\nФормат: word,explanation,translation\n(explanation и translation опциональны)",
            reply_markup=keyboard
        )
    except:
        await callback.message.edit_text(
            "Отправь CSV файл со словами.\nФормат: word,explanation,translation\n(explanation и translation опциональны)",
            reply_markup=keyboard
        )


@dp.message(VocabularyStates.waiting_file)
async def process_vocab_file(message: Message, state: FSMContext):
    """Обработка загрузки файла"""
    if not message.document:
        await message.answer("Пожалуйста, отправь CSV файл.")
        return
    
    try:
        # Скачиваем файл
        file = await bot.get_file(message.document.file_id)
        file_content = await bot.download_file(file.file_path)
        
        # Пробуем разные кодировки
        csv_content = None
        for encoding in ['utf-8', 'utf-8-sig', 'cp1251', 'latin-1']:
            try:
                file_content.seek(0)  # Возвращаемся в начало файла
                csv_content = file_content.read().decode(encoding)
                break
            except:
                continue
        
        if not csv_content:
            await message.answer("Ошибка: не удалось прочитать файл. Проверьте кодировку (должна быть UTF-8).")
            await state.clear()
            return
        
        # Импортируем слова
        count = db.import_vocabulary_from_csv(csv_content)
        
        if count > 0:
            await message.answer(f"Загружено {count} слов в словарь!")
        else:
            await message.answer(
                "Загружено 0 слов.\n\n"
                "Проверьте формат файла:\n"
                "• Первая строка должна содержать заголовки (word, explanation, translation)\n"
                "• Обязательно только поле 'word'\n"
                "• Поля 'explanation' и 'translation' опциональны"
            )
        
        await state.clear()
    except Exception as e:
        await message.answer(f"Ошибка при загрузке файла: {e}")
        await state.clear()


@dp.callback_query(F.data == "anal_stats")
async def anal_stats_handler(callback: CallbackQuery):
    """Обработчик аналитики - статистика"""
    await callback.answer()
    await callback.message.answer("Генерирую графики статистики...")
    
    sessions = db.get_detailed_sessions(days=14)
    if not sessions:
        await callback.message.answer("Недостаточно данных для анализа.", reply_markup=get_main_keyboard())
        return
    
    try:
        stats_buf = generate_stats_charts(sessions)
        await callback.message.answer_photo(
            photo=stats_buf,
            caption="Статистика: сессии по дням, средняя длительность, процент завершённых"
        )
    except Exception as e:
        await callback.message.answer(f"Ошибка при генерации графика: {e}", reply_markup=get_main_keyboard())


@dp.callback_query(F.data == "workout_sleep")
async def workout_sleep_handler(callback: CallbackQuery):
    """Обработчик WORKOUT → Сон"""
    await callback.answer()
    await cmd_sleep(callback, None)


@dp.callback_query(F.data == "back_to_sleep")
async def back_to_sleep_handler(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню Сон"""
    await callback.answer()
    await state.clear()
    await cmd_sleep(callback, None)


@dp.callback_query(F.data == "back_to_workout")
async def back_to_workout_handler(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню WORKOUT"""
    await callback.answer()
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Тренировки", callback_data="workout_training")],
        [InlineKeyboardButton(text="Анализ", callback_data="workout_analysis")],
        [InlineKeyboardButton(text="Сон", callback_data="workout_sleep")]
    ])
    
    try:
        photo = FSInputFile("images/workout.jpg")
        await callback.message.answer_photo(photo=photo, reply_markup=keyboard)
    except:
        try:
            photo = FSInputFile("images/workout.png")
            await callback.message.answer_photo(photo=photo, reply_markup=keyboard)
        except:
            await callback.message.answer("WORKOUT", reply_markup=keyboard)


@dp.callback_query(F.data == "focus_start")
async def focus_start_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик FOCUS → Сессия фокуса"""
    await callback.answer()
    user_id = callback.from_user.id
    
    if user_id in active_timers:
        active_timers[user_id].cancel()
        del active_timers[user_id]
    
    # Пытаемся отредактировать фото с кнопками управления задачами
    try:
        photo = FSInputFile("images/focus.jpg")
        await callback.message.edit_media(
            media=InputMediaPhoto(media=photo),
            reply_markup=get_focus_tasks_keyboard()
        )
    except:
        # Если не удалось отредактировать, отправляем новое фото с кнопками
        try:
            photo = FSInputFile("images/focus.jpg")
            await callback.message.answer_photo(
                photo=photo,
                reply_markup=get_focus_tasks_keyboard()
            )
        except:
            # Если фото не найдено, отправляем текст
            await callback.message.answer(
                "Управление задачами:",
                reply_markup=get_focus_tasks_keyboard()
            )


# Обработчики управления задачами для сессий фокуса
@dp.callback_query(F.data == "focus_add_task")
async def focus_add_task_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления задачи"""
    await callback.answer()
    try:
        await callback.message.edit_text("Введи название задачи:")
    except:
        await callback.message.answer("Введи название задачи:")
    await state.set_state(FocusStates.waiting_task_name)


@dp.message(FocusStates.waiting_task_name)
async def process_task_name(message: Message, state: FSMContext):
    """Обработка названия задачи"""
    task_name = message.text.strip() if message.text else ""
    if task_name:
        await state.update_data(task_name=task_name)
        await message.answer("Введи описание задачи (или отправь '-' чтобы пропустить):")
        await state.set_state(FocusStates.waiting_task_description)
    else:
        await message.answer("Название задачи не может быть пустым.")


@dp.message(FocusStates.waiting_task_description)
async def process_task_description(message: Message, state: FSMContext):
    """Обработка описания задачи"""
    data = await state.get_data()
    task_name = data.get("task_name")
    description = message.text.strip() if message.text else None
    
    if description == "-":
        description = None
    
    task_id = db.add_focus_task(task_name, description)
    # Отправляем фото с кнопками управления задачами
    try:
        photo = FSInputFile("images/focus.jpg")
        await message.answer_photo(
            photo=photo,
            caption=f"Задача '{task_name}' добавлена.",
            reply_markup=get_focus_tasks_keyboard()
        )
    except:
        await message.answer(f"Задача '{task_name}' добавлена.", reply_markup=get_focus_tasks_keyboard())
    await state.clear()


@dp.callback_query(F.data == "focus_start_session")
async def focus_start_session_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик начала сессии - показываем список задач"""
    await callback.answer()
    tasks = db.get_all_focus_tasks()
    
    if not tasks:
        # Пытаемся отредактировать фото с кнопками управления задачами
        try:
            photo = FSInputFile("images/focus.jpg")
            await callback.message.edit_media(
                media=InputMediaPhoto(media=photo, caption="Нет добавленных задач. Сначала добавь задачи."),
                reply_markup=get_focus_tasks_keyboard()
            )
        except:
            # Если не удалось отредактировать, отправляем новое фото с кнопками
            try:
                photo = FSInputFile("images/focus.jpg")
                await callback.message.answer_photo(
                    photo=photo,
                    caption="Нет добавленных задач. Сначала добавь задачи.",
                    reply_markup=get_focus_tasks_keyboard()
                )
            except:
                try:
                    await callback.message.edit_text(
                        "Нет добавленных задач. Сначала добавь задачи.",
                        reply_markup=get_focus_tasks_keyboard()
                    )
                except:
                    await callback.message.answer(
                        "Нет добавленных задач. Сначала добавь задачи.",
                        reply_markup=get_focus_tasks_keyboard()
                    )
        return
    
    # Формируем клавиатуру с задачами
    buttons = []
    for task in tasks:
        task_name = task['task_name']
        buttons.append([InlineKeyboardButton(
            text=task_name,
            callback_data=f"focus_task_{task['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_focus_tasks_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    try:
        await callback.message.edit_text("Выбери задачу для сессии:", reply_markup=keyboard)
    except:
        await callback.message.answer("Выбери задачу для сессии:", reply_markup=keyboard)
    
    await state.set_state(FocusStates.waiting_task_selection)


@dp.callback_query(F.data.startswith("focus_task_"), FocusStates.waiting_task_selection)
async def focus_task_selected_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора задачи - запускаем таймер"""
    await callback.answer()
    task_id = int(callback.data.split("_")[-1])
    task = db.get_focus_task_by_id(task_id)
    
    if not task:
        await callback.message.answer("Задача не найдена.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    
    # Сохраняем информацию о задаче
    await state.update_data(task_id=task_id, task_name=task['task_name'], task_description=task.get('description'))
    
    # Запускаем таймер (используем стандартную длительность 20 минут)
    user_id = callback.from_user.id
    planned_minutes = 20
    
    if user_id in active_timers:
        active_timers[user_id].cancel()
        del active_timers[user_id]
    
    timer = FocusTimer(duration_minutes=planned_minutes)
    
    # Сохраняем данные в активных сессиях
    active_sessions[user_id] = {
        "task_id": task_id,
        "task_name": task['task_name'],
        "planned_minutes": planned_minutes,
        "message_id": callback.message.message_id
    }
    
    # Кнопки для управления таймером
    timer_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пауза", callback_data="focus_pause")],
        [InlineKeyboardButton(text="Отменить", callback_data="focus_cancel")]
    ])
    
    # Отправляем сообщение с таймером
    timer_message = await callback.message.answer(
        f"Задача: {task['task_name']}\n\nОдин раунд. {planned_minutes} минут. Без геройства. Я с тобой.\n\n⏱ 0:00 / {planned_minutes}:00\n" + "░" * 20,
        reply_markup=timer_keyboard
    )
    
    # Сохраняем ID сообщения с таймером
    active_sessions[user_id]["timer_message_id"] = timer_message.message_id
    
    async def update_timer_display(seconds_passed: int, total_seconds: int, is_paused: bool = False):
        """Обновление отображения таймера"""
        minutes = seconds_passed // 60
        secs = seconds_passed % 60
        total_minutes = total_seconds // 60
        
        # Прогресс-бар (20 символов)
        progress = int((seconds_passed / total_seconds) * 20)
        progress_bar = "█" * progress + "░" * (20 - progress)
        
        # Текст паузы
        pause_text = " ⏸ ПАУЗА" if is_paused else ""
        
        # Кнопки управления
        if is_paused:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Продолжить", callback_data="focus_resume")],
                [InlineKeyboardButton(text="Отменить", callback_data="focus_cancel")]
            ])
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пауза", callback_data="focus_pause")],
                [InlineKeyboardButton(text="Отменить", callback_data="focus_cancel")]
            ])
        
        try:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=timer_message.message_id,
                text=f"Задача: {task['task_name']}\n\nОдин раунд. {planned_minutes} минут. Без геройства. Я с тобой.\n\n⏱ {minutes}:{secs:02d} / {total_minutes}:00{pause_text}\n{progress_bar}",
                reply_markup=keyboard
            )
        except:
            pass  # Игнорируем ошибки редактирования
    
    async def timer_cb():
        # Обновляем таймер в последний раз
        await update_timer_display(planned_minutes * 60, planned_minutes * 60, is_paused=False)
        
        # Отправляем сообщение о завершении раунда
        await bot.send_message(
            user_id,
            "🔔 Раунд закончен. Как с фокусом?",
            reply_markup=get_focus_status_keyboard()
        )
        
        # Удаляем таймер из активных
        if user_id in active_timers:
            del active_timers[user_id]
    
    # Запускаем таймер с обновлениями каждые 10 секунд
    async def timer_with_updates():
        total_seconds = planned_minutes * 60
        elapsed_seconds = 0
        
        while elapsed_seconds < total_seconds:
            await asyncio.sleep(10)
            
            # Проверяем, что таймер все еще активен
            if user_id not in active_timers or active_timers[user_id] != timer:
                break  # Таймер был отменен
            
            # Если таймер на паузе, пропускаем обновление времени
            if timer.is_paused:
                await update_timer_display(elapsed_seconds, total_seconds, is_paused=True)
                continue
            
            # Увеличиваем прошедшее время
            elapsed_seconds += 10
            
            # Обновляем отображение
            await update_timer_display(elapsed_seconds, total_seconds, is_paused=False)
        
        # Если таймер все еще активен и не был отменен, вызываем callback
        if user_id in active_timers and active_timers[user_id] == timer and not timer.is_paused:
            await timer_cb()
    
    # Сохраняем таймер
    active_timers[user_id] = timer
    
    # Запускаем обновления таймера (это и есть основной таймер)
    asyncio.create_task(timer_with_updates())


@dp.callback_query(F.data == "focus_pause")
async def focus_pause_handler(callback: CallbackQuery):
    """Обработчик паузы сессии фокуса"""
    await callback.answer("⏸ Пауза")
    
    user_id = callback.from_user.id
    
    if user_id in active_timers:
        timer = active_timers[user_id]
        timer.pause()
        
        # Обновляем отображение
        if user_id in active_sessions:
            session = active_sessions[user_id]
            timer_message_id = session.get("timer_message_id")
            
            if timer_message_id:
                # Вычисляем прошедшее время
                elapsed = timer.paused_seconds
                total = timer.duration_seconds
                minutes = elapsed // 60
                secs = elapsed % 60
                total_minutes = total // 60
                
                progress = int((elapsed / total) * 20)
                progress_bar = "█" * progress + "░" * (20 - progress)
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Продолжить", callback_data="focus_resume")],
                    [InlineKeyboardButton(text="Отменить", callback_data="focus_cancel")]
                ])
                
                try:
                    await bot.edit_message_text(
                        chat_id=user_id,
                        message_id=timer_message_id,
                        text=f"Задача: {session['task_name']}\n\nОдин раунд. {timer.duration_minutes} минут. Без геройства. Я с тобой.\n\n⏱ {minutes}:{secs:02d} / {total_minutes}:00 ⏸ ПАУЗА\n{progress_bar}",
                        reply_markup=keyboard
                    )
                except:
                    pass


@dp.callback_query(F.data == "focus_resume")
async def focus_resume_handler(callback: CallbackQuery):
    """Обработчик возобновления сессии фокуса"""
    await callback.answer("▶ Продолжено")
    
    user_id = callback.from_user.id
    
    if user_id in active_timers:
        timer = active_timers[user_id]
        timer.resume()


@dp.callback_query(F.data == "focus_cancel")
async def focus_cancel_handler(callback: CallbackQuery):
    """Обработчик отмены сессии фокуса"""
    await callback.answer("❌ Отменено")
    
    user_id = callback.from_user.id
    
    if user_id in active_timers:
        timer = active_timers[user_id]
        timer.cancel()
        del active_timers[user_id]
        
        # Обновляем сообщение с таймером
        if user_id in active_sessions:
            session = active_sessions[user_id]
            timer_message_id = session.get("timer_message_id")
            
            if timer_message_id:
                try:
                    await bot.edit_message_text(
                        chat_id=user_id,
                        message_id=timer_message_id,
                        text=f"Задача: {session['task_name']}\n\n❌ Сессия отменена."
                    )
                except:
                    pass
            
            # Удаляем сессию
            del active_sessions[user_id]
        
        await callback.message.answer("Сессия фокуса отменена.")


@dp.callback_query(F.data == "focus_edit_tasks")
async def focus_edit_tasks_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования задач"""
    await callback.answer()
    tasks = db.get_all_focus_tasks()
    
    if not tasks:
        # Пытаемся отредактировать фото с кнопками управления задачами
        try:
            photo = FSInputFile("images/focus.jpg")
            await callback.message.edit_media(
                media=InputMediaPhoto(media=photo, caption="Нет добавленных задач."),
                reply_markup=get_focus_tasks_keyboard()
            )
        except:
            # Если не удалось отредактировать, отправляем новое фото с кнопками
            try:
                photo = FSInputFile("images/focus.jpg")
                await callback.message.answer_photo(
                    photo=photo,
                    caption="Нет добавленных задач.",
                    reply_markup=get_focus_tasks_keyboard()
                )
            except:
                try:
                    await callback.message.edit_text(
                        "Нет добавленных задач.",
                        reply_markup=get_focus_tasks_keyboard()
                    )
                except:
                    await callback.message.answer(
                        "Нет добавленных задач.",
                        reply_markup=get_focus_tasks_keyboard()
                    )
        return
    
    # Формируем клавиатуру с задачами для редактирования
    buttons = []
    for task in tasks:
        task_name = task['task_name']
        buttons.append([InlineKeyboardButton(
            text=f"{task_name}",
            callback_data=f"focus_edit_task_{task['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_focus_tasks_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    try:
        await callback.message.edit_text("Выбери задачу для редактирования:", reply_markup=keyboard)
    except:
        await callback.message.answer("Выбери задачу для редактирования:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("focus_edit_task_"))
async def focus_edit_task_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования конкретной задачи"""
    await callback.answer()
    task_id = int(callback.data.split("_")[-1])
    task = db.get_focus_task_by_id(task_id)
    
    if not task:
        await callback.message.answer("Задача не найдена.", reply_markup=get_main_keyboard())
        return
    
    await state.update_data(editing_task_id=task_id)
    try:
        await callback.message.edit_text(f"Текущее название: {task['task_name']}\n\nВведи новое название:")
    except:
        await callback.message.answer(f"Текущее название: {task['task_name']}\n\nВведи новое название:")
    await state.set_state(FocusStates.waiting_task_edit)


@dp.message(FocusStates.waiting_task_edit)
async def process_task_edit(message: Message, state: FSMContext):
    """Обработка редактирования задачи"""
    data = await state.get_data()
    task_id = data.get("editing_task_id")
    new_name = message.text.strip() if message.text else ""
    
    if task_id and new_name:
        task = db.get_focus_task_by_id(task_id)
        if task:
            db.update_focus_task(task_id, new_name, task.get('description'))
            # Отправляем фото с кнопками управления задачами
            try:
                photo = FSInputFile("images/focus.jpg")
                await message.answer_photo(
                    photo=photo,
                    caption=f"Задача обновлена: {new_name}",
                    reply_markup=get_focus_tasks_keyboard()
                )
            except:
                await message.answer(f"Задача обновлена: {new_name}", reply_markup=get_focus_tasks_keyboard())
        else:
            try:
                photo = FSInputFile("images/focus.jpg")
                await message.answer_photo(
                    photo=photo,
                    caption="Задача не найдена.",
                    reply_markup=get_focus_tasks_keyboard()
                )
            except:
                await message.answer("Задача не найдена.", reply_markup=get_focus_tasks_keyboard())
    else:
        try:
            photo = FSInputFile("images/focus.jpg")
            await message.answer_photo(
                photo=photo,
                caption="Название не может быть пустым.",
                reply_markup=get_focus_tasks_keyboard()
            )
        except:
            await message.answer("Название не может быть пустым.", reply_markup=get_focus_tasks_keyboard())
    
    await state.clear()


@dp.callback_query(F.data == "focus_delete_tasks")
async def focus_delete_tasks_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик удаления задач"""
    await callback.answer()
    tasks = db.get_all_focus_tasks()
    
    if not tasks:
        # Пытаемся отредактировать фото с кнопками управления задачами
        try:
            photo = FSInputFile("images/focus.jpg")
            await callback.message.edit_media(
                media=InputMediaPhoto(media=photo, caption="Нет добавленных задач."),
                reply_markup=get_focus_tasks_keyboard()
            )
        except:
            # Если не удалось отредактировать, отправляем новое фото с кнопками
            try:
                photo = FSInputFile("images/focus.jpg")
                await callback.message.answer_photo(
                    photo=photo,
                    caption="Нет добавленных задач.",
                    reply_markup=get_focus_tasks_keyboard()
                )
            except:
                try:
                    await callback.message.edit_text(
                        "Нет добавленных задач.",
                        reply_markup=get_focus_tasks_keyboard()
                    )
                except:
                    await callback.message.answer(
                        "Нет добавленных задач.",
                        reply_markup=get_focus_tasks_keyboard()
                    )
        return
    
    # Формируем клавиатуру с задачами для удаления
    buttons = []
    for task in tasks:
        task_name = task['task_name']
        buttons.append([InlineKeyboardButton(
            text=f"{task_name}",
            callback_data=f"focus_delete_task_{task['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_focus_tasks_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    try:
        await callback.message.edit_text("Выбери задачу для удаления:", reply_markup=keyboard)
    except:
        await callback.message.answer("Выбери задачу для удаления:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("focus_delete_task_"))
async def focus_delete_task_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик удаления конкретной задачи"""
    await callback.answer()
    task_id = int(callback.data.split("_")[-1])
    task = db.get_focus_task_by_id(task_id)
    
    if task:
        db.delete_focus_task(task_id)
        # Пытаемся отредактировать фото с кнопками управления задачами
        try:
            photo = FSInputFile("images/focus.jpg")
            await callback.message.edit_media(
                media=InputMediaPhoto(media=photo, caption=f"Задача '{task['task_name']}' удалена."),
                reply_markup=get_focus_tasks_keyboard()
            )
        except:
            # Если не удалось отредактировать, отправляем новое фото с кнопками
            try:
                photo = FSInputFile("images/focus.jpg")
                await callback.message.answer_photo(
                    photo=photo,
                    caption=f"Задача '{task['task_name']}' удалена.",
                    reply_markup=get_focus_tasks_keyboard()
                )
            except:
                try:
                    await callback.message.edit_text(f"Задача '{task['task_name']}' удалена.", reply_markup=get_focus_tasks_keyboard())
                except:
                    await callback.message.answer(f"Задача '{task['task_name']}' удалена.", reply_markup=get_focus_tasks_keyboard())
    else:
        try:
            photo = FSInputFile("images/focus.jpg")
            await callback.message.answer_photo(
                photo=photo,
                caption="Задача не найдена.",
                reply_markup=get_focus_tasks_keyboard()
            )
        except:
            await callback.message.answer("Задача не найдена.", reply_markup=get_focus_tasks_keyboard())


@dp.callback_query(F.data == "focus_dump")
async def focus_dump_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик FOCUS → Разгрузка головы"""
    await callback.answer()
    await button_dump(callback, state)


@dp.callback_query(F.data == "focus_delete_stats")
async def focus_delete_stats_handler(callback: CallbackQuery):
    """Обработчик удаления статистики"""
    await callback.answer()
    
    # Подтверждение удаления
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, удалить все", callback_data="focus_delete_stats_confirm")],
        [InlineKeyboardButton(text="Отмена", callback_data="back_to_focus_main")]
    ])
    
    try:
        await callback.message.edit_text(
            "⚠️ Ты уверен? Это действие нельзя отменить!\n\n"
            "Будут удалены все данные:\n"
            "• Сессии фокуса\n"
            "• Данные о сне\n"
            "• Планы тренировок\n"
            "• Разгрузки головы\n"
            "• Заметки об обучении\n"
            "• Задачи фокуса",
            reply_markup=keyboard
        )
    except:
        await callback.message.answer(
            "⚠️ Ты уверен? Это действие нельзя отменить!\n\n"
            "Будут удалены все данные:\n"
            "• Сессии фокуса\n"
            "• Данные о сне\n"
            "• Планы тренировок\n"
            "• Разгрузки головы\n"
            "• Заметки об обучении\n"
            "• Задачи фокуса",
            reply_markup=keyboard
        )


@dp.callback_query(F.data == "focus_delete_stats_confirm")
async def focus_delete_stats_confirm_handler(callback: CallbackQuery):
    """Подтверждение удаления статистики"""
    await callback.answer("✅ Статистика удалена")
    
    # Удаляем все статистические данные
    success = db.delete_all_stats()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
    ])
    
    keyboard = get_focus_main_keyboard()
    
    if success:
        try:
            await callback.message.edit_text(
                "✅ Все статистические данные удалены.",
                reply_markup=keyboard
            )
        except:
            # Если не получилось отредактировать, отправляем новое сообщение и возвращаем в меню FOCUS
            await callback.message.answer(
                "✅ Все статистические данные удалены."
            )
            try:
                photo = FSInputFile("images/focus.jpg")
                await callback.message.answer_photo(photo=photo, reply_markup=keyboard)
            except:
                await callback.message.answer("FOCUS", reply_markup=keyboard)
    else:
        try:
            await callback.message.edit_text(
                "❌ Ошибка при удалении данных.",
                reply_markup=keyboard
            )
        except:
            await callback.message.answer(
                "❌ Ошибка при удалении данных.",
                reply_markup=keyboard
            )


# Обработчики WORKOUT → Тренировки
@dp.callback_query(F.data == "workout_training")
async def workout_training_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик WORKOUT → Тренировки"""
    await callback.answer()
    
    # Проверяем, есть ли план на неделю
    plans = db.get_all_workout_plans()
    if len(plans) < 7:
        # Нужно заполнить план
        try:
            await callback.message.edit_text(
                "Заполни план тренировок на неделю.\n\nНачнем с понедельника. Какие упражнения на понедельник?",
                reply_markup=get_back_to_workout_keyboard()
            )
        except:
            await callback.message.answer(
                "Заполни план тренировок на неделю.\n\nНачнем с понедельника. Какие упражнения на понедельник?",
                reply_markup=get_back_to_workout_keyboard()
            )
        await state.set_state(WorkoutStates.waiting_plan_monday)
    else:
        # Показываем план на сегодня
        from datetime import datetime
        today = datetime.now()
        day_of_week = today.weekday()  # 0=понедельник, 6=воскресенье
        
        plan = db.get_workout_plan(day_of_week)
        if plan:
            exercises = plan.split('\n')
            text = f"Тренировка на {['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'][day_of_week]}:\n\n"
            for i, ex in enumerate(exercises, 1):
                if ex.strip():
                    text += f"{i}. {ex.strip()}\n"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Сделал", callback_data=f"workout_done_{day_of_week}")],
                [InlineKeyboardButton(text="Не сделал", callback_data=f"workout_skip_{day_of_week}")],
                [InlineKeyboardButton(text="Редактировать план", callback_data="workout_edit_plan")]
            ])
            try:
                await callback.message.edit_text(text, reply_markup=keyboard)
            except:
                await callback.message.answer(text, reply_markup=keyboard)
        else:
            try:
                await callback.message.edit_text(
                    "План на сегодня не заполнен. Заполни план тренировок.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Заполнить план", callback_data="workout_edit_plan")]
                    ])
                )
            except:
                await callback.message.answer(
                    "План на сегодня не заполнен. Заполни план тренировок.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Заполнить план", callback_data="workout_edit_plan")]
                    ])
                )


@dp.callback_query(F.data == "workout_edit_plan")
async def workout_edit_plan_handler(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование плана тренировок"""
    await callback.answer()
    try:
        await callback.message.edit_text(
            "Заполни план тренировок на неделю.\n\nНачнем с понедельника. Какие упражнения на понедельник?",
            reply_markup=get_back_to_workout_keyboard()
        )
    except:
        await callback.message.answer(
            "Заполни план тренировок на неделю.\n\nНачнем с понедельника. Какие упражнения на понедельник?",
            reply_markup=get_back_to_workout_keyboard()
        )
    await state.set_state(WorkoutStates.waiting_plan_monday)


@dp.message(WorkoutStates.waiting_plan_monday)
async def process_workout_monday(message: Message, state: FSMContext):
    """Обработка плана на понедельник"""
    exercises = message.text.strip() if message.text else ""
    if exercises:
        db.set_workout_plan(0, exercises)
        await message.answer("План на понедельник сохранен.\n\nКакие упражнения на вторник?", reply_markup=get_back_to_workout_keyboard())
        await state.set_state(WorkoutStates.waiting_plan_tuesday)
    else:
        await message.answer("Введи упражнения текстом.", reply_markup=get_back_to_workout_keyboard())


@dp.message(WorkoutStates.waiting_plan_tuesday)
async def process_workout_tuesday(message: Message, state: FSMContext):
    """Обработка плана на вторник"""
    exercises = message.text.strip() if message.text else ""
    if exercises:
        db.set_workout_plan(1, exercises)
        await message.answer("План на вторник сохранен.\n\nКакие упражнения на среду?", reply_markup=get_back_to_workout_keyboard())
        await state.set_state(WorkoutStates.waiting_plan_wednesday)
    else:
        await message.answer("Введи упражнения текстом.", reply_markup=get_back_to_workout_keyboard())


@dp.message(WorkoutStates.waiting_plan_wednesday)
async def process_workout_wednesday(message: Message, state: FSMContext):
    """Обработка плана на среду"""
    exercises = message.text.strip() if message.text else ""
    if exercises:
        db.set_workout_plan(2, exercises)
        await message.answer("План на среду сохранен.\n\nКакие упражнения на четверг?", reply_markup=get_back_to_workout_keyboard())
        await state.set_state(WorkoutStates.waiting_plan_thursday)
    else:
        await message.answer("Введи упражнения текстом.", reply_markup=get_back_to_workout_keyboard())


@dp.message(WorkoutStates.waiting_plan_thursday)
async def process_workout_thursday(message: Message, state: FSMContext):
    """Обработка плана на четверг"""
    exercises = message.text.strip() if message.text else ""
    if exercises:
        db.set_workout_plan(3, exercises)
        await message.answer("План на четверг сохранен.\n\nКакие упражнения на пятницу?", reply_markup=get_back_to_workout_keyboard())
        await state.set_state(WorkoutStates.waiting_plan_friday)
    else:
        await message.answer("Введи упражнения текстом.", reply_markup=get_back_to_workout_keyboard())


@dp.message(WorkoutStates.waiting_plan_friday)
async def process_workout_friday(message: Message, state: FSMContext):
    """Обработка плана на пятницу"""
    exercises = message.text.strip() if message.text else ""
    if exercises:
        db.set_workout_plan(4, exercises)
        await message.answer("План на пятницу сохранен.\n\nКакие упражнения на субботу?", reply_markup=get_back_to_workout_keyboard())
        await state.set_state(WorkoutStates.waiting_plan_saturday)
    else:
        await message.answer("Введи упражнения текстом.", reply_markup=get_back_to_workout_keyboard())


@dp.message(WorkoutStates.waiting_plan_saturday)
async def process_workout_saturday(message: Message, state: FSMContext):
    """Обработка плана на субботу"""
    exercises = message.text.strip() if message.text else ""
    if exercises:
        db.set_workout_plan(5, exercises)
        await message.answer("План на субботу сохранен.\n\nКакие упражнения на воскресенье?", reply_markup=get_back_to_workout_keyboard())
        await state.set_state(WorkoutStates.waiting_plan_sunday)
    else:
        await message.answer("Введи упражнения текстом.", reply_markup=get_back_to_workout_keyboard())


@dp.message(WorkoutStates.waiting_plan_sunday)
async def process_workout_sunday(message: Message, state: FSMContext):
    """Обработка плана на воскресенье"""
    exercises = message.text.strip() if message.text else ""
    if exercises:
        db.set_workout_plan(6, exercises)
        await message.answer("План на воскресенье сохранен.\n\nПлан тренировок на неделю готов.")
        
        # Возвращаем на страницу WORKOUT
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Тренировки", callback_data="workout_training")],
            [InlineKeyboardButton(text="Анализ", callback_data="workout_analysis")],
            [InlineKeyboardButton(text="Сон", callback_data="workout_sleep")]
        ])
        
        try:
            photo = FSInputFile("images/workout.jpg")
            await message.answer_photo(photo=photo, reply_markup=keyboard)
        except:
            try:
                photo = FSInputFile("images/workout.png")
                await message.answer_photo(photo=photo, reply_markup=keyboard)
            except:
                await message.answer("WORKOUT", reply_markup=keyboard)
        
        await state.clear()
    else:
        await message.answer("Введи упражнения текстом.", reply_markup=get_back_to_workout_keyboard())


@dp.callback_query(F.data.startswith("workout_done_"))
async def workout_done_handler(callback: CallbackQuery):
    """Отметить тренировку как выполненную"""
    await callback.answer()
    day_of_week = int(callback.data.split("_")[-1])
    today = datetime.now().date().isoformat()
    db.mark_workout_completed(today, day_of_week, True)
    try:
        await callback.message.edit_text("Тренировка отмечена как выполненная.")
    except:
        await callback.message.answer("Тренировка отмечена как выполненная.")


@dp.callback_query(F.data.startswith("workout_skip_"))
async def workout_skip_handler(callback: CallbackQuery):
    """Отметить тренировку как пропущенную"""
    await callback.answer()
    day_of_week = int(callback.data.split("_")[-1])
    today = datetime.now().date().isoformat()
    db.mark_workout_completed(today, day_of_week, False)
    try:
        await callback.message.edit_text("Тренировка отмечена как пропущенная.")
    except:
        await callback.message.answer("Тренировка отмечена как пропущенная.")


@dp.callback_query(F.data == "workout_analysis")
async def workout_analysis_handler(callback: CallbackQuery):
    """Обработчик WORKOUT → Анализ нагрузки"""
    await callback.answer()
    # Получаем данные за последние 14 дней
    completions = db.get_workout_completions(14)
    
    if not completions:
        try:
            await callback.message.edit_text("Недостаточно данных для анализа. Выполни несколько тренировок.")
        except:
            await callback.message.answer("Недостаточно данных для анализа. Выполни несколько тренировок.")
        return
    
    # Анализируем двухнедельные циклы
    from collections import defaultdict
    by_week = defaultdict(lambda: {"completed": 0, "skipped": 0, "days": []})
    
    for comp in completions:
        date_obj = datetime.fromisoformat(comp['date'])
        week_num = date_obj.isocalendar()[1]  # Номер недели года
        if comp['completed']:
            by_week[week_num]["completed"] += 1
        else:
            by_week[week_num]["skipped"] += 1
        by_week[week_num]["days"].append(comp['day_of_week'])
    
    # Формируем рекомендации
    text = "Анализ нагрузки за последние 2 недели:\n\n"
    
    for week_num in sorted(by_week.keys())[-2:]:  # Последние 2 недели
        data = by_week[week_num]
        total = data["completed"] + data["skipped"]
        if total > 0:
            density = data["completed"] / total if total > 0 else 0
            text += f"Неделя {week_num}: выполнено {data['completed']}/{total} ({density*100:.0f}%)\n"
    
    # Рекомендации (каждое второе воскресенье)
    today = datetime.now()
    if today.weekday() == 6 and today.isocalendar()[1] % 2 == 0:  # Воскресенье, четная неделя
        if len(by_week) >= 2:
            weeks = sorted(by_week.keys())[-2:]
            week1_density = by_week[weeks[0]]["completed"] / max(1, by_week[weeks[0]]["completed"] + by_week[weeks[0]]["skipped"])
            week2_density = by_week[weeks[1]]["completed"] / max(1, by_week[weeks[1]]["completed"] + by_week[weeks[1]]["skipped"])
            
            text += "\nРекомендации:\n"
            if abs(week1_density - week2_density) > 0.3:
                if week1_density < week2_density:
                    text += "Нагрузка в первой неделе ниже. Можно добавить упражнения или подходы.\n"
                else:
                    text += "Нагрузка во второй неделе ниже. Можно добавить упражнения или подходы.\n"
            else:
                text += "Нагрузка распределена равномерно.\n"
    
    try:
        await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    except:
        await callback.message.answer(text, reply_markup=get_back_to_menu_keyboard())


# Команда /focus
@dp.message(Command("focus"))
async def cmd_focus(message: Message, state: FSMContext):
    """Обработчик команды /focus"""
    user_id = message.from_user.id
    
    # Отменяем предыдущий таймер, если есть
    if user_id in active_timers:
        active_timers[user_id].cancel()
        del active_timers[user_id]
    
    await message.answer(
        "Управление задачами:",
        reply_markup=get_focus_tasks_keyboard()
    )
    """Обработка выбора типа задачи (v1.1)"""
    task_type_map = {
        "task_theory": "theory",
        "task_practice": "practice",
        "task_reading": "reading",
        "task_examples": "examples",
        "task_input": "input",
        "task_review": "review"
    }
    
    task_type = task_type_map.get(callback.data, "theory")
    data = await state.get_data()
    domain = data.get("direction", "Другое")
    
    # Получаем рекомендуемую длительность на основе истории
    avg_duration = db.get_average_focus_duration(domain, task_type)
    if avg_duration:
        # Адаптация: если последние 3 сессии < 70% или > 90%
        recent_sessions = db.get_detailed_sessions(domain=domain, task_type=task_type, days=7)
        if len(recent_sessions) >= 3:
            last_3 = recent_sessions[:3]
            completion_rates = [
                (s.get('actual_minutes', 0) or 0) / (s.get('planned_minutes', 20) or 20)
                for s in last_3 if s.get('planned_minutes')
            ]
            if completion_rates and all(r < 0.7 for r in completion_rates):
                planned_minutes = max(10, int(avg_duration * 0.8))  # Уменьшаем
            elif completion_rates and all(r > 0.9 for r in completion_rates):
                planned_minutes = min(30, int(avg_duration * 1.2))  # Увеличиваем
            else:
                planned_minutes = int(avg_duration)
        else:
            planned_minutes = int(avg_duration) if avg_duration else 20
    else:
        planned_minutes = 20  # По умолчанию
    
    # Сохраняем тип задачи и запланированное время
    await state.update_data(task_type=task_type, planned_minutes=planned_minutes, start_time=datetime.now().isoformat())
    
    # Запускаем таймер
    user_id = callback.from_user.id
    timer = FocusTimer(duration_minutes=planned_minutes)
    
    # Сохраняем данные в активных сессиях
    active_sessions[user_id] = {
        "direction": domain,
        "task_type": task_type,
        "planned_minutes": planned_minutes,
        "message_id": callback.message.message_id
    }
    
    # Отправляем сообщение с таймером
    timer_message = await callback.message.answer(
        f"Один раунд. {planned_minutes} минут. Без геройства. Я с тобой.\n\n⏱ 0:00 / {planned_minutes}:00\n" + "░" * 20
    )
    
    # Сохраняем ID сообщения с таймером
    active_sessions[user_id]["timer_message_id"] = timer_message.message_id
    
    async def update_timer_display(seconds_passed: int, total_seconds: int):
        """Обновление отображения таймера"""
        minutes = seconds_passed // 60
        secs = seconds_passed % 60
        total_minutes = total_seconds // 60
        
        # Прогресс-бар (20 символов)
        progress = int((seconds_passed / total_seconds) * 20)
        progress_bar = "█" * progress + "░" * (20 - progress)
        
        try:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=timer_message.message_id,
                text=f"Один раунд. {planned_minutes} минут. Без геройства. Я с тобой.\n\n⏱ {minutes}:{secs:02d} / {total_minutes}:00\n{progress_bar}"
            )
        except:
            pass  # Игнорируем ошибки редактирования
    
    async def timer_cb():
        # Обновляем таймер в последний раз
        await update_timer_display(planned_minutes * 60, planned_minutes * 60, is_paused=False)
        
        # Отправляем сообщение о завершении раунда
        await bot.send_message(
            user_id,
            "🔔 Раунд закончен. Как с фокусом?",
            reply_markup=get_focus_status_keyboard()
        )
        
        # Удаляем таймер из активных
        if user_id in active_timers:
            del active_timers[user_id]
    
    # Запускаем таймер с обновлениями каждые 10 секунд
    async def timer_with_updates():
        total_seconds = planned_minutes * 60
        for i in range(0, total_seconds, 10):
            await asyncio.sleep(10)
            if user_id in active_timers and active_timers[user_id] == timer:
                await update_timer_display(i + 10, total_seconds)
            else:
                break  # Таймер был отменен
        # Если таймер все еще активен, вызываем callback
        if user_id in active_timers and active_timers[user_id] == timer:
            await timer_cb()
    
    # Сохраняем таймер
    active_timers[user_id] = timer
    
    # Запускаем обновления таймера (это и есть основной таймер)
    asyncio.create_task(timer_with_updates())
    
    await callback.answer()


@dp.callback_query(F.data.in_(["focus_ok", "focus_partial", "focus_lost"]))
async def process_focus_status(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора статуса фокуса"""
    status_map = {
        "focus_ok": "✅",
        "focus_partial": "🟡",
        "focus_lost": "❌"
    }
    
    focus_status = status_map.get(callback.data, "🟡")
    
    # Сохраняем статус в состоянии
    await state.update_data(focus_status=focus_status)
    
    # Редактируем сообщение или отправляем новое
    try:
        await callback.message.edit_text("Что именно делал? (1–2 слова)")
    except:
        await callback.message.answer("Что именно делал? (1–2 слова)")
    
    await state.set_state(FocusStates.waiting_description)
    await callback.answer()


@dp.message(FocusStates.waiting_description)
async def process_focus_description(message: Message, state: FSMContext):
    """Обработка описания сессии фокуса"""
    user_id = message.from_user.id
    data = await state.get_data()
    
    # Получаем данные из активных сессий
    session_data = active_sessions.get(user_id, {})
    task_name = session_data.get("task_name", "Задача")
    task_id = session_data.get("task_id")
    planned_minutes = session_data.get("planned_minutes", 20)
    
    focus_status = data.get("focus_status", "🟡")
    description = message.text.strip() if message.text else None
    
    # Вычисляем фактическое время (примерно, так как таймер уже закончился)
    actual_minutes = planned_minutes  # Можно улучшить, сохраняя время начала
    
    # Определяем статус сессии
    status = "completed" if focus_status == "✅" else ("dropped" if focus_status == "❌" else "completed")
    
    # Сохраняем детальную сессию
    db.add_detailed_session(
        domain=task_name,  # Используем название задачи как domain
        task_type="custom",  # Тип задачи - кастомная
        planned_minutes=planned_minutes,
        actual_minutes=actual_minutes,
        status=status,
        focus_status=focus_status,
        description=description
    )
    
    # Также сохраняем в старую таблицу для совместимости
    db.add_focus_session(
        direction=task_name,
        duration=actual_minutes,
        focus_status=focus_status,
        description=description
    )
    
    # Очищаем активную сессию
    if user_id in active_sessions:
        del active_sessions[user_id]
    
    await message.answer("Засчитано. Хорошая работа.", reply_markup=get_main_keyboard())
    await state.clear()


# Команда /day - УДАЛЕНА (функционал "Проверить день" удален)


# Команда /dump
@dp.message(Command("dump"))
async def cmd_dump(message: Message, state: FSMContext):
    """Обработчик команды /dump"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Новая запись", callback_data="dump_new"),
        InlineKeyboardButton(text="Мои записи", callback_data="dump_list")
    ]])
    await message.answer("Разгрузка головы:", reply_markup=keyboard)
    await state.set_state(DumpStates.waiting_content)


@dp.callback_query(F.data == "dump_new")
async def dump_new(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки новой записи"""
    await callback.answer()
    keyboard = get_back_to_dump_keyboard()
    try:
        await callback.message.edit_text("Пиши всё, что сейчас в голове. Можно без порядка.", reply_markup=keyboard)
    except:
        await callback.message.answer("Пиши всё, что сейчас в голове. Можно без порядка.", reply_markup=keyboard)
    await state.set_state(DumpStates.waiting_content)


@dp.callback_query(F.data == "dump_list")
async def dump_list(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки списка записей"""
    await callback.answer()
    dumps = db.get_all_brain_dumps(limit=20)
    
    if not dumps:
        await callback.message.edit_text("Записей пока нет.", reply_markup=get_back_to_dump_keyboard())
        await state.clear()
        return
    
    # Формируем список записей
    text = "📋 Твои записи:\n\n"
    buttons = []
    
    for dump in dumps[:10]:  # Показываем первые 10
        dump_id = dump["id"]
        content = dump["content"][:50] + "..." if len(dump["content"]) > 50 else dump["content"]
        date_str = dump["created_at"][:10]  # Только дата
        text += f"{dump_id}. {content}\n📅 {date_str}\n\n"
        buttons.append([InlineKeyboardButton(
            text=f"#{dump_id} {content[:30]}...",
            callback_data=f"dump_view_{dump_id}"
        )])
    
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="focus_dump")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(DumpStates.viewing_list)


@dp.callback_query(F.data.startswith("dump_view_"), DumpStates.viewing_list)
async def dump_view(callback: CallbackQuery, state: FSMContext):
    """Просмотр конкретной записи"""
    await callback.answer()
    dump_id = int(callback.data.split("_")[-1])
    dump = db.get_brain_dump_by_id(dump_id)
    
    if not dump:
        await callback.message.edit_text("Запись не найдена.", reply_markup=get_back_to_dump_keyboard())
        await state.clear()
        return
    
    date_time = dump["created_at"][:16].replace("T", " ")
    text = f"📝 Запись #{dump_id}\n📅 {date_time}\n\n{dump['content']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Редактировать", callback_data=f"dump_edit_{dump_id}"),
        InlineKeyboardButton(text="Удалить", callback_data=f"dump_delete_{dump_id}")
    ], [
        InlineKeyboardButton(text="Назад к списку", callback_data="dump_list")
    ]])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.update_data(dump_id=dump_id)


@dp.callback_query(F.data.startswith("dump_edit_"), DumpStates.viewing_list)
async def dump_edit_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования записи"""
    await callback.answer()
    dump_id = int(callback.data.split("_")[-1])
    dump = db.get_brain_dump_by_id(dump_id)
    
    if dump:
        await callback.message.edit_text(f"Редактируй запись:\n\n{dump['content']}")
        await state.update_data(dump_id=dump_id)
        await state.set_state(DumpStates.waiting_edit_text)


@dp.callback_query(F.data.startswith("dump_delete_"), DumpStates.viewing_list)
async def dump_delete(callback: CallbackQuery, state: FSMContext):
    """Удаление записи"""
    await callback.answer()
    dump_id = int(callback.data.split("_")[-1])
    
    if db.delete_brain_dump(dump_id):
        # После удаления возвращаемся к списку записей
        await dump_list(callback, state)
    else:
        await callback.message.edit_text("Ошибка при удалении.", reply_markup=get_back_to_dump_keyboard())
        await state.clear()


@dp.message(DumpStates.waiting_content)
async def process_dump(message: Message, state: FSMContext):
    """Обработка новой разгрузки головы"""
    content = message.text.strip() if message.text else ""
    
    if content:
        db.add_brain_dump(content)
        
        # Предлагаем выбрать одну вещь
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Да", callback_data="dump_yes"),
            InlineKeyboardButton(text="Нет", callback_data="dump_no")
        ]])
        
        await message.answer(
            "Хочешь выбрать одну вещь на сейчас?",
            reply_markup=keyboard
        )
        await state.set_state(DumpStates.waiting_choice)
    else:
        await message.answer("Разгрузка сохранена.", reply_markup=get_back_to_dump_keyboard())
        await state.clear()


@dp.message(DumpStates.waiting_edit_text)
async def process_dump_edit(message: Message, state: FSMContext):
    """Обработка редактирования записи"""
    data = await state.get_data()
    dump_id = data.get("dump_id")
    new_content = message.text.strip() if message.text else ""
    
    if dump_id and new_content:
        if db.update_brain_dump(dump_id, new_content):
            # Возвращаемся к просмотру записи
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Редактировать", callback_data=f"dump_edit_{dump_id}"),
                InlineKeyboardButton(text="Удалить", callback_data=f"dump_delete_{dump_id}")
            ], [
                InlineKeyboardButton(text="Назад к списку", callback_data="dump_list")
            ]])
            dump = db.get_brain_dump_by_id(dump_id)
            if dump:
                date_time = dump["created_at"][:16].replace("T", " ")
                text = f"📝 Запись #{dump_id}\n📅 {date_time}\n\n{dump['content']}"
                await message.answer("Запись обновлена.", reply_markup=keyboard)
                await message.answer(text, reply_markup=keyboard)
            else:
                await message.answer("Запись обновлена.", reply_markup=get_back_to_dump_keyboard())
        else:
            await message.answer("Ошибка при обновлении.", reply_markup=get_back_to_dump_keyboard())
    else:
        await message.answer("Текст не может быть пустым.", reply_markup=get_back_to_dump_keyboard())
    
    await state.clear()


@dp.callback_query(F.data.in_(["dump_yes", "dump_no"]), DumpStates.waiting_choice)
async def process_dump_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора после разгрузки"""
    if callback.data == "dump_yes":
        await callback.message.edit_text("Выбери одну вещь и начни с неё.", reply_markup=get_back_to_dump_keyboard())
    else:
        await callback.message.edit_text("Хорошо. Отдохни.", reply_markup=get_back_to_dump_keyboard())
    
    await state.clear()
    await callback.answer()


# Команда /learn - УДАЛЕНА (функционал "Что понял" удален)
# Все обработчики learn_* - УДАЛЕНЫ (функционал "Что понял" удален)


# Старый обработчик английского удален - заменен на SRS версию выше


# Обработчики кнопок главного меню
# Обработчик cmd_day - УДАЛЕН (функционал "Проверить день" удален)


@dp.callback_query(F.data == "cmd_dump")
async def button_dump(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Разгрузка головы'"""
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Новая запись", callback_data="dump_new"),
        InlineKeyboardButton(text="Мои записи", callback_data="dump_list")
    ], [
        InlineKeyboardButton(text="Назад", callback_data="back_to_focus_main")
    ]])
    try:
        await callback.message.edit_text("Разгрузка головы:", reply_markup=keyboard)
    except:
        await callback.message.answer("Разгрузка головы:", reply_markup=keyboard)
    await state.set_state(DumpStates.waiting_content)


# Обработчик cmd_learn - УДАЛЕН (функционал "Что понял" удален)


# Старый обработчик кнопки английского удален - заменен на SRS версию выше


@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Назад' - возврат в главное меню"""
    await callback.answer()
    await state.clear()
    
    # Получаем username или используем имя
    username = callback.from_user.username
    if username:
        greeting = f"Привет @{username}, приступим?"
    else:
        # Если username нет, используем имя или "друг"
        name = callback.from_user.first_name or "друг"
        greeting = f"Привет {name}, приступим?"
    
    await callback.message.answer(
        text=greeting,
        reply_markup=get_main_keyboard()
    )


# ========== НОВЫЕ ФУНКЦИИ v1.1 ==========

# Аналитика
@dp.message(Command("productivity"))
@dp.callback_query(F.data == "anal_productivity")
async def cmd_productivity(message_or_callback, state: FSMContext):
    """Генерация тепловой карты продуктивности"""
    if isinstance(message_or_callback, CallbackQuery):
        callback = message_or_callback
        await callback.answer()
        message = callback.message
    else:
        message = message_or_callback
    
    await message.answer("Генерирую тепловую карту...")
    
    sessions = db.get_detailed_sessions(days=14)
    if not sessions:
        await message.answer("Недостаточно данных для анализа.", reply_markup=get_main_keyboard())
        return
    
    try:
        heatmap_buf = generate_productivity_heatmap(sessions)
        photo_file = BufferedInputFile(heatmap_buf.read(), filename="productivity.png")
        await message.answer_photo(
            photo=photo_file,
            caption="Тепловая карта продуктивности (успешность по часам и дням недели)"
        )
    except Exception as e:
        await message.answer(f"Ошибка при генерации графика: {e}", reply_markup=get_main_keyboard())


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Генерация графиков статистики"""
    await message.answer("Генерирую графики статистики...")
    
    sessions = db.get_detailed_sessions(days=14)
    if not sessions:
        await message.answer("Недостаточно данных для анализа.", reply_markup=get_main_keyboard())
        return
    
    try:
        stats_buf = generate_stats_charts(sessions)
        photo_file = BufferedInputFile(stats_buf.read(), filename="stats.png")
        await message.answer_photo(
            photo=photo_file,
            caption="Статистика: сессии по дням, средняя длительность, процент завершённых"
        )
    except Exception as e:
        await message.answer(f"Ошибка при генерации графика: {e}", reply_markup=get_main_keyboard())


# Поиск информации
@dp.message(Command("search"))
@dp.callback_query(F.data == "cmd_search")
async def cmd_search(message_or_callback, state: FSMContext):
    """Поиск информации в интернете"""
    if isinstance(message_or_callback, CallbackQuery):
        callback = message_or_callback
        await callback.answer()
        await callback.message.edit_text("О чём искать информацию?")
        await state.set_state(SearchStates.waiting_query)
    else:
        message = message_or_callback
        await message.answer("О чём искать информацию?", reply_markup=get_back_to_menu_keyboard())
        await state.set_state(SearchStates.waiting_query)


@dp.message(SearchStates.waiting_query)
async def process_search(message: Message, state: FSMContext):
    """Обработка поискового запроса"""
    query = message.text.strip() if message.text else ""
    
    if not query:
        await message.answer("Запрос не может быть пустым.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    
    await message.answer("Ищу информацию...")
    
    try:
        results = search_info(query)
        
        response = f"🔍 Результаты поиска: {query}\n\n"
        
        if results.get('youtube'):
            response += "📺 YouTube:\n"
            for video in results['youtube'][:5]:
                response += f"• {video['title']}\n{video['link']}\n\n"
        
        if results.get('web'):
            response += "🌐 Статьи:\n"
            for article in results['web'][:3]:
                response += f"• {article['title']}\n{article['link']}\n\n"
        
        if not results.get('youtube') and not results.get('web'):
            response = "Ничего не найдено. Попробуй другой запрос."
        
        await message.answer(response, reply_markup=get_main_keyboard())
    except Exception as e:
        await message.answer(f"Ошибка при поиске: {e}", reply_markup=get_main_keyboard())
    
    await state.clear()


# Трекинг сна
@dp.message(Command("sleep"))
@dp.callback_query(F.data == "cmd_sleep")
async def cmd_sleep(message_or_callback, state: FSMContext):
    """Трекинг сна"""
    if isinstance(message_or_callback, CallbackQuery):
        callback = message_or_callback
        await callback.answer()
        message = callback.message
    else:
        message = message_or_callback
    
    # Проверяем, есть ли незавершенная запись
    latest_sleep = db.get_latest_sleep_record()
    
    if latest_sleep:
        # Есть незавершенная запись - предлагаем завершить
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Проснулся", callback_data="sleep_wake"),
            InlineKeyboardButton(text="Отменить", callback_data="sleep_cancel")
        ], [
            InlineKeyboardButton(text="График сна", callback_data="sleep_chart")
        ], [
            InlineKeyboardButton(text="Назад", callback_data="back_to_workout")
        ]])
        await message.answer("Есть незавершенная запись сна. Проснулся?", reply_markup=keyboard)
    else:
        # Нет записи - предлагаем начать
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Лёг спать", callback_data="sleep_start"),
            InlineKeyboardButton(text="График сна", callback_data="sleep_chart")
        ], [
            InlineKeyboardButton(text="Назад", callback_data="back_to_workout")
        ]])
        await message.answer("Трекинг сна:", reply_markup=keyboard)


@dp.callback_query(F.data == "sleep_start")
async def sleep_start(callback: CallbackQuery):
    """Начало сна"""
    await callback.answer()
    record_id = db.add_sleep_start()
    
    # Возвращаем в меню "Сон" с кнопками управления
    sleep_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Проснулся", callback_data="sleep_wake"),
        InlineKeyboardButton(text="Отменить", callback_data="sleep_cancel")
    ], [
        InlineKeyboardButton(text="График сна", callback_data="sleep_chart")
    ], [
        InlineKeyboardButton(text="Назад", callback_data="back_to_workout")
    ]])
    
    try:
        await callback.message.edit_text(
            "Сон начат. Через 30 минут запись будет зафиксирована.\n\n"
            "Когда проснёшься, нажми 'Проснулся'.",
            reply_markup=sleep_keyboard
        )
    except:
        await callback.message.answer(
            "Сон начат. Через 30 минут запись будет зафиксирована.\n\n"
            "Когда проснёшься, нажми 'Проснулся'.",
            reply_markup=sleep_keyboard
        )
    
    # Задача для фиксации через 30 минут
    async def fix_sleep():
        await asyncio.sleep(30 * 60)  # 30 минут
        # Запись уже будет в базе, просто подтверждаем
    
    asyncio.create_task(fix_sleep())


@dp.callback_query(F.data == "sleep_cancel")
async def sleep_cancel_handler(callback: CallbackQuery):
    """Отмена сна"""
    await callback.answer("❌ Сон отменен")
    
    # Удаляем незавершенную запись сна
    db.delete_latest_sleep_record()
    
    # Возвращаем в меню "Сон"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Лёг спать", callback_data="sleep_start"),
        InlineKeyboardButton(text="График сна", callback_data="sleep_chart")
    ], [
        InlineKeyboardButton(text="Назад", callback_data="back_to_workout")
    ]])
    
    try:
        await callback.message.edit_text("Трекинг сна:", reply_markup=keyboard)
    except:
        await callback.message.answer("Трекинг сна:", reply_markup=keyboard)


@dp.callback_query(F.data == "sleep_wake")
async def sleep_wake(callback: CallbackQuery):
    """Пробуждение"""
    await callback.answer()
    latest_sleep = db.get_latest_sleep_record()
    
    if latest_sleep:
        db.complete_sleep(latest_sleep['id'])
        duration_hours = (latest_sleep.get('duration_minutes') or 0) / 60
        
        # Возвращаем в меню "Сон"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Лёг спать", callback_data="sleep_start"),
            InlineKeyboardButton(text="График сна", callback_data="sleep_chart")
        ], [
            InlineKeyboardButton(text="Назад", callback_data="back_to_workout")
        ]])
        
        try:
            await callback.message.edit_text(
                f"Сон зафиксирован.\n\n"
                f"Длительность: {duration_hours:.1f} часов",
                reply_markup=keyboard
            )
        except:
            await callback.message.answer(
                f"Сон зафиксирован.\n\n"
                f"Длительность: {duration_hours:.1f} часов",
                reply_markup=keyboard
            )
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Лёг спать", callback_data="sleep_start"),
            InlineKeyboardButton(text="График сна", callback_data="sleep_chart")
        ], [
            InlineKeyboardButton(text="Назад", callback_data="back_to_workout")
        ]])
        try:
            await callback.message.edit_text("Запись не найдена.", reply_markup=keyboard)
        except:
            await callback.message.answer("Запись не найдена.", reply_markup=keyboard)


@dp.callback_query(F.data == "sleep_chart")
async def sleep_chart(callback: CallbackQuery):
    """График сна"""
    await callback.answer()
    await callback.message.answer("Генерирую график сна...")
    
    sleep_records = db.get_sleep_records(days=7)
    avg_sleep = db.get_average_sleep(days=7)
    
    # Клавиатура с кнопкой "Назад"
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Назад", callback_data="back_to_sleep")
    ]])
    
    try:
        chart_buf = generate_sleep_chart(sleep_records)
        caption = f"График сна за неделю"
        if avg_sleep:
            avg_hours = avg_sleep / 60
            caption += f"\nСредний сон: {avg_hours:.1f} часов"
            if avg_hours < 6:
                caption += "\n⚠️ Мало сна! Рекомендуется 7-8 часов."
        
        photo_file = BufferedInputFile(chart_buf.read(), filename="sleep_chart.png")
        await callback.message.answer_photo(photo=photo_file, caption=caption, reply_markup=back_keyboard)
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}", reply_markup=back_keyboard)


# Экспорт данных
@dp.message(Command("export"))
@dp.callback_query(F.data == "cmd_export")
async def cmd_export(message_or_callback, state: FSMContext):
    """Экспорт данных в CSV"""
    if isinstance(message_or_callback, CallbackQuery):
        callback = message_or_callback
        await callback.answer()
        message = callback.message
    else:
        message = message_or_callback
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Сессии", callback_data="export_sessions"),
        InlineKeyboardButton(text="Английский", callback_data="export_english"),
        InlineKeyboardButton(text="Сон", callback_data="export_sleep")
    ]])
    
    await message.answer("Что экспортировать?", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("export_"))
async def process_export(callback: CallbackQuery):
    """Обработка экспорта"""
    await callback.answer()
    export_type = callback.data.split("_")[-1]
    
    try:
        if export_type == "sessions":
            sessions = db.get_detailed_sessions(days=365)
            csv_data = export_sessions_to_csv(sessions)
            filename = "sessions.csv"
        elif export_type == "english":
            phrases = db.get_all_english_phrases()
            reviews = []  # Можно добавить получение reviews
            csv_data = export_english_to_csv(phrases, reviews)
            filename = "english_progress.csv"
        elif export_type == "sleep":
            sleep_records = db.get_sleep_records(days=365)
            csv_data = export_sleep_to_csv(sleep_records)
            filename = "sleep.csv"
        else:
            await callback.message.answer("Неизвестный тип экспорта.")
            return
        
        # Отправляем CSV как документ
        from aiogram.types import BufferedInputFile
        csv_file = BufferedInputFile(csv_data.encode('utf-8'), filename=filename)
        await callback.message.answer_document(document=csv_file, caption=f"Экспорт: {filename}")
    except Exception as e:
        await callback.message.answer(f"Ошибка при экспорте: {e}")


# Старый обработчик английского (SRS) - УДАЛЕН, заменен на неправильные глаголы в обработчике ENG


# Инициализация FastAPI приложения
app = FastAPI(title="Telegram Bot Напарник")


@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "bot": "Напарник"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "bot": "Напарник"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """Обработчик webhook от Telegram"""
    try:
        # Получаем обновление от Telegram
        update_dict = await request.json()
        update = Update(**update_dict)
        
        # Обрабатываем обновление через диспетчер
        # В aiogram 3 используется feed_update для обработки обновлений
        await dp.feed_update(bot=bot, update=update)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"ok": True}
        )
    except Exception as e:
        print(f"Ошибка при обработке webhook: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"ok": False, "error": str(e)}
        )


async def setup_webhook():
    """Настройка webhook при старте приложения"""
    global bot  # Объявляем global в начале функции
    
    # Получаем URL для webhook (поддержка различных платформ)
    # Приоритет: WEBHOOK_URL > RENDER_EXTERNAL_URL > SCALINGO_APP_URL > SCALINGO_URL
    webhook_url_env = os.getenv("WEBHOOK_URL")  # Для VPS и кастомных деплоев
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    scalingo_url = os.getenv("SCALINGO_APP_URL") or os.getenv("SCALINGO_URL")
    
    # Если WEBHOOK_URL установлен напрямую, используем его
    if webhook_url_env:
        webhook_url = webhook_url_env
    else:
        # Иначе собираем из базового URL
        app_url = render_url or scalingo_url
        
        if not app_url:
            print("⚠️  URL приложения не установлен. Webhook не будет установлен.")
            print("   Для локальной разработки это нормально - используется polling.")
            print("   Для деплоя установите WEBHOOK_URL, RENDER_EXTERNAL_URL или SCALINGO_APP_URL.")
            return
        
        webhook_url = f"{app_url}/webhook"
    
    # ВСЕГДА пересоздаем объект бота с токеном из окружения
    # Это гарантирует, что используется актуальный токен
    current_token_from_env = os.getenv("BOT_TOKEN", "").strip()
    if not current_token_from_env:
        print("❌ BOT_TOKEN не найден в окружении!")
        return
    
    # Очищаем токен от всех невидимых символов
    current_token_from_env = ''.join(char for char in current_token_from_env if char.isprintable())
    current_token_from_env = current_token_from_env.strip()
    
    # Проверяем формат токена (должен быть число:строка)
    if ':' not in current_token_from_env:
        print(f"❌ Неверный формат токена! Токен должен быть в формате 'число:строка'")
        return
    
    print(f"DEBUG: Пересоздаем объект бота с токеном из окружения")
    print(f"DEBUG: Токен из окружения: {current_token_from_env[:20]}... (длина: {len(current_token_from_env)})")
    print(f"DEBUG: Проверка токена через getMe...")
    
    # Проверяем токен через getMe перед установкой webhook
    try:
        check_url = f"https://api.telegram.org/bot{current_token_from_env}/getMe"
        async with aiohttp.ClientSession() as session:
            async with session.get(check_url) as response:
                check_result = await response.json()
                if check_result.get("ok"):
                    bot_info = check_result.get("result", {})
                    print(f"DEBUG: Токен валиден! Бот: @{bot_info.get('username', 'unknown')}")
                else:
                    print(f"❌ Токен невалиден! Ответ API: {check_result}")
                    raise Exception(f"Токен не прошел проверку: {check_result.get('description', 'Unknown error')}")
    except Exception as check_error:
        print(f"❌ Ошибка при проверке токена: {check_error}")
        raise
    
    # Закрываем старую сессию, если есть
    try:
        await bot.session.close()
    except:
        pass
    
    # Создаем новый объект бота с токеном из окружения
    temp_bot = Bot(token=current_token_from_env)
    
    print(f"DEBUG: Webhook URL: {webhook_url}")
    
    # Удаляем старый webhook (если есть) используя новый объект бота
    try:
        await temp_bot.delete_webhook(drop_pending_updates=True)
        print("✓ Старый webhook удален")
    except Exception as e:
        print(f"⚠️  Ошибка при удалении старого webhook: {e}")
        # Не критично, продолжаем
    
    # Используем прямой API запрос как основной способ (более надежно)
    print(f"DEBUG: Устанавливаем webhook через прямой API запрос...")
    try:
        api_url = f"https://api.telegram.org/bot{current_token_from_env}/setWebhook"
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json={
                "url": webhook_url,
                "drop_pending_updates": True
            }) as response:
                result = await response.json()
                if result.get("ok"):
                    print(f"✓ Webhook установлен через API: {webhook_url}")
                    # Обновляем глобальный объект bot
                    bot = temp_bot
                else:
                    error_desc = result.get('description', 'Unknown error')
                    print(f"❌ Ошибка при установке webhook через API: {error_desc}")
                    print(f"DEBUG: Полный ответ API: {result}")
                    # Пробуем через aiogram как fallback
                    try:
                        await temp_bot.set_webhook(
                            url=webhook_url,
                            drop_pending_updates=True
                        )
                        print(f"✓ Webhook установлен через aiogram (fallback): {webhook_url}")
                        bot = temp_bot
                    except Exception as aiogram_error:
                        print(f"❌ Ошибка при установке webhook через aiogram: {aiogram_error}")
                        raise Exception(f"Не удалось установить webhook: {error_desc}")
    except Exception as api_error:
        print(f"❌ Ошибка при установке webhook через API: {api_error}")
        import traceback
        traceback.print_exc()
        raise


async def notification_scheduler():
    """Фоновая задача для автоматических уведомлений"""
    while True:
        try:
            await asyncio.sleep(60)  # Проверяем каждую минуту
            
            now = datetime.now()
            current_hour = now.hour
            current_minute = now.minute
            current_weekday = now.weekday()  # 0=понедельник, 6=воскресенье
            
            # Получаем user_id из БД
            user_id = db.get_user_id()
            if not user_id:
                continue  # Пользователь еще не использовал бота
            
            # Проверяем, что сейчас 20:00
            if current_hour == 20 and current_minute == 0:
                # Уведомление о тепловой карте каждые 14 дней (на 14-й день и далее каждые 14 дней)
                days_since_first = db.get_days_since_first_session()
                if days_since_first is not None and days_since_first >= 14 and days_since_first % 14 == 0:
                    last_notification = db.get_last_heatmap_notification_date()
                    today = datetime.now().strftime("%Y-%m-%d")
                    
                    if last_notification != today:
                        # Генерируем тепловую карту и отправляем
                        sessions = db.get_detailed_sessions(days=14)
                        if sessions:
                            try:
                                heatmap_buf = generate_productivity_heatmap(sessions)
                                photo_file = BufferedInputFile(heatmap_buf.read(), filename="productivity.png")
                                
                                await bot.send_photo(
                                    chat_id=user_id,
                                    photo=photo_file,
                                    caption="Твоя тепловая карта готова. Взгляни!"
                                )
                                db.mark_heatmap_notification_sent()
                                print(f"Отправлено уведомление о тепловой карте пользователю {user_id}")
                            except Exception as e:
                                print(f"Ошибка при отправке уведомления о тепловой карте: {e}")
                
                # Уведомление о графике сна каждое воскресенье
                if current_weekday == 6:  # Воскресенье
                    last_notification = db.get_last_sleep_chart_notification_date()
                    today = datetime.now().strftime("%Y-%m-%d")
                    
                    if last_notification != today:
                        # Генерируем график сна и отправляем
                        sleep_records = db.get_sleep_records(days=7)
                        if sleep_records:
                            try:
                                chart_buf = generate_sleep_chart(sleep_records)
                                photo_file = BufferedInputFile(chart_buf.read(), filename="sleep_chart.png")
                                
                                await bot.send_photo(
                                    chat_id=user_id,
                                    photo=photo_file,
                                    caption="Сделал твой график сна. Взгляни!"
                                )
                                db.mark_sleep_chart_notification_sent()
                                print(f"Отправлено уведомление о графике сна пользователю {user_id}")
                            except Exception as e:
                                print(f"Ошибка при отправке уведомления о графике сна: {e}")
        except Exception as e:
            print(f"Ошибка в notification_scheduler: {e}")
            await asyncio.sleep(60)


@app.on_event("startup")
async def on_startup():
    """Действия при запуске приложения (только для webhook режима)"""
    print("Бот «Напарник» v2.0 запускается...")
    
    # Инициализация неправильных глаголов
    try:
        verbs = db.get_all_irregular_verbs()
        if len(verbs) < 50:  # Если глаголов мало, загружаем
            print("Инициализация базы неправильных глаголов...")
            count = 0
            for form1, form2, form3, translation, example2, example3 in IRREGULAR_VERBS:
                try:
                    db.add_irregular_verb(form1, form2, form3, translation, example2, example3)
                    count += 1
                except:
                    pass  # Глагол уже существует
            print(f"Загружено {count} неправильных глаголов")
    except Exception as e:
        print(f"Ошибка при инициализации глаголов: {e}")
    
    await setup_webhook()
    
    # Запускаем фоновую задачу для уведомлений
    asyncio.create_task(notification_scheduler())
    
    print("Бот готов к работе!")


@app.on_event("shutdown")
async def on_shutdown():
    """Действия при остановке приложения"""
    print("Остановка бота...")
    await bot.session.close()
    print("Бот остановлен")


# Главная функция запуска
async def run_polling():
    """Запуск бота через polling (для локальной разработки)"""
    print("Бот «Напарник» v2.0 запускается в режиме polling...")
    
    # Инициализация неправильных глаголов
    try:
        verbs = db.get_all_irregular_verbs()
        if len(verbs) < 50:  # Если глаголов мало, загружаем
            print("Инициализация базы неправильных глаголов...")
            count = 0
            for form1, form2, form3, translation, example2, example3 in IRREGULAR_VERBS:
                try:
                    db.add_irregular_verb(form1, form2, form3, translation, example2, example3)
                    count += 1
                except:
                    pass  # Глагол уже существует
            print(f"Загружено {count} неправильных глаголов")
    except Exception as e:
        print(f"Ошибка при инициализации глаголов: {e}")
    
    # Удаляем webhook, если был установлен
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✓ Webhook удален, переходим на polling")
    except Exception as e:
        print(f"⚠️  Ошибка при удалении webhook: {e}")
    
    # Запускаем фоновую задачу для уведомлений
    asyncio.create_task(notification_scheduler())
    
    print("Бот готов к работе! Используется polling для локальной разработки.")
    # Запускаем polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


def main():
    """Главная функция для запуска приложения"""
    # Проверяем переменные окружения для определения режима работы
    webhook_url = os.getenv("WEBHOOK_URL")
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    scalingo_url = os.getenv("SCALINGO_APP_URL") or os.getenv("SCALINGO_URL")
    deploy_mode = os.getenv("DEPLOY_MODE", "").lower() == "true"
    
    # Отладочный вывод для диагностики
    print(f"DEBUG: WEBHOOK_URL = {webhook_url}")
    print(f"DEBUG: has_webhook_url = {bool(webhook_url or render_url or scalingo_url)}")
    
    # Определяем, есть ли URL для webhook
    has_webhook_url = webhook_url or render_url or scalingo_url
    
    # Режим деплоя (webhook): если явно указан DEPLOY_MODE=true или есть URL для webhook
    # Это позволяет запускать webhook режим даже локально для тестирования
    if deploy_mode or has_webhook_url:
        print("🚀 Режим деплоя: используется webhook")
        # Используем PORT из окружения или дефолтный 3000
        port = int(os.getenv("PORT", 3000))
        
        # Запускаем FastAPI приложение
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
    else:
        # Режим локальной разработки: используем polling
        # PORT из .env игнорируется в этом режиме
        print("🔧 Режим локальной разработки: используется polling")
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
