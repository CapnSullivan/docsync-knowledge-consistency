"""
app.py

Минимальный web UI для docsync.

Назначение:
    Дать простой экран поверх уже существующего ядра:
        - запустить проверку документов;
        - увидеть проблемы по файлам;
        - выбрать конкретные исправления checkbox-ами;
        - применить выбранные исправления;
        - увидеть результат повторной проверки.

Важно:
    Этот файл не содержит логики поиска ошибок. Он вызывает существующие функции
    из find_term_candidates.py и docsync.fixes. Web UI является оболочкой, а не
    новым ядром проекта.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_DIR / "Scripts"
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import find_term_candidates
from docsync.fixes import (
    apply_selected_fixes,
    get_expected_text,
    get_problem_candidates,
    sort_candidates_for_review,
)
from docsync.models import Candidate, ScanResult
from docsync.registry import RegistryEntry
from docsync.reports import get_match_type_label, get_script_note, relative_path


app = FastAPI(title="docsync")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@dataclass
class ProblemView:
    """
    Данные одной проблемы в виде, удобном для HTML-шаблона.
    """
    index: int
    file_path: str
    file_extension: str
    can_apply_fix: bool
    line_number: int
    key: str
    matched_text: str
    expected_text: str
    match_type_label: str
    context: str
    script_note: str | None


@dataclass
class DocumentProblemGroup:
    """
    UI group: one document card with all problems found in that document.
    """
    file_path: str
    file_extension: str
    can_apply_fix: bool
    problems: list[ProblemView]


@dataclass
class ScannedDocumentView:
    """
    One document that participates in the current scan.
    """
    file_path: str
    file_extension: str


@dataclass
class RegistryEntryView:
    """
    Данные одной записи реестра для страницы `/registry`.

    Это отдельная view-модель, а не `docsync.registry.RegistryEntry`.
    `RegistryEntry` нужен сканеру и содержит только поля, необходимые для
    поиска в документах: key, canonical, aliases, suspicious.

    Странице реестра нужны дополнительные поля для человека: type,
    description и status. Поэтому UI читает расширенный набор данных,
    но не раздувает модель сканера лишними административными полями.
    """
    key: str
    type: str
    canonical: str
    description: str
    aliases: list[str]
    suspicious: list[str]
    status: str


@dataclass
class RegistryPageState:
    """
    Полное состояние страницы обзора реестра терминов.

    PageState используется главной страницей проверки документов.
    RegistryPageState используется только страницей `/registry`, чтобы
    не смешивать отчет сканирования и административный обзор правил.
    """
    entries: list[RegistryEntryView]
    registry_path: Path


@dataclass
class PageState:
    """
    Все данные, которые нужны главной странице UI.
    """
    checked_documents_count: int
    scanned_documents: list[ScannedDocumentView]
    problem_count: int
    problem_document_count: int
    problems: list[ProblemView]
    problem_groups: list[DocumentProblemGroup]
    applied_count: int | None = None
    skipped_count: int | None = None
    skipped_messages: list[str] | None = None
    status_message: str | None = None


def load_registry() -> list[RegistryEntry]:
    """
    Загружает реестр знаний текущей песочницы.
    """
    return find_term_candidates.load_registry(find_term_candidates.REGISTRY_PATH)


def load_registry_page_state() -> RegistryPageState:
    """
    Загружает JSON-реестр для read-only страницы `/registry`.

    Здесь намеренно читается сырой JSON, а не результат `load_registry()`.
    Причина: `load_registry()` обслуживает сканер и отбрасывает поля,
    которые не участвуют в поиске ошибок. Для страницы обзора эти поля
    важны, потому что пользователь должен видеть смысл записи, ее тип и статус.

    Пока функция только читает данные. Когда появится редактирование реестра,
    рядом нужно будет добавить отдельный слой валидации формы перед записью
    обратно в JSON.
    """
    raw_items = json.loads(find_term_candidates.REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    entries = []

    for item in raw_items:
        entries.append(
            RegistryEntryView(
                key=item.get("key", ""),
                type=item.get("type", ""),
                canonical=item.get("canonical", ""),
                description=item.get("description", ""),
                aliases=item.get("aliases", []),
                suspicious=item.get("suspicious", []),
                status=item.get("status", ""),
            )
        )

    return RegistryPageState(
        entries=entries,
        registry_path=find_term_candidates.REGISTRY_PATH,
    )


def scan_problem_candidates(registry: list[RegistryEntry]) -> tuple[ScanResult, list[Candidate]]:
    """
    Запускает сканирование и возвращает только проблемы.
    """
    scan_result = find_term_candidates.scan_documents(registry)
    problem_candidates = sort_candidates_for_review(
        get_problem_candidates(scan_result.candidates)
    )
    return scan_result, problem_candidates


def build_problem_views(
    candidates: list[Candidate],
    registry_by_key: dict[str, RegistryEntry],
) -> list[ProblemView]:
    """
    Превращает Candidate в данные для HTML.

    index начинается с 1, чтобы пользователь выбирал проблемы так же, как в CLI.
    """
    problem_views = []

    for index, candidate in enumerate(candidates, start=1):
        expected_text = get_expected_text(candidate, registry_by_key)
        file_extension = candidate.file_path.suffix.lower()

        problem_views.append(
            ProblemView(
                index=index,
                file_path=relative_path(candidate.file_path, find_term_candidates.DOCUMENTS_DIR),
                file_extension=file_extension.removeprefix("."),
                can_apply_fix=file_extension == ".md",
                line_number=candidate.line_number,
                key=candidate.key,
                matched_text=candidate.matched_text,
                expected_text=expected_text,
                match_type_label=get_match_type_label(candidate.match_type),
                context=candidate.context,
                script_note=get_script_note(candidate.matched_text),
            )
        )

    return problem_views


def build_document_problem_groups(problems: list[ProblemView]) -> list[DocumentProblemGroup]:
    """
    Groups the flat scanner result by document for the web UI.

    The scanner still returns a flat Candidate list. That is convenient for
    fixes: each checkbox sends the index of one exact problem. The UI groups
    those exact problems under document cards because that is easier to review.
    """
    groups_by_file_path: dict[str, DocumentProblemGroup] = {}

    for problem in problems:
        group = groups_by_file_path.get(problem.file_path)

        if group is None:
            group = DocumentProblemGroup(
                file_path=problem.file_path,
                file_extension=problem.file_extension,
                can_apply_fix=problem.can_apply_fix,
                problems=[],
            )
            groups_by_file_path[problem.file_path] = group

        group.problems.append(problem)

    return list(groups_by_file_path.values())


def build_scanned_document_views() -> list[ScannedDocumentView]:
    """
    Builds a visible list of files that are included in the current scan.

    The list comes from find_term_candidates.get_document_paths(), so the UI
    shows the same document set that the scanner actually uses.
    """
    documents = []

    for file_path in find_term_candidates.get_document_paths():
        documents.append(
            ScannedDocumentView(
                file_path=relative_path(file_path, find_term_candidates.DOCUMENTS_DIR),
                file_extension=file_path.suffix.lower().removeprefix('.'),
            )
        )

    return documents


def build_page_state(
    *,
    applied_count: int | None = None,
    skipped_count: int | None = None,
    skipped_messages: list[str] | None = None,
    status_message: str | None = None,
) -> PageState:
    """
    Собирает актуальное состояние страницы после scan или apply.
    """
    registry = load_registry()
    registry_by_key = {entry.key: entry for entry in registry}
    scan_result, problem_candidates = scan_problem_candidates(registry)
    problem_views = build_problem_views(problem_candidates, registry_by_key)
    problem_groups = build_document_problem_groups(problem_views)
    scanned_documents = build_scanned_document_views()

    return PageState(
        checked_documents_count=scan_result.checked_documents_count,
        scanned_documents=scanned_documents,
        problem_count=len(problem_views),
        problem_document_count=len(problem_groups),
        problems=problem_views,
        problem_groups=problem_groups,
        applied_count=applied_count,
        skipped_count=skipped_count,
        skipped_messages=skipped_messages,
        status_message=status_message,
    )


def get_candidates_by_selected_indexes(selected_indexes: list[int]) -> list[Candidate]:
    """
    Повторно сканирует документы и возвращает Candidate по выбранным индексам.

    Перед применением исправлений сканирование выполняется заново. Это снижает риск
    применить устаревшие позиции, если файл изменился после открытия страницы.
    """
    registry = load_registry()
    _, problem_candidates = scan_problem_candidates(registry)
    selected_candidates = []

    for selected_index in selected_indexes:
        candidate_index = selected_index - 1

        if 0 <= candidate_index < len(problem_candidates):
            selected_candidates.append(problem_candidates[candidate_index])

    return selected_candidates


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    page_state = build_page_state()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "state": page_state,
            "documents_dir": find_term_candidates.DOCUMENTS_DIR,
        },
    )


@app.get("/registry", response_class=HTMLResponse)
def registry_page(request: Request) -> HTMLResponse:
    page_state = load_registry_page_state()
    return templates.TemplateResponse(
        request,
        "registry.html",
        {
            "state": page_state,
            "documents_dir": find_term_candidates.DOCUMENTS_DIR,
        },
    )


@app.post("/apply", response_class=HTMLResponse)
def apply_fixes(request: Request, selected_problem: list[int] = Form(default=[])) -> HTMLResponse:
    if not selected_problem:
        page_state = build_page_state(status_message="Исправления не выбраны.")
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "state": page_state,
                "documents_dir": find_term_candidates.DOCUMENTS_DIR,
            },
        )

    registry = load_registry()
    registry_by_key = {entry.key: entry for entry in registry}
    selected_candidates = get_candidates_by_selected_indexes(selected_problem)
    fix_results = apply_selected_fixes(selected_candidates, registry_by_key)

    applied_count = sum(1 for result in fix_results if result.applied)
    skipped_results = [result for result in fix_results if not result.applied]
    skipped_messages = [
        f"{relative_path(result.candidate.file_path, find_term_candidates.DOCUMENTS_DIR)}:"
        f"{result.candidate.line_number} - {result.message}"
        for result in skipped_results
    ]

    page_state = build_page_state(
        applied_count=applied_count,
        skipped_count=len(skipped_results),
        skipped_messages=skipped_messages,
        status_message="Выбранные исправления обработаны. Ниже показана повторная проверка.",
    )
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "state": page_state,
            "documents_dir": find_term_candidates.DOCUMENTS_DIR,
        },
    )

