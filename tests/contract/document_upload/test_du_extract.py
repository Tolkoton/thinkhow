"""Contract tests of document-upload: `platform.documents.extract` on real file bytes (Seam 1).

Slice tester; from the contract `.engine/slices/document-upload.md`, not the code. No mocked parser: the
spike's real PDF and DOCX files, DOCX files built by hand with zipfile, and broken bytes.
"""

import io

import pypdf
import pytest
from du_fakes import RESUME_DOCX_TEXT, RESUME_PDF_TEXT, docx, file_bytes, reason_of, zip_of


def _extract(name: str, data: bytes) -> str:
    from thinkhow.platform.documents import extract

    return extract(name, data)


def _reason(name: str, data: bytes) -> object:
    from thinkhow.platform.documents import Unreadable

    with pytest.raises(Unreadable) as caught:
        _extract(name, data)
    return reason_of(caught.value)


def test_a_chromium_printed_cyrillic_pdf_gives_its_text() -> None:
    assert _extract("resume.pdf", file_bytes("resume.pdf")) == RESUME_PDF_TEXT


def test_the_pages_of_a_pdf_are_joined_by_one_newline() -> None:
    writer = pypdf.PdfWriter()
    writer.append(pypdf.PdfReader(io.BytesIO(file_bytes("resume.pdf"))))
    writer.append(pypdf.PdfReader(io.BytesIO(file_bytes("resume.pdf"))))
    buf = io.BytesIO()
    writer.write(buf)
    assert _extract("two.pdf", buf.getvalue()) == RESUME_PDF_TEXT + "\n" + RESUME_PDF_TEXT


def test_a_docx_gives_its_paragraphs_joined_by_newlines() -> None:
    assert _extract("resume.docx", file_bytes("resume.docx")) == RESUME_DOCX_TEXT
    built = docx([["Перший абзац"], ["Другий ", "з двох частин"], ["Третій"]])
    assert _extract("built.docx", built) == "Перший абзац\nДругий з двох частин\nТретій"


def test_a_text_file_drops_a_utf8_bom_and_reads_utf16_with_a_bom() -> None:
    text = "Мої нотатки\nПро роботу"
    assert _extract("a.txt", b"\xef\xbb\xbf" + text.encode("utf-8")) == text
    assert _extract("a.md", text.encode("utf-8")) == text
    assert _extract("a.markdown", b"\xff\xfe" + text.encode("utf-16-le")) == text
    assert _extract("a.txt", b"\xfe\xff" + text.encode("utf-16-be")) == text


def test_newlines_are_normalised_and_the_edges_trimmed() -> None:
    raw = "  \n\tРядок один\r\nРядок два\rРядок три  \r\n\n"
    assert _extract("n.txt", raw.encode("utf-8")) == "Рядок один\nРядок два\nРядок три"
    docx_inside = docx([[""], ["  Абзац  "], [""]])
    assert _extract("n.docx", docx_inside) == "Абзац"


def test_the_extension_is_read_case_insensitively() -> None:
    assert _extract("RESUME.PDF", file_bytes("resume.pdf")) == RESUME_PDF_TEXT
    assert _extract("Resume.DocX", file_bytes("resume.docx")) == RESUME_DOCX_TEXT
    assert _extract("NOTES.TXT", "нотатка".encode()) == "нотатка"
    assert _extract("Notes.Md", "нотатка".encode()) == "нотатка"
    assert _extract("Notes.MARKDOWN", "нотатка".encode()) == "нотатка"


def test_another_extension_is_unreadable_format_whatever_the_bytes() -> None:
    pdf = file_bytes("resume.pdf")
    for name in ("resume.doc", "resume.rtf", "resume", "resume.pdf.exe", "resume.odt"):
        assert _reason(name, pdf) == "format", name
    assert _reason("notes.csv", b"a,b") == "format"


def test_no_text_after_trimming_is_unreadable_empty() -> None:
    assert _reason("scan.pdf", file_bytes("scan.pdf")) == "empty"
    assert _reason("blank.txt", b" \r\n\t\n ") == "empty"
    assert _reason("nothing.md", b"") == "empty"
    assert _reason("blank.docx", docx([[" "], [""]])) == "empty"


def test_bytes_the_parser_cannot_read_are_unreadable_broken() -> None:
    assert _reason("broken.pdf", b"%PDF-1.7 garbage") == "broken"
    assert _reason("hello.pdf", b"hello") == "broken"
    assert _reason("not-a-zip.docx", b"PK this is not a zip archive") == "broken"
    assert _reason("pdf-named-docx.docx", file_bytes("resume.pdf")) == "broken"
    assert _reason("docx-named-pdf.pdf", file_bytes("resume.docx")) == "broken"


def test_a_zip_without_word_document_xml_is_unreadable_broken() -> None:
    assert (
        _reason("other.docx", zip_of({"[Content_Types].xml": "<Types/>", "word/other.xml": "<x/>"}))
        == "broken"
    )


def test_a_docx_part_with_a_doctype_is_unreadable_broken() -> None:
    assert _reason("dtd.docx", docx([["Текст"]], doctype=True)) == "broken"


def test_a_text_file_not_valid_in_its_encoding_is_unreadable_broken() -> None:
    assert _reason("latin1.txt", "café".encode("latin-1")) == "broken"
    assert _reason("bad.md", b"\xc3\x28 text") == "broken"
    assert _reason("lone-surrogate.txt", b"\xff\xfe" + b"\x00\xd8") == "broken"


def test_a_pdf_that_needs_a_password_is_unreadable_encrypted() -> None:
    assert _reason("encrypted.pdf", file_bytes("encrypted.pdf")) == "encrypted"
