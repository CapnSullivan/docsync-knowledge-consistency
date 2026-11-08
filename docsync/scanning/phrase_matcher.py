"""
phrase_matcher.py

Техническое назначение:
    Поиск возможных опечаток внутри многословных канонических фраз.

Зачем нужен отдельный модуль:
    Обычный поиск опечаток в find_term_candidates.py работает по одному слову:
    mana -> mane. Для фраз этого мало, потому что ошибка может быть внутри
    одного слова большой фразы: Game abaut of might and magik.

Ограничение первой версии:
    Фраза-кандидат должна иметь такое же количество слов, как канон.
    Допускается максимум одно ошибочное значимое слово.
    Короткие слова вроде of, in, to не исправляются как отдельные ошибки.
"""

from pathlib import Path

from docsync.models import Candidate, Token
from docsync.registry import RegistryEntry
from docsync.scanning.text_tokens import build_context, extract_tokens, get_line_number


MAX_BAD_WORDS = 1
MAX_WORD_DISTANCE = 2
MIN_SIGNIFICANT_WORD_LENGTH = 4


def levenshtein_distance(left: str, right: str) -> int:
    """
    Считает расстояние Левенштейна между двумя словами.

    Это локальная копия алгоритма для фразового поиска. Позже ее можно вынести
    в общий модуль, если похожие сравнения начнут использоваться в нескольких местах.
    """
    left = left.lower()
    right = right.lower()

    if left == right:
        return 0

    if not left:
        return len(right)

    if not right:
        return len(left)

    previous_row = list(range(len(right) + 1))

    for left_index, left_char in enumerate(left, start=1):
        current_row = [left_index]

        for right_index, right_char in enumerate(right, start=1):
            insert_cost = current_row[right_index - 1] + 1
            delete_cost = previous_row[right_index] + 1
            replace_cost = previous_row[right_index - 1] + (left_char != right_char)
            current_row.append(min(insert_cost, delete_cost, replace_cost))

        previous_row = current_row

    return previous_row[-1]


def ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    """
    Проверяет, пересекаются ли два диапазона символов.
    """
    return left[0] < right[1] and right[0] < left[1]


def overlaps_occupied_position(
    candidate_range: tuple[int, int],
    occupied_positions: set[tuple[int, int]],
) -> bool:
    """
    Проверяет, не попадает ли фраза в уже найденное точное совпадение.

    Это снижает дубли: если точный или suspicious-вариант уже найден обычным
    поиском, фразовый поиск не должен выводить то же место второй раз.
    """
    return any(
        ranges_overlap(candidate_range, occupied_range)
        for occupied_range in occupied_positions
    )


def build_window_text(text: str, window_tokens: list[Token]) -> str:
    """
    Возвращает исходный текст фразы из документа между первым и последним словом.

    Так сохраняются пробелы и символы между словами, если они были в документе.
    """
    start_position = window_tokens[0].position
    end_position = window_tokens[-1].position + len(window_tokens[-1].text)
    return text[start_position:end_position]


def compare_phrase_window(
    canonical_tokens: list[Token],
    window_tokens: list[Token],
) -> int | None:
    """
    Сравнивает канон и окно документа одинаковой длины по словам.

    Возвращает суммарную дистанцию, если окно похоже на канон.
    Возвращает None, если окно слишком отличается.
    """
    bad_word_count = 0
    total_distance = 0

    for canonical_token, window_token in zip(canonical_tokens, window_tokens):
        canonical_word = canonical_token.text
        window_word = window_token.text

        if canonical_word.lower() == window_word.lower():
            continue

        if len(canonical_word) < MIN_SIGNIFICANT_WORD_LENGTH:
            return None

        if len(window_word) < MIN_SIGNIFICANT_WORD_LENGTH:
            return None

        if abs(len(canonical_word) - len(window_word)) > MAX_WORD_DISTANCE:
            return None

        distance = levenshtein_distance(canonical_word, window_word)

        if distance == 0 or distance > MAX_WORD_DISTANCE:
            return None

        bad_word_count += 1
        total_distance += distance

        if bad_word_count > MAX_BAD_WORDS:
            return None

    if bad_word_count == 0:
        return None

    return total_distance


def find_phrase_typo_candidates(
    text: str,
    file_path: Path,
    registry: list[RegistryEntry],
    occupied_positions: set[tuple[int, int]],
) -> list[Candidate]:
    """
    Ищет возможные опечатки в многословных канонических фразах.

    Алгоритм:
        1. Берет многословный canonical из реестра.
        2. Разбивает документ на слова.
        3. Двигает по документу окно той же длины, что canonical.
        4. Сравнивает слова внутри окна.
        5. Если отличие небольшое, возвращает Candidate на всю фразу.
    """
    candidates = []
    document_tokens = extract_tokens(text)

    for entry in registry:
        canonical_tokens = extract_tokens(entry.canonical)
        canonical_word_count = len(canonical_tokens)

        if canonical_word_count < 2:
            continue

        if len(document_tokens) < canonical_word_count:
            continue

        for start_index in range(0, len(document_tokens) - canonical_word_count + 1):
            window_tokens = document_tokens[start_index:start_index + canonical_word_count]
            start_position = window_tokens[0].position
            end_position = window_tokens[-1].position + len(window_tokens[-1].text)
            candidate_range = (start_position, end_position)

            if overlaps_occupied_position(candidate_range, occupied_positions):
                continue

            distance = compare_phrase_window(canonical_tokens, window_tokens)

            if distance is None:
                continue

            matched_text = build_window_text(text, window_tokens)
            candidates.append(
                Candidate(
                    key=entry.key,
                    match_type="possible_phrase_typo",
                    matched_text=matched_text,
                    file_path=file_path,
                    line_number=get_line_number(text, start_position),
                    start_position=start_position,
                    end_position=end_position,
                    context=build_context(text, start_position, end_position),
                    suggested_text=entry.canonical,
                    distance=distance,
                )
            )
            occupied_positions.add(candidate_range)

    return candidates
