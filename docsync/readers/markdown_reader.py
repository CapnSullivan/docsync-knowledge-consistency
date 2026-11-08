"""
markdown_reader.py

Читает markdown-файл как обычный UTF-8 текст.

Это самый простой reader: markdown уже является текстовым форматом, поэтому здесь
нет извлечения из контейнера, XML или таблиц. Модуль существует ради общей схемы:
любой формат документа должен превращаться в DocumentText.
"""

from pathlib import Path

from docsync.models import DocumentText


def read_markdown_document(file_path: Path) -> DocumentText:
    """
    Возвращает markdown-документ в виде DocumentText.
    """
    return DocumentText(
        file_path=file_path,
        text=file_path.read_text(encoding="utf-8"),
        source_type="markdown",
    )
