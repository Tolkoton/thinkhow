"""Spike of task 311: can pypdf read a PDF Chromium printed (Cyrillic), the stdlib read a DOCX, and how do
an image-only PDF, a broken PDF and an encrypted PDF fail? Run: uv run --with pypdf python spike.py <dir>."""
import io, sys, zipfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
import pypdf
from xml.etree import ElementTree

out = Path(sys.argv[1])
HTML = """<html><body><h1>Олена Коваль</h1><p>Продакт-менеджерка, 7 років у fintech.</p>
<ul><li>2019–2024 — Monobank: запустила кешбек-сервіс, 1,2 млн користувачів</li><li>SQL, Amplitude, A/B-тести</li></ul>
<p>English: Product manager, Kyiv.</p></body></html>"""
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    page.set_content(HTML)
    pdf = page.pdf()
    page.set_content("<html><body><img src='data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"200\" height=\"50\"><rect width=\"200\" height=\"50\" fill=\"black\"/></svg>'></body></html>")
    image_pdf = page.pdf()
    b.close()
(out / "resume.pdf").write_bytes(pdf)

def pdf_text(data: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

t = time.monotonic(); text = pdf_text(pdf)
print("PDF text (%.2fs):" % (time.monotonic() - t), repr(text))
print("image-only PDF text:", repr(pdf_text(image_pdf).strip()))
for name, data in [("broken", b"%PDF-1.7 garbage"), ("not pdf", b"hello")]:
    try:
        print(name, repr(pdf_text(data)))
    except Exception as e:
        print(name, "->", type(e).__module__, type(e).__name__, e)
w = pypdf.PdfWriter(); w.append(pypdf.PdfReader(io.BytesIO(pdf))); w.encrypt("secret"); buf = io.BytesIO(); w.write(buf)
try:
    r = pypdf.PdfReader(io.BytesIO(buf.getvalue())); print("encrypted is_encrypted", r.is_encrypted); print(repr(r.pages[0].extract_text()))
except Exception as e:
    print("encrypted ->", type(e).__module__, type(e).__name__, e)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
doc = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>Олена Коваль</w:t></w:r></w:p><w:p><w:r><w:t xml:space="preserve">Досвід: </w:t></w:r><w:r><w:t>Monobank</w:t></w:r></w:p></w:body></w:document>'
docx_buf = io.BytesIO()
with zipfile.ZipFile(docx_buf, "w") as z:
    z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    z.writestr("word/document.xml", doc)
(out / "resume.docx").write_bytes(docx_buf.getvalue())
with zipfile.ZipFile(io.BytesIO(docx_buf.getvalue())) as z:
    root = ElementTree.fromstring(z.read("word/document.xml"))
paras = ["".join(t.text or "" for t in p.iter(f"{{{W}}}t")) for p in root.iter(f"{{{W}}}p")]
print("DOCX paragraphs:", paras)
print("pypdf", pypdf.__version__)
(out / "scan.pdf").write_bytes(image_pdf)
(out / "encrypted.pdf").write_bytes(buf.getvalue())
print("wrote resume.pdf scan.pdf encrypted.pdf resume.docx")
