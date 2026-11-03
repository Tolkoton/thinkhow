"""The text of a person's file: PDF, DOCX, TXT, MD (task 311). Reads bytes only; stores and logs nothing.

The format comes from the name's extension. pypdf reads a PDF; a DOCX is the paragraphs of
`word/document.xml`, read by the standard library (PR-33, PR-34).
"""

import io
import zipfile
from typing import Literal
from xml.etree import ElementTree

from pypdf import PdfReader

Reason = Literal["format", "empty", "broken", "encrypted"]
TEXT_SUFFIXES = (".txt", ".md", ".markdown")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BOMS = (("utf-8-sig", b"\xef\xbb\xbf"), ("utf-16", b"\xff\xfe"), ("utf-16", b"\xfe\xff"))


class Unreadable(Exception):
    """The file gives no text: another format, no text (a scan), bytes that do not parse, a password."""

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason)
        self.reason: Reason = reason


def file_format(name: str) -> str:
    """The extension the format is read from, lower case without the dot ("" when there is none)."""
    head, dot, suffix = name.rpartition(".")
    return suffix.lower() if dot and head else ""


def extract(name: str, data: bytes) -> str:
    """Flow: the reader of the extension → the raw text → newlines normalised, edges trimmed, never empty."""
    kind = file_format(name)
    if kind == "pdf":
        raw = _pdf(data)
    elif kind == "docx":
        raw = _docx(data)
    elif "." + kind in TEXT_SUFFIXES:
        raw = _plain(data)
    else:
        raise Unreadable("format")
    text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise Unreadable("empty")
    return text


def _pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise Unreadable("encrypted")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Unreadable:
        raise
    except Exception as exc:  # any failure of the parser is a file that does not parse
        raise Unreadable("broken") from exc


def _docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            part = archive.read("word/document.xml")
        if b"<!DOCTYPE" in part:
            raise Unreadable("broken")
        root = ElementTree.fromstring(part)
    except Unreadable:
        raise
    except Exception as exc:
        raise Unreadable("broken") from exc
    return "\n".join("".join(t.text or "" for t in p.iter(f"{W}t")) for p in root.iter(f"{W}p"))


def _plain(data: bytes) -> str:
    """UTF-16 only with its BOM; otherwise UTF-8, a UTF-8 BOM dropped."""
    encoding = next((enc for enc, bom in BOMS if data.startswith(bom)), "utf-8")
    try:
        return data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise Unreadable("broken") from exc
