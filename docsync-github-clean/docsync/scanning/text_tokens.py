"""
text_tokens.py

Техническое назначение:
    Низкоуровневая работа с текстом документа.

Модуль умеет:
    - выделять отдельные слова из текста;
    - определять номер строки по позиции символа;
    - строить короткий контекст вокруг найденного совпадения.

Граница ответственности:
    Модуль не знает про реестр знаний, кандидатов, отчеты и документы проекта.
    Он работает только с обычной строкой текста.
"""

import re

from docsync.models import Token


# Сколько символов слева и справа показывать вокруг найденного слова.
# Контекст нужен, чтобы в отчете было видно место ошибки без открытия файла.
CONTEXT_RADIUS = 45

# Токен - это отдельное слово в обычном тексте.
# Сейчас считаем словом последовательность русских или английских букв.
WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё]+")


def get_line_number(text: str, position: int) -> int:
    """
    Возвращает номер строки по позиции символа в тексте.
    """
    return text.count("\n", 0, position) + 1


def build_context(text: str, start: int, end: int) -> str:
    """
    Возвращает короткий фрагмент текста вокруг найденного совпадения.

    Найденное слово оборачивается в квадратные скобки. Так в отчете сразу видно,
    где именно находится кандидат.
    """
    context_start = max(0, start - CONTEXT_RADIUS)
    context_end = min(len(text), end + CONTEXT_RADIUS)

    before = text[context_start:start]
    matched = text[start:end]
    after = text[end:context_end]

    context = f"{before}[{matched}]{after}"
    return " ".join(context.split())


def extract_tokens(text: str) -> list[Token]:
    """
    Разбивает обычный текст на отдельные слова.

    Это нужно для поиска возможных опечаток. Нечеткий поиск лучше делать
    не по всему документу сразу, а по отдельным словам.
    """
    return [Token(text=match.group(0), position=match.start()) for match in WORD_PATTERN.finditer(text)]