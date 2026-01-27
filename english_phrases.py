"""
Модуль с английскими фразами для изучения.
Фразы подобраны для уровня A2+.
"""

# Список фраз: (английская фраза, перевод, пример использования)
ENGLISH_PHRASES = [
    (
        "I'm used to it",
        "Я к этому привык",
        "I'm used to working late. — Я привык работать допоздна."
    ),
    (
        "It's up to you",
        "Решать тебе",
        "What should we do? It's up to you. — Что нам делать? Решать тебе."
    ),
    (
        "I can't help it",
        "Я ничего не могу с этим поделать",
        "I can't help feeling nervous. — Я не могу не нервничать."
    ),
    (
        "That makes sense",
        "Это имеет смысл",
        "Your explanation makes sense. — Твое объяснение имеет смысл."
    ),
    (
        "I'm looking forward to",
        "Я с нетерпением жду",
        "I'm looking forward to the weekend. — Я с нетерпением жду выходных."
    ),
    (
        "It's worth it",
        "Это того стоит",
        "The course is expensive, but it's worth it. — Курс дорогой, но это того стоит."
    ),
    (
        "I'm running out of",
        "У меня заканчивается",
        "I'm running out of time. — У меня заканчивается время."
    ),
    (
        "Let me know",
        "Дай мне знать",
        "Let me know when you're ready. — Дай мне знать, когда будешь готов."
    ),
    (
        "I'm in the middle of",
        "Я в процессе",
        "I'm in the middle of something. — Я в процессе чего-то."
    ),
    (
        "It depends on",
        "Это зависит от",
        "It depends on the weather. — Это зависит от погоды."
    ),
    (
        "I'm getting used to",
        "Я привыкаю к",
        "I'm getting used to the new schedule. — Я привыкаю к новому расписанию."
    ),
    (
        "That's the point",
        "В этом и суть",
        "That's the point of practice. — В этом и суть практики."
    ),
    (
        "I'm not sure",
        "Я не уверен",
        "I'm not sure about that. — Я не уверен в этом."
    ),
    (
        "It doesn't matter",
        "Неважно",
        "It doesn't matter what you choose. — Неважно, что ты выберешь."
    ),
    (
        "I'll figure it out",
        "Я разберусь",
        "Don't worry, I'll figure it out. — Не волнуйся, я разберусь."
    ),
]


def get_random_phrase() -> tuple[str, str, str]:
    """
    Получить случайную фразу.
    
    Returns:
        Кортеж (фраза, перевод, пример)
    """
    import random
    return random.choice(ENGLISH_PHRASES)


def get_phrase_by_index(index: int) -> tuple[str, str, str]:
    """
    Получить фразу по индексу.
    
    Args:
        index: Индекс фразы
    
    Returns:
        Кортеж (фраза, перевод, пример)
    """
    if 0 <= index < len(ENGLISH_PHRASES):
        return ENGLISH_PHRASES[index]
    return ENGLISH_PHRASES[0]
