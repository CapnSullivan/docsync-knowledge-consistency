"""
fixes.py

Техническое назначение:
    Модуль отвечает за применение выбранных исправлений к документам.

Граница ответственности:
    Модуль не ищет проблемы сам. Он получает уже найденные Candidate из сканера
    и применяет только те исправления, которые пользователь выбрал явно.

Главный принцип безопасности:
    Исправление применяется не "по всему проекту" и не "по всем похожим словам".
    Исправление применяется к конкретному месту: файл + start_position + end_position.
    Перед заменой модуль проверяет, что в этом месте файла до сих пор лежит
    тот текст, который нашел сканер.
"""

from dataclasses import dataclass
from pathlib import Path

from docsync.models import Candidate
from docsync.registry import RegistryEntry
from docsync.reports import PROBLEM_MATCH_TYPES, get_match_type_label, relative_path


@dataclass
class FixResult:
    """
    Результат попытки применить одно исправление.
    """
    candidate: Candidate
    replacement_text: str
    applied: bool
    message: str


def get_expected_text(candidate: Candidate, registry_by_key: dict[str, RegistryEntry]) -> str:
    """
    Возвращает предлагаемую замену для найденной проблемы.

    Для possible_typo сканер может уже подготовить suggested_text.
    Для suspicious и case_mismatch берется canonical из реестра.
    """
    if candidate.suggested_text:
        return candidate.suggested_text

    return registry_by_key[candidate.key].canonical


def get_problem_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """
    Оставляет только проблемы, которые можно предлагать пользователю для действия.
    """
    return [
        candidate
        for candidate in candidates
        if candidate.match_type in PROBLEM_MATCH_TYPES
    ]


def sort_candidates_for_review(candidates: list[Candidate]) -> list[Candidate]:
    """
    Сортирует проблемы так, как удобно человеку: сначала документ, потом строка.
    """
    return sorted(
        candidates,
        key=lambda candidate: (
            str(candidate.file_path),
            candidate.line_number,
            candidate.start_position,
            candidate.key,
        ),
    )


def print_fix_candidates(
    candidates: list[Candidate],
    registry_by_key: dict[str, RegistryEntry],
    documents_dir: Path,
) -> None:
    """
    Печатает список конкретных мест, которые можно исправить.

    Каждый пункт получает номер. Пользователь выбирает именно номера мест,
    а не общий тип проблемы и не весь термин сразу.
    """
    current_file = None

    for index, candidate in enumerate(candidates, start=1):
        if candidate.file_path != current_file:
            current_file = candidate.file_path
            print()
            print(relative_path(candidate.file_path, documents_dir))

        expected_text = get_expected_text(candidate, registry_by_key)
        print(f"[{index}] строка {candidate.line_number}: {candidate.key}")
        print(f"    найдено: {candidate.matched_text}")
        print(f"    заменить на: {expected_text}")
        print(f"    тип: {get_match_type_label(candidate.match_type)}")


def parse_selected_indexes(raw_value: str, max_index: int) -> list[int]:
    """
    Разбирает ввод пользователя.

    Поддерживаются форматы:
        1,3,4
        all
        пустая строка для отмены
    """
    raw_value = raw_value.strip().lower()

    if not raw_value:
        return []

    if raw_value == "all":
        return list(range(1, max_index + 1))

    selected_indexes = []

    for part in raw_value.split(","):
        part = part.strip()

        if not part:
            continue

        try:
            index = int(part)
        except ValueError:
            raise ValueError(f"Номер должен быть числом: {part}") from None

        if index < 1 or index > max_index:
            raise ValueError(f"Номер вне списка: {index}")

        if index not in selected_indexes:
            selected_indexes.append(index)

    return selected_indexes


def apply_selected_fixes(
    candidates: list[Candidate],
    registry_by_key: dict[str, RegistryEntry],
) -> list[FixResult]:
    """
    Применяет выбранные исправления.

    Замены внутри каждого файла выполняются с конца к началу. Это нужно, чтобы
    более ранняя замена не сдвинула позиции более поздних замен в том же файле.
    """
    results = []
    candidates_by_file = {}

    for candidate in candidates:
        if candidate.file_path.suffix.lower() != ".md":
            results.append(
                FixResult(
                    candidate=candidate,
                    replacement_text=get_expected_text(candidate, registry_by_key),
                    applied=False,
                    message="автоисправление поддерживается только для markdown",
                )
            )
            continue

        candidates_by_file.setdefault(candidate.file_path, []).append(candidate)

    for file_path, file_candidates in candidates_by_file.items():
        text = file_path.read_text(encoding="utf-8")
        updated_text = text
        file_results = []

        for candidate in sorted(file_candidates, key=lambda item: item.start_position, reverse=True):
            expected_text = get_expected_text(candidate, registry_by_key)
            current_text = updated_text[candidate.start_position:candidate.end_position]

            if current_text != candidate.matched_text:
                file_results.append(
                    FixResult(
                        candidate=candidate,
                        replacement_text=expected_text,
                        applied=False,
                        message="место в документе изменилось после сканирования",
                    )
                )
                continue

            updated_text = (
                updated_text[:candidate.start_position]
                + expected_text
                + updated_text[candidate.end_position:]
            )
            file_results.append(
                FixResult(
                    candidate=candidate,
                    replacement_text=expected_text,
                    applied=True,
                    message="исправлено",
                )
            )

        if updated_text != text:
            file_path.write_text(updated_text, encoding="utf-8")

        results.extend(reversed(file_results))

    return results


def print_fix_results(results: list[FixResult], documents_dir: Path) -> None:
    """
    Печатает итог применения выбранных исправлений.
    """
    applied_count = sum(1 for result in results if result.applied)
    skipped_count = len(results) - applied_count

    print()
    print("Применение исправлений завершено.")
    print(f"Исправлено: {applied_count}")
    print(f"Пропущено: {skipped_count}")

    if skipped_count:
        print()
        print("Пропущенные исправления:")

        for result in results:
            if result.applied:
                continue

            candidate = result.candidate
            print(
                f"- {relative_path(candidate.file_path, documents_dir)}:{candidate.line_number} "
                f"{candidate.key} - {result.message}"
            )
