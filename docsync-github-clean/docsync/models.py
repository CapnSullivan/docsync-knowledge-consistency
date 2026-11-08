"""
models.py

Техническое назначение:
    Общие структуры данных для ядра docsync.

Зачем нужен модуль:
    Несколько частей системы работают с одними и теми же понятиями:
    прочитанный документ, найденный кандидат, токен текста, результат сканирования.
    Эти структуры не должны жить внутри одного запускаемого скрипта, иначе другие
    модули не смогут нормально использовать их повторно.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocumentText:
    """
    Текст, извлеченный из документа любого поддерживаемого формата.

    file_path:
        Исходный файл на диске.

    text:
        Обычный текст, который можно передать сканеру. Сканер не должен знать,
        был ли источник markdown-файлом или Word-документом.

    source_type:
        Тип источника: например markdown или docx. Это нужно для отчетов и для
        будущих ограничений: исправлять по позициям безопасно markdown, но не docx.
    """
    file_path: Path
    text: str
    source_type: str


@dataclass
class Candidate:
    """
    Одно найденное место в рабочем документе.

    Важно: это не просто "термин найден где-то в документе".
    Candidate хранит конкретное место: файл, строку, позицию начала и позицию конца.
    Эти позиции нужны для безопасного применения исправлений.
    """
    key: str
    match_type: str
    matched_text: str
    file_path: Path
    line_number: int
    start_position: int
    end_position: int
    context: str
    suggested_text: str | None = None
    distance: int | None = None


@dataclass
class Token:
    """
    Одно слово из текста и позиция его начала в исходной строке документа.
    """
    text: str
    position: int


@dataclass
class ScanResult:
    """
    Итог сканирования набора документов.
    """
    checked_documents_count: int
    candidates: list[Candidate]
