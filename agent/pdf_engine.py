import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import fitz  # PyMuPDF
from agent.config import TEMPLATES_DIR, COMPLETED_DIR


def list_available_forms() -> str:
    """List all prepared PDF form templates available in the templates folder."""
    forms = sorted(TEMPLATES_DIR.glob("*.pdf"))
    if not forms:
        return json.dumps(
            {"status": "empty", "message": f"No PDF forms found in {TEMPLATES_DIR}"}
        )

    result = []
    for pdf_path in forms:
        doc = fitz.open(pdf_path)
        title = doc.metadata.get("title") or pdf_path.stem
        subject = doc.metadata.get("subject") or ""
        doc.close()
        result.append(
            {
                "form_filename": pdf_path.name,
                "title": title,
                "description": subject,
            }
        )
    return json.dumps(result, indent=2)


def inspect_form_fields(form_filename: str) -> str:
    """Inspect all fillable AcroForm fields and their annotations/tooltips in a PDF template.

    Args:
        form_filename: Exact filename of the PDF in the templates folder (e.g., 'application.pdf').
    """
    pdf_path = TEMPLATES_DIR / Path(form_filename).name
    if not pdf_path.exists():
        return json.dumps({"error": f"Form '{form_filename}' not found."})

    doc = fitz.open(pdf_path)
    fields = []
    seen = set()

    for page_num, page in enumerate(doc, start=1):
        for widget in page.widgets():
            name = widget.field_name
            if not name or name in seen:
                continue
            seen.add(name)

            fields.append(
                {
                    "field_name": name,
                    "field_type": widget.field_type_string,  # Text, CheckBox, RadioButton, ComboBox, etc.
                    "annotation_tooltip": widget.field_label
                    or "",  # Your PDF tooltip / alternate name
                    "current_value": widget.field_value or "",
                    "page": page_num,
                    "on_state": (
                        widget.on_state()
                        if widget.field_type_string == "CheckBox"
                        else None
                    ),
                }
            )

    doc.close()
    return json.dumps({"form_filename": pdf_path.name, "fields": fields}, indent=2)


def fill_pdf_form(form_filename: str, field_values: Dict[str, Any]) -> str:
    """Fill out a PDF form template with the provided field values and save the completed PDF.

    Args:
        form_filename: Exact filename of the PDF in the templates folder.
        field_values: Dictionary mapping exact `field_name` to the value to fill.
                      For CheckBox fields, pass True/False or the checkbox's `on_state` string.
    """
    pdf_path = TEMPLATES_DIR / Path(form_filename).name
    if not pdf_path.exists():
        return json.dumps({"error": f"Form '{form_filename}' not found."})

    doc = fitz.open(pdf_path)
    updated_count = 0

    for page in doc:
        for widget in page.widgets():
            fname = widget.field_name
            if fname not in field_values:
                continue

            val = field_values[fname]
            if widget.field_type_string == "CheckBox":
                if isinstance(val, bool):
                    widget.field_value = widget.on_state() if val else "Off"
                else:
                    widget.field_value = str(val)
            else:
                widget.field_value = "" if val is None else str(val)

            widget.update()
            updated_count += 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filename = f"{pdf_path.stem}_filled_{timestamp}.pdf"
    out_path = COMPLETED_DIR / out_filename
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()

    return json.dumps(
        {
            "status": "success",
            "fields_updated": updated_count,
            "output_path": str(out_path),
        }
    )
