from __future__ import annotations

import csv
import io
import os
import uuid
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
BASE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xlsm", ".pdf", ".txt"}
MAX_FILE_BYTES = 15 * 1024 * 1024


def save_upload(filename: str, content: bytes) -> dict[str, object]:
    original_name = Path(filename or "uploaded_file").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{extension or 'unknown'}'. Allowed: CSV, XLSX, XLSM, PDF, TXT.")
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("File is too large. Maximum supported upload size is 15 MB.")

    file_id = uuid.uuid4().hex
    stored_name = f"{file_id}{extension}"
    destination = BASE_DIR / stored_name
    destination.write_bytes(content)
    return {
        "file_id": file_id,
        "filename": original_name,
        "extension": extension,
        "size_bytes": len(content),
        "stored_path": str(destination),
    }


def _read_csv(path: Path) -> str:
    rows: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        for index, row in enumerate(reader):
            rows.append(" | ".join(row))
            if index >= 199:
                rows.append("[truncated after 200 rows]")
                break
    return "\n".join(rows)


def _read_excel(path: Path) -> str:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sections: list[str] = []
    try:
        for sheet in workbook.worksheets:
            sections.append(f"[SHEET: {sheet.title}]")
            for index, row in enumerate(sheet.iter_rows(values_only=True)):
                values = ["" if value is None else str(value) for value in row]
                sections.append(" | ".join(values))
                if index >= 199:
                    sections.append("[truncated after 200 rows]")
                    break
            if len(sections) > 1000:
                sections.append("[truncated after workbook size limit]")
                break
    finally:
        workbook.close()
    return "\n".join(sections)


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    sections: list[str] = []
    for index, page in enumerate(reader.pages[:30]):
        sections.append(f"[PAGE {index + 1}]\n{page.extract_text() or ''}")
    if len(reader.pages) > 30:
        sections.append("[truncated after 30 pages]")
    return "\n".join(sections)


def read_file(file_id: str) -> dict[str, object]:
    matches = list(BASE_DIR.glob(f"{file_id}.*"))
    if not matches:
        raise FileNotFoundError(f"Uploaded file '{file_id}' was not found.")
    path = matches[0]
    extension = path.suffix.lower()

    if extension == ".csv":
        text = _read_csv(path)
    elif extension in {".xlsx", ".xlsm"}:
        text = _read_excel(path)
    elif extension == ".pdf":
        text = _read_pdf(path)
    elif extension == ".txt":
        text = path.read_text(encoding="utf-8-sig")[:1_000_000]
    else:
        raise ValueError(f"Unsupported stored file type '{extension}'.")

    return {
        "file_id": file_id,
        "filename": path.name,
        "extension": extension,
        "content": text,
        "characters": len(text),
    }
