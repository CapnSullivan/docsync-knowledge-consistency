import argparse
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

# При запуске скрипта напрямую Python добавляет в import-пути папку Scripts.
# Пакет docsync лежит рядом с Scripts, то есть в корне проекта.
# Поэтому корень проекта добавляется явно, чтобы импорт docsync работал.
sys.path.insert(0, str(PROJECT_DIR))

from docsync.models import Candidate, DocumentText, ScanResult
from docsync.readers.docx_reader import read_docx_document
from docsync.readers.markdown_reader import read_markdown_document
from docsync.scanning.phrase_matcher import find_phrase_typo_candidates
from docsync.registry import RegistryEntry, load_registry
from docsync.reports import print_report
from docsync.scanning.text_tokens import build_context, extract_tokens, get_line_number


DOCUMENTS_DIR = PROJECT_DIR / "documents_sandbox" / "game_knowledge"
SOURCE_DIR = DOCUMENTS_DIR / "source"
REGISTRY_PATH = DOCUMENTS_DIR / "source" / "knowledge_registry.json"

# Максимальная дистанция для поиска возможных опечаток.
# 1 означает: допускается одна правка - замена, вставка или удаление символа.
# Пример: mana -> mane = 1 замена буквы.
MAX_TYPO_DISTANCE = 1


def build_search_items(entry: RegistryEntry) -> list[tuple[str, str]]:
    """
    Превращает один элемент реестра в список вариантов для поиска.

    Поиск идет без учета регистра, поэтому canonical=mana и alias=Mana
    были бы одним и тем же поисковым вариантом. Чтобы не плодить дубли,
    уже добавленные значения запоминаются в lower-case виде.
    """
    search_items = []
    seen_values = set()

    for match_type, values in (
        ("canonical", [entry.canonical]),
        ("alias", entry.aliases),
        ("suspicious", entry.suspicious),
    ):
        for value in values:
            normalized_value = value.lower()

            if normalized_value in seen_values:
                continue

            seen_values.add(normalized_value)
            search_items.append((match_type, value))

    return search_items


def find_text_occurrences(text: str, needle: str) -> list[re.Match]:
    """
    Ищет точные вхождения текста без учета регистра.

    re.escape нужен, чтобы символы вроде точки или скобки искались как обычный
    текст, а не как специальные команды регулярного выражения.
    """
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    return list(pattern.finditer(text))


def levenshtein_distance(left: str, right: str) -> int:
    """
    Считает расстояние Левенштейна между двумя строками.

    Расстояние Левенштейна - это минимальное количество правок, чтобы превратить
    одну строку в другую. Одна правка - это вставка, удаление или замена символа.

    Примеры:
    mana -> mana = 0
    mana -> mane = 1
    mana -> manna = 1
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


def find_typo_candidates(
    text: str,
    file_path: Path,
    registry: list[RegistryEntry],
    occupied_positions: set[tuple[int, int]],
) -> list[Candidate]:
    """
    Ищет возможные опечатки по отдельным словам.

    occupied_positions содержит позиции уже найденных точных совпадений.
    Это нужно, чтобы не выводить одно и то же слово дважды: например mane
    не должен одновременно быть suspicious и possible_typo.
    """
    candidates = []
    tokens = extract_tokens(text)

    for token in tokens:
        token_range = (token.position, token.position + len(token.text))

        if token_range in occupied_positions:
            continue

        for entry in registry:
            canonical_words = extract_tokens(entry.canonical)

            # На первом шаге ищем опечатки только для однословных канонов.
            # Для длинных фраз вроде названия игры нужен отдельный алгоритм.
            if len(canonical_words) != 1:
                continue

            canonical_word = canonical_words[0].text

            if len(token.text) < 3:
                continue

            if abs(len(token.text) - len(canonical_word)) > MAX_TYPO_DISTANCE:
                continue

            distance = levenshtein_distance(token.text, canonical_word)

            if 0 < distance <= MAX_TYPO_DISTANCE:
                candidates.append(
                    Candidate(
                        key=entry.key,
                        match_type="possible_typo",
                        matched_text=token.text,
                        file_path=file_path,
                        line_number=get_line_number(text, token.position),
                        start_position=token.position,
                        end_position=token.position + len(token.text),
                        context=build_context(text, token.position, token.position + len(token.text)),
                        suggested_text=canonical_word,
                        distance=distance,
                    )
                )

    return candidates


def scan_document(document: DocumentText, registry: list[RegistryEntry]) -> list[Candidate]:
    """
    Сканирует уже прочитанный документ.

    Здесь сканеру все равно, откуда пришел текст: markdown, docx или будущий формат.
    Reader отвечает за извлечение текста, scanner отвечает за поиск проблем.
    """
    text = document.text
    candidates = []
    occupied_positions = set()

    for entry in registry:
        for match_type, search_text in build_search_items(entry):
            if not search_text:
                continue

            for match in find_text_occurrences(text, search_text):
                matched_text = match.group(0)
                actual_match_type = match_type

                # canonical ищется без учета регистра, но отличие регистра
                # тоже фиксируется как отдельная проблема.
                if match_type == "canonical" and matched_text != search_text:
                    actual_match_type = "case_mismatch"

                occupied_positions.add((match.start(), match.end()))
                candidates.append(
                    Candidate(
                        key=entry.key,
                        match_type=actual_match_type,
                        matched_text=matched_text,
                        file_path=document.file_path,
                        line_number=get_line_number(text, match.start()),
                        start_position=match.start(),
                        end_position=match.end(),
                        context=build_context(text, match.start(), match.end()),
                    )
                )

    typo_candidates = find_typo_candidates(
        text=text,
        file_path=document.file_path,
        registry=registry,
        occupied_positions=occupied_positions,
    )
    candidates.extend(typo_candidates)

    for candidate in typo_candidates:
        occupied_positions.add((candidate.start_position, candidate.end_position))

    candidates.extend(
        find_phrase_typo_candidates(
            text=text,
            file_path=document.file_path,
            registry=registry,
            occupied_positions=occupied_positions,
        )
    )

    return candidates


def scan_file(file_path: Path, registry: list[RegistryEntry]) -> list[Candidate]:
    """
    Совместимость со старым API: сканирует один markdown-файл.

    Основная новая точка входа - scan_document().
    """
    return scan_document(read_markdown_document(file_path), registry)


def get_document_paths() -> list[Path]:
    """
    Возвращает рабочие документы поддерживаемых форматов.

    Папка source пропускается, потому что там лежит центр знаний и пояснения
    к нему. Кандидатов ищем только в рабочих документах команды.
    """
    document_paths = []

    for file_path in sorted(DOCUMENTS_DIR.rglob("*")):
        if not file_path.is_file():
            continue

        if SOURCE_DIR in file_path.parents:
            continue

        if file_path.suffix.lower() not in {".md", ".docx"}:
            continue

        if file_path.name.startswith("~$"):
            continue

        document_paths.append(file_path)

    return document_paths


def get_markdown_document_paths() -> list[Path]:
    """
    Старое имя функции оставлено для совместимости.

    Теперь возвращаются не только markdown, а все поддерживаемые документы.
    """
    return get_document_paths()


def read_document(file_path: Path) -> DocumentText:
    """
    Выбирает reader по расширению файла.
    """
    suffix = file_path.suffix.lower()

    if suffix == ".md":
        return read_markdown_document(file_path)

    if suffix == ".docx":
        return read_docx_document(file_path)

    raise ValueError(f"Неподдерживаемый формат документа: {file_path}")


def scan_documents(registry: list[RegistryEntry]) -> ScanResult:
    candidates = []
    document_paths = get_document_paths()

    for file_path in document_paths:
        document = read_document(file_path)
        candidates.extend(scan_document(document, registry))

    return ScanResult(
        checked_documents_count=len(document_paths),
        candidates=candidates,
    )


def run_scan(*, detailed_report: bool = False) -> None:
    registry = load_registry(REGISTRY_PATH)
    scan_result = scan_documents(registry)
    print_report(scan_result, registry, DOCUMENTS_DIR, detailed=detailed_report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Проверка markdown/docx-документов по реестру знаний."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="показать подробный отчет со всеми найденными совпадениями",
    )
    return parser


def main(detailed_report: bool | None = None) -> None:
    if detailed_report is None:
        args = build_parser().parse_args()
        detailed_report = args.debug

    run_scan(detailed_report=detailed_report)


if __name__ == "__main__":
    main()
