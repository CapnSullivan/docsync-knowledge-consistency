"""
test_full_cycle.py

Этот файл проверяет главный рабочий цикл docsync на контролируемой песочнице.

ВАЖНО:
    Этот тест НЕ проверяет ручное состояние документов, которое пользователь
    оставил перед запуском теста.

    Тест специально сам создает входные данные:
        1. восстанавливает sandbox;
        2. генерирует известный набор искажений через seed=7;
        3. получает от генератора список ожидаемых ошибок;
        4. запускает сканер;
        5. сравнивает ожидаемые ошибки с фактически найденными Candidate;
        6. применяет исправления;
        7. проверяет, что после исправлений проблем не осталось.

Зачем тест сам готовит данные:
    Автотест должен быть повторяемым. Если он будет зависеть от того, что сейчас
    руками лежит в sandbox, он начнет падать или проходить случайно.

Что именно проверяется:
    Не проверяется красивый текст консольного отчета.
    Проверяются данные ядра:
        - относительный путь документа;
        - ключ знания;
        - найденный ошибочный текст;
        - тип найденной проблемы.

Что тест поймает:
    - генератор объявил ошибку, но сканер ее не нашел;
    - сканер нашел ошибку не того типа;
    - сканер нашел лишнюю проблему;
    - apply_selected_fixes не смог применить выбранные исправления;
    - после исправлений остались проблемы.
"""

import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_DIR / "Scripts"
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import find_term_candidates
from docsync.demo_documents import mutate_demo_documents, reset_demo_documents
from docsync.fixes import apply_selected_fixes, get_problem_candidates, sort_candidates_for_review

ProblemSignature = tuple[str, str, str, str]


def format_problem_signature(problem: ProblemSignature) -> str:
    """
    Превращает одну проблему в короткую читаемую строку.

    Формат один и тот же для ожидаемых проблем генератора и фактических
    проблем сканера, поэтому при падении теста сразу видно расхождение.
    """
    file_path, key, text, match_type = problem
    return f"- {file_path} | {key} | {match_type} | {text}"


def build_problem_mismatch_message(
    expected: list[ProblemSignature],
    actual: list[ProblemSignature],
) -> str:
    """
    Строит понятное сообщение о несовпадении expected и actual.

    Обычный assertEqual для списков печатает большую нечитаемую простыню.
    Здесь выводится только полезная разница:
        - что ожидалось, но не найдено;
        - что найдено лишним.
    """
    expected_set = set(expected)
    actual_set = set(actual)

    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)

    message_parts = ["Найденные проблемы не совпали с ожидаемыми."]

    if missing:
        message_parts.append("")
        message_parts.append("Ожидались, но не найдены:")
        message_parts.extend(format_problem_signature(problem) for problem in missing)

    if extra:
        message_parts.append("")
        message_parts.append("Найдены лишние:")
        message_parts.extend(format_problem_signature(problem) for problem in extra)

    return "\n".join(message_parts)


class FullCycleTest(unittest.TestCase):
    def setUp(self) -> None:
        """
        Перед каждым тестом возвращаем sandbox к базовому состоянию.

        Это защита от ручных правок и от результатов предыдущих запусков.
        Тест должен начинаться из известной точки, иначе его результат нельзя
        считать надежным.
        """
        reset_demo_documents(PROJECT_DIR)

    def tearDown(self) -> None:
        """
        После теста снова возвращаем sandbox к базовому состоянию.

        Это нужно, чтобы запуск теста не оставлял после себя испорченные документы.
        """
        reset_demo_documents(PROJECT_DIR)

    def assert_problem_signatures_equal(
        self,
        expected: list[ProblemSignature],
        actual: list[ProblemSignature],
    ) -> None:
        """
        Сравнивает ожидаемые и фактические проблемы с читаемым сообщением.
        """
        if expected == actual:
            return

        self.fail(build_problem_mismatch_message(expected, actual))

    def test_seed_7_expected_distortions_are_found_and_fixed(self) -> None:
        """
        Проверяет полный цикл на известном сценарии seed=7.

        seed=7 выбран как фиксированный сценарий, где генератор создает несколько
        разных типов проблем:
            - suspicious;
            - possible_phrase_typo.

        Тест не сверяет только количество. Он сверяет конкретный набор проблем,
        который генератор обещал создать, с тем, что реально нашел сканер.
        """
        # Шаг 1. Генератор сам создает документы и возвращает контракт ожиданий.
        # Контракт - это список expected_distortions: какие ошибки должны быть найдены.
        mutate_result = mutate_demo_documents(PROJECT_DIR, seed=7)

        # Шаг 2. Загружаем реестр знаний. Он нужен сканеру и модулю исправлений.
        registry = find_term_candidates.load_registry(find_term_candidates.REGISTRY_PATH)
        registry_by_key = {entry.key: entry for entry in registry}

        # Шаг 3. Сканер независимо анализирует документы.
        # Он не читает expected_distortions и не знает, что генератор ожидал найти.
        scan_result = find_term_candidates.scan_documents(registry)
        problem_candidates = sort_candidates_for_review(
            get_problem_candidates(scan_result.candidates)
        )

        # Шаг 4. Приводим ожидания генератора к простой сравнимой форме.
        # Здесь намеренно нет line_number и позиций: для этого теста важны
        # документ, ключ, найденный текст и тип проблемы.
        expected = sorted(
            (
                distortion.file_path,
                distortion.key,
                distortion.created_text,
                distortion.expected_match_type,
            )
            for distortion in mutate_result.expected_distortions
        )

        # Шаг 5. Приводим реальные находки сканера к такой же форме.
        actual = sorted(
            (
                candidate.file_path.relative_to(find_term_candidates.DOCUMENTS_DIR).as_posix(),
                candidate.key,
                candidate.matched_text,
                candidate.match_type,
            )
            for candidate in problem_candidates
        )

        # Главная проверка: сканер должен найти ровно те проблемы,
        # которые генератор заранее объявил ожидаемыми.
        self.assert_problem_signatures_equal(expected, actual)

        # Шаг 6. Проверяем модуль исправлений на тех Candidate, которые нашел сканер.
        # Исправления применяются по точным позициям внутри файлов.
        fix_results = apply_selected_fixes(problem_candidates, registry_by_key)
        self.assertEqual(len(mutate_result.expected_distortions), len(fix_results))
        self.assertTrue(all(result.applied for result in fix_results))

        # Шаг 7. Повторный scan должен показать, что найденные проблемы исчезли.
        final_scan_result = find_term_candidates.scan_documents(registry)
        final_problem_candidates = get_problem_candidates(final_scan_result.candidates)
        self.assertEqual([], final_problem_candidates)


if __name__ == "__main__":
    unittest.main()
