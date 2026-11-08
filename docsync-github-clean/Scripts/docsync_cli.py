"""
docsync_cli.py

Интерактивный консольный центр управления прототипом docsync.

Основной режим:
    Если запустить файл без аргументов, откроется текстовое меню.

Дополнительный режим:
    Команды scan, apply-fixes, mutate-demo и reset-demo оставлены для быстрого
    запуска из терминала или будущих автотестов.

Зачем нужен этот файл:
    Пользователь не должен помнить названия всех отдельных скриптов.
    Этот файл собирает основные действия прототипа в одном месте.
"""

import argparse
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from docsync.demo_documents import mutate_demo_documents, reset_demo_documents
from docsync.fixes import (
    apply_selected_fixes,
    get_problem_candidates,
    parse_selected_indexes,
    print_fix_candidates,
    print_fix_results,
    sort_candidates_for_review,
)

import find_term_candidates


def run_scan(*, detailed_report: bool = False) -> None:
    """
    Запускает сканер документов.

    detailed_report=False - обычный короткий отчет без успешных карточек.
    detailed_report=True - полный отладочный отчет со всеми найденными совпадениями.
    """
    find_term_candidates.main(detailed_report=detailed_report)


def run_apply_fixes() -> None:
    """
    Интерактивно применяет выбранные исправления.

    Исправления выбираются по номерам конкретных мест в конкретных документах.
    Это не массовая замена по всему проекту.
    """
    registry = find_term_candidates.load_registry(find_term_candidates.REGISTRY_PATH)
    registry_by_key = {entry.key: entry for entry in registry}
    scan_result = find_term_candidates.scan_documents(registry)
    candidates = sort_candidates_for_review(get_problem_candidates(scan_result.candidates))

    if not candidates:
        print("Несоответствия не обнаружены. Исправлять нечего.")
        return

    print("Найдены места, которые можно исправить:")
    print_fix_candidates(candidates, registry_by_key, find_term_candidates.DOCUMENTS_DIR)
    print()
    print("Введите номера исправлений через запятую, например: 1,3")
    print("Введите all, чтобы выбрать все найденные места.")
    print("Оставьте пустым, чтобы отменить.")

    try:
        selected_indexes = parse_selected_indexes(
            input("Выбор: "),
            max_index=len(candidates),
        )
    except ValueError as error:
        print(f"Ошибка выбора: {error}")
        return

    if not selected_indexes:
        print("Исправления отменены.")
        return

    selected_candidates = [candidates[index - 1] for index in selected_indexes]

    print()
    print("Будут применены исправления:")
    print_fix_candidates(selected_candidates, registry_by_key, find_term_candidates.DOCUMENTS_DIR)
    print()

    confirmation = input("Применить выбранные исправления? y/n: ").strip().lower()

    if confirmation not in {"y", "yes", "д", "да"}:
        print("Исправления отменены.")
        return

    results = apply_selected_fixes(selected_candidates, registry_by_key)
    print_fix_results(results, find_term_candidates.DOCUMENTS_DIR)


def run_mutate_demo(seed: int | None) -> None:
    """
    Восстанавливает тестовые документы и вносит в них искажения.

    seed нужен для воспроизводимости. Если указать одно и то же число,
    генератор выберет одни и те же варианты ошибок.
    """
    mutate_result = mutate_demo_documents(PROJECT_DIR, seed=seed)

    print("Тестовые документы восстановлены и искажены.")
    print()
    print("Выбранные варианты:")

    for name, value in mutate_result.selected_values.items():
        print(f"- {name}: {value}")

    if mutate_result.expected_distortions:
        print()
        print("Ожидаемые проблемы для тестов:")
        for distortion in mutate_result.expected_distortions:
            print(
                f"- {distortion.file_path}: {distortion.key} / "
                f"{distortion.expected_match_type} / {distortion.created_text}"
            )


def run_reset_demo() -> None:
    """
    Возвращает тестовые документы к базовому состоянию.
    """
    reset_demo_documents(PROJECT_DIR)
    print("Тестовые документы восстановлены в базовое состояние.")


def print_menu() -> None:
    print()
    print("Docsync - консольное меню")
    print("=" * 32)
    print("1. Проверить документы")
    print("2. Показать подробный отладочный отчет")
    print("3. Исправить выбранные несоответствия")
    print("4. Испортить тестовые документы случайно")
    print("5. Испортить тестовые документы с seed")
    print("6. Восстановить тестовые документы")
    print("0. Выход")
    print()


def wait_for_enter() -> None:
    input("Нажмите Enter, чтобы вернуться в меню...")


def ask_seed() -> int | None:
    raw_seed = input("Введите seed числом или оставьте пустым: ").strip()

    if not raw_seed:
        return None

    try:
        return int(raw_seed)
    except ValueError:
        print("Seed должен быть целым числом. Команда отменена.")
        return None


def run_interactive_menu() -> None:
    """
    Запускает интерактивный режим.

    Это режим для ручной работы: пользователь выбирает действие цифрой,
    получает результат и возвращается в меню.
    """
    while True:
        print_menu()
        choice = input("Выберите действие: ").strip()
        print()

        if choice == "1":
            run_scan(detailed_report=False)
            wait_for_enter()
        elif choice == "2":
            run_scan(detailed_report=True)
            wait_for_enter()
        elif choice == "3":
            run_apply_fixes()
            wait_for_enter()
        elif choice == "4":
            run_mutate_demo(seed=None)
            wait_for_enter()
        elif choice == "5":
            seed = ask_seed()
            print()
            if seed is not None:
                run_mutate_demo(seed=seed)
            wait_for_enter()
        elif choice == "6":
            run_reset_demo()
            wait_for_enter()
        elif choice == "0":
            print("Выход.")
            return
        else:
            print("Неизвестный пункт меню.")
            wait_for_enter()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Центр управления прототипом docsync."
    )
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser(
        "scan",
        help="проверить рабочие markdown-документы и вывести краткий отчет",
    )
    scan_parser.add_argument(
        "--debug",
        action="store_true",
        help="показать подробный отчет со всеми найденными совпадениями",
    )

    subparsers.add_parser(
        "apply-fixes",
        help="выбрать и применить конкретные исправления по найденным местам",
    )

    mutate_parser = subparsers.add_parser(
        "mutate-demo",
        help="восстановить тестовые документы и внести случайные искажения",
    )
    mutate_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="число для воспроизводимой генерации тестовых искажений",
    )

    subparsers.add_parser(
        "reset-demo",
        help="восстановить стабильную базовую версию тестовых документов",
    )

    return parser


def main() -> None:
    # Если аргументов нет, запускается меню.
    # Если аргументы есть, работает командный режим.
    if len(sys.argv) == 1:
        run_interactive_menu()
        return

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        run_scan(detailed_report=args.debug)
    elif args.command == "apply-fixes":
        run_apply_fixes()
    elif args.command == "mutate-demo":
        run_mutate_demo(seed=args.seed)
    elif args.command == "reset-demo":
        run_reset_demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
