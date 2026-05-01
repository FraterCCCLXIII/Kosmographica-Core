from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.routers.documents import _source_type_for_filename
from app.services.parsing import DocumentParser


def test_plain_text_extensions_are_supported(tmp_path: Path) -> None:
    source = tmp_path / "notes.csv"
    source.write_text("name,tradition\nPlotinus,Neoplatonism\n", encoding="utf-8")

    parsed = DocumentParser().parse(source, "csv")

    assert "Plotinus" in parsed.raw_text
    assert parsed.title == "notes"
    assert parsed.metadata["source_type"] == "csv"
    assert _source_type_for_filename("notes.csv") == "csv"
    assert _source_type_for_filename("notes.markdown") == "md"


def test_epub_parser_extracts_metadata_and_spine_text(tmp_path: Path) -> None:
    source = tmp_path / "sample.epub"
    with ZipFile(source, "w", ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", _container_xml())
        archive.writestr("OEBPS/content.opf", _package_xml())
        archive.writestr("OEBPS/chapter-1.xhtml", _chapter_html("First chapter", "Hermes teaches contemplation."))
        archive.writestr("OEBPS/chapter-2.xhtml", _chapter_html("Second chapter", "Sophia answers with silence."))

    parsed = DocumentParser().parse(source, "epub")

    assert parsed.title == "Sample EPUB"
    assert parsed.author == "Kosmographica"
    assert parsed.language == "en"
    assert "First chapter" in parsed.raw_text
    assert parsed.raw_text.index("Hermes teaches") < parsed.raw_text.index("Sophia answers")
    assert parsed.metadata["source_type"] == "epub"
    assert parsed.metadata["item_count"] == 2
    assert _source_type_for_filename("sample.epub") == "epub"


def _container_xml() -> str:
    return """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def _package_xml() -> str:
    return """<?xml version="1.0"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Sample EPUB</dc:title>
    <dc:creator>Kosmographica</dc:creator>
    <dc:language>en</dc:language>
    <dc:date>2026</dc:date>
  </metadata>
  <manifest>
    <item id="chapter-1" href="chapter-1.xhtml" media-type="application/xhtml+xml"/>
    <item id="chapter-2" href="chapter-2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chapter-1"/>
    <itemref idref="chapter-2"/>
  </spine>
</package>
"""


def _chapter_html(title: str, body: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{title}</title><style>.hidden {{ display: none; }}</style></head>
  <body><h1>{title}</h1><p>{body}</p><script>ignored()</script></body>
</html>
"""
