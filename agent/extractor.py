import base64
import zipfile
from pathlib import Path
from typing import Tuple, List

import fitz  # PyMuPDF
import docx
import openpyxl

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _bytes_to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def extract_from_pdf(path: Path, max_pages: int = 8) -> Tuple[str, List[str]]:
    """Extracts text and renders pages to PNG base64 so embedded images/scans are read."""
    doc = fitz.open(path)
    text_chunks = [f"### Attachment: {path.name} (PDF, {len(doc)} pages)"]
    images_b64: List[str] = []

    for i, page in enumerate(doc):
        page_text = page.get_text("text").strip()
        if page_text:
            text_chunks.append(f"--- Page {i + 1} Text ---\n{page_text}")

        # Render page to PNG (150 DPI balances readability and token/VRAM speed)
        if i < max_pages:
            pix = page.get_pixmap(dpi=150)
            images_b64.append(_bytes_to_b64(pix.tobytes("png")))

    doc.close()
    return "\n\n".join(text_chunks), images_b64


def extract_from_docx(path: Path) -> Tuple[str, List[str]]:
    """Extracts paragraphs, tables, and all embedded images inside word/media/."""
    document = docx.Document(path)
    text_chunks = [f"### Attachment: {path.name} (Word Document)"]

    for p in document.paragraphs:
        if p.text.strip():
            text_chunks.append(p.text.strip())

    for idx, table in enumerate(document.tables):
        rows = []
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            rows.append("| " + " | ".join(cells) + " |")
        if rows:
            text_chunks.append(f"--- Table {idx + 1} ---\n" + "\n".join(rows))

    # Extract embedded images from the .docx zip archive
    images_b64: List[str] = []
    with zipfile.ZipFile(path, "r") as zf:
        for member in zf.namelist():
            if (
                member.startswith("word/media/")
                and Path(member).suffix.lower() in IMAGE_EXTS
            ):
                img_bytes = zf.read(member)
                images_b64.append(_bytes_to_b64(img_bytes))
                text_chunks.append(f"[Embedded image extracted: {Path(member).name}]")

    return "\n\n".join(text_chunks), images_b64


def extract_from_xlsx(path: Path) -> Tuple[str, List[str]]:
    """Extracts all sheets from an Excel workbook as Markdown tables."""
    wb = openpyxl.load_workbook(path, data_only=True)
    text_chunks = [f"### Attachment: {path.name} (Excel Workbook)"]

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        rows = []
        for row in sheet.iter_rows(values_only=True):
            if any(cell is not None for cell in row):
                cells = [str(cell).strip() if cell is not None else "" for cell in row]
                rows.append("| " + " | ".join(cells) + " |")
        if rows:
            text_chunks.append(f"--- Sheet: {sheet_name} ---\n" + "\n".join(rows))

    return "\n\n".join(text_chunks), []


def process_attachments(file_paths: List[str]) -> Tuple[str, List[str]]:
    """Processes a list of uploaded file paths into combined text and base64 images."""
    all_text: List[str] = []
    all_images: List[str] = []

    for raw_path in file_paths:
        path = Path(raw_path)
        if not path.exists():
            continue

        ext = path.suffix.lower()
        if ext == ".pdf":
            txt, imgs = extract_from_pdf(path)
        elif ext == ".docx":
            txt, imgs = extract_from_docx(path)
        elif ext in {".xlsx", ".xlsm"}:
            txt, imgs = extract_from_xlsx(path)
        elif ext in IMAGE_EXTS:
            txt = f"### Attachment: {path.name} (Image)"
            imgs = [_bytes_to_b64(path.read_bytes())]
        else:
            # Fallback for plain text / CSV / Markdown
            txt = f"### Attachment: {path.name}\n" + path.read_text(errors="ignore")
            imgs = []

        if txt:
            all_text.append(txt)
        all_images.extend(imgs)

    return "\n\n".join(all_text), all_images
