"""
reports.py

Техническое назначение:
    Модуль отвечает только за вывод результата проверки в консоль.

Граница ответственности:
    Этот модуль не сканирует документы, не читает реестр и не ищет ошибки.
    Он получает готовый ScanResult и список записей реестра, после чего печатает отчет.

Режимы отчета:
    Краткий режим используется по умолчанию. Он показывает результат глазами
    оператора: какие документы проверены, в каких документах есть проблемы,
    какие места нужно открыть и исправить.

    Подробный режим нужен для отладки. Он показывает все найденные совпадения,
    включая корректные совпадения и допустимые варианты.
"""

from pathlib import Path

from docsync.models import Candidate, ScanResult
from docsync.registry import RegistryEntry


# Эти типы считаются проблемами, а не просто найденными упоминаниями.
PROBLEM_MATCH_TYPES = {"case_mismatch", "suspicious", "possible_typo", "possible_phrase_typo"}


def relative_path(file_path: Path, documents_dir: Path) -> str:
    """
    Делает путь короче для отчета.

    Вместо полного пути на диске показывает путь внутри проверяемой папки документов.
    Так отчет легче читать.
    """
    return str(file_path.relative_to(documents_dir))


def get_match_type_label(match_type: str) -> str:
    labels = {
        "canonical": "корректное совпадение",
        "case_mismatch": "отличие только в регистре",
        "alias": "допустимый вариант",
        "suspicious": "известное несоответствие",
        "possible_typo": "возможная опечатка",
        "possible_phrase_typo": "возможная опечатка во фразе",
    }
    return labels.get(match_type, match_type)


def is_latin_letter(character: str) -> bool:
    return "A" <= character <= "Z" or "a" <= character <= "z"


def is_cyrillic_letter(character: str) -> bool:
    return "А" <= character <= "я" or character in {"Ё", "ё"}


def get_script_note(text: str) -> str | None:
    """
    Возвращает предупреждение, если в одном найденном тексте смешаны алфавиты.

    Пример проблемы:
        mana - все буквы латинские;
        manа - последние символ выглядит как латинская a, но это кириллическая а.

    Без такой пометки отчет выглядит абсурдно: найдено manа, должно быть mana.
    Глаз видит почти одно и то же, а Python сравнивает разные Unicode-символы.
    """
    has_latin = any(is_latin_letter(character) for character in text)
    has_cyrillic = any(is_cyrillic_letter(character) for character in text)

    if has_latin and has_cyrillic:
        return "смешаны латиница и кириллица"

    return None


def print_text_with_script_note(prefix: str, text: str) -> None:
    """
    Печатает текст и, если нужно, поясняет невидимую проблему с алфавитами.
    """
    print(f"{prefix}{text}")

    script_note = get_script_note(text)
    if script_note:
        print(f"      предупреждение: {script_note}")


def group_candidates_by_key(candidates: list[Candidate]) -> dict[str, list[Candidate]]:
    grouped_candidates = {}

    for candidate in candidates:
        grouped_candidates.setdefault(candidate.key, []).append(candidate)

    return grouped_candidates


def group_candidates_by_file(candidates: list[Candidate]) -> dict[Path, list[Candidate]]:
    """
    Группирует находки по документам.

    Краткий отчет строится именно так, потому что оператору важнее понять,
    какие файлы нужно открыть, а не какие внутренние ключи сработали в сканере.
    """
    grouped_candidates = {}

    for candidate in candidates:
        grouped_candidates.setdefault(candidate.file_path, []).append(candidate)

    return grouped_candidates


def get_problem_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """
    Возвращает только те находки, которые требуют внимания.

    Это основа краткого отчета: нормальные совпадения не должны создавать шум.
    """
    return [
        candidate
        for candidate in candidates
        if candidate.match_type in PROBLEM_MATCH_TYPES
    ]


def count_problem_candidates(candidates: list[Candidate]) -> int:
    return len(get_problem_candidates(candidates))


def print_compact_summary(
    scan_result: ScanResult,
    registry: list[RegistryEntry],
    problem_count: int,
    problem_document_count: int,
) -> None:
    print("Проверка документов...")
    print()
    print("Проверка завершена.")
    print(f"Терминов в базе: {len(registry)}")
    print(f"Проверено документов: {scan_result.checked_documents_count}")
    print(f"Документов с проблемами: {problem_document_count}")
    print(f"Всего несоответствий: {problem_count}")
    print()


def print_debug_summary(
    scan_result: ScanResult,
    registry: list[RegistryEntry],
    problem_count: int,
) -> None:
    print("Проверка документов...")
    print()
    print("Проверка завершена.")
    print(f"Терминов в базе: {len(registry)}")
    print(f"Проверено документов: {scan_result.checked_documents_count}")
    print(f"Найдено совпадений: {len(scan_result.candidates)}")
    print(f"Требуют внимания: {problem_count}")
    print()


def print_compact_report(
    scan_result: ScanResult,
    registry: list[RegistryEntry],
    documents_dir: Path,
) -> None:
    """
    Печатает основной короткий отчет.

    В этом режиме нет карточек по успешным совпадениям. Если ошибок нет,
    пользователь видит только сводку. Если ошибки есть, они группируются
    по документам, потому что исправление начинается с открытия файла.
    """
    registry_by_key = {entry.key: entry for entry in registry}
    problem_candidates = get_problem_candidates(scan_result.candidates)
    grouped_by_file = group_candidates_by_file(problem_candidates)

    print_compact_summary(
        scan_result=scan_result,
        registry=registry,
        problem_count=len(problem_candidates),
        problem_document_count=len(grouped_by_file),
    )

    if not problem_candidates:
        print("Несоответствия не обнаружены.")
        return

    print("Документы, требующие проверки:")
    print()

    for document_index, file_path in enumerate(sorted(grouped_by_file), start=1):
        file_candidates = sorted(
            grouped_by_file[file_path],
            key=lambda candidate: (candidate.line_number, candidate.key, candidate.matched_text),
        )

        print(f"{document_index}. {relative_path(file_path, documents_dir)}")
        print(f"   Количество несоответствий: {len(file_candidates)}")

        for candidate in file_candidates:
            registry_entry = registry_by_key[candidate.key]
            expected_text = candidate.suggested_text or registry_entry.canonical
            print(f"   Строка {candidate.line_number}: {candidate.key}")
            print_text_with_script_note("      найдено: ", candidate.matched_text)
            print(f"      должно быть: {expected_text}")
            print(f"      тип: {get_match_type_label(candidate.match_type)}")

        print()

    print("Подробный отладочный отчет: python Scripts/docsync_cli.py scan --debug")


def print_detailed_report(
    scan_result: ScanResult,
    registry: list[RegistryEntry],
    documents_dir: Path,
) -> None:
    """
    Печатает подробный отчет по всем найденным совпадениям.

    Это старое поведение отчета, сохраненное для отладки: здесь видны не только
    проблемы, но и корректные совпадения, alias-варианты и контекст вокруг находок.
    """
    registry_by_key = {entry.key: entry for entry in registry}
    candidates = scan_result.candidates
    grouped_candidates = group_candidates_by_key(candidates)
    problem_count = count_problem_candidates(candidates)

    print_debug_summary(scan_result, registry, problem_count)

    if not candidates:
        print("Кандидаты не найдены.")
        return

    for key in sorted(grouped_candidates):
        key_candidates = grouped_candidates[key]
        key_problem_count = count_problem_candidates(key_candidates)
        registry_entry = registry_by_key[key]
        status = "требует внимания" if key_problem_count else "без проблем"

        print("=" * 72)
        print(f"Ключ: {key}")
        print(f"Канон: {registry_entry.canonical}")
        print(f"Статус: {status}")
        print(f"Совпадений: {len(key_candidates)}")
        print(f"Проблем: {key_problem_count}")
        print()

        for index, candidate in enumerate(key_candidates, start=1):
            print(f"{index}. {relative_path(candidate.file_path, documents_dir)}:{candidate.line_number}")
            print(f"   Тип: {get_match_type_label(candidate.match_type)}")
            print_text_with_script_note("   Найдено: ", candidate.matched_text)

            if candidate.match_type in PROBLEM_MATCH_TYPES:
                expected_text = candidate.suggested_text or registry_entry.canonical
                print(f"   Должно быть: {expected_text}")

            if candidate.distance is not None:
                print(f"   Расстояние Левенштейна: {candidate.distance}")

            print(f"   Контекст: {candidate.context}")
            print()


def print_report(
    scan_result: ScanResult,
    registry: list[RegistryEntry],
    documents_dir: Path,
    *,
    detailed: bool = False,
) -> None:
    """
    Единая функция входа для печати отчета.

    detailed=False - основной короткий отчет по документам.
    detailed=True - полный отладочный отчет с карточками всех совпадений.
    """
    if detailed:
        print_detailed_report(scan_result, registry, documents_dir)
        return

    print_compact_report(scan_result, registry, documents_dir)
