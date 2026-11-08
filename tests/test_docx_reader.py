"""
test_docx_reader.py

Проверяет минимальное чтение .docx через стандартную библиотеку Python.

Тест не проверяет Microsoft Word и не проверяет форматирование. Он проверяет
только наш контракт reader-а: .docx должен превращаться в DocumentText с обычным
текстом, который дальше может использовать сканер.
"""

import tempfile
import unittest
from pathlib import Path
import sys
import zipfile
from xml.sax.saxutils import escape


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from docsync.readers.docx_reader import read_docx_document


def build_minimal_docx(file_path: Path, paragraphs: list[str]) -> None:
    """
    Создает минимальный .docx для теста reader-а.
    """
    def paragraph_xml(text: str) -> str:
        return f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>"

    document_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {paragraphs}
    <w:sectPr/>
  </w:body>
</w:document>
'''.format(paragraphs="\n    ".join(paragraph_xml(text) for text in paragraphs))

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
'''

    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
'''

    with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)


class DocxReaderTest(unittest.TestCase):
    def test_docx_reader_extracts_paragraph_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "sample.docx"
            build_minimal_docx(
                docx_path,
                [
                    "Game about might and magic",
                    "The hero uses mana.",
                ],
            )

            document = read_docx_document(docx_path)

        self.assertEqual("docx", document.source_type)
        self.assertEqual(docx_path, document.file_path)
        self.assertEqual("Game about might and magic\nThe hero uses mana.", document.text)


if __name__ == "__main__":
    unittest.main()
