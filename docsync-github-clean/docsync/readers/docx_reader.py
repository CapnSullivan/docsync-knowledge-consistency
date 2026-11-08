"""
docx_reader.py

Минимальное чтение .docx без внешних зависимостей.

.docx - это zip-архив. Основной текст документа лежит внутри файла
`word/document.xml`. Reader достает XML, собирает текстовые узлы абзацев и
возвращает обычный текст для сканера.

Ограничения первой версии:
    - только чтение .docx;
    - без исправления .docx;
    - без сохранения форматирования;
    - таблицы читаются как последовательность текстовых фрагментов, если они есть
      в основном document.xml.
"""

from pathlib import Path
import xml.etree.ElementTree as ElementTree
import zipfile

from docsync.models import DocumentText


WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DOCUMENT_XML_PATH = "word/document.xml"


def extract_paragraph_text(paragraph: ElementTree.Element) -> str:
    """
    Собирает текст одного Word-абзаца из XML-узлов w:t.
    """
    text_parts = []

    for text_node in paragraph.iter(f"{WORD_NAMESPACE}t"):
        if text_node.text:
            text_parts.append(text_node.text)

    return "".join(text_parts).strip()


def extract_docx_text(file_path: Path) -> str:
    """
    Извлекает обычный текст из .docx.
    """
    with zipfile.ZipFile(file_path) as docx_archive:
        document_xml = docx_archive.read(DOCUMENT_XML_PATH)

    root = ElementTree.fromstring(document_xml)
    paragraphs = []

    for paragraph in root.iter(f"{WORD_NAMESPACE}p"):
        paragraph_text = extract_paragraph_text(paragraph)

        if paragraph_text:
            paragraphs.append(paragraph_text)

    return "\n".join(paragraphs)


def read_docx_document(file_path: Path) -> DocumentText:
    """
    Возвращает Word .docx документ в виде DocumentText.
    """
    return DocumentText(
        file_path=file_path,
        text=extract_docx_text(file_path),
        source_type="docx",
    )
