import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import fitz  # PyMuPDF
from agent.config import TEMPLATES_DIR, COMPLETED_DIR


def _load_sidecar_schema(template_path: Path) -> Dict[str, Dict[str, Any]]:
    json_path = template_path.with_suffix(".json")
    if not json_path.exists():
        return {}
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return (
            {str(k): v for k, v in data.items() if isinstance(v, dict)}
            if isinstance(data, dict)
            else {}
        )
    except Exception:
        return {}


def list_available_forms() -> str:
    """List all prepared PDF form templates available in the templates folder along with any matching sidecar JSON schema."""
    forms = sorted(TEMPLATES_DIR.glob("*.pdf"))
    if not forms:
        return json.dumps(
            {"status": "empty", "message": "No PDF forms found in templates/"}
        )

    result = []
    for pdf_path in forms:
        doc = fitz.open(pdf_path)
        entry = {
            "form_filename": pdf_path.name,
            "title": doc.metadata.get("title") or pdf_path.stem,
            "description": doc.metadata.get("subject") or "",
            "has_schema_json": False,
        }
        doc.close()

        json_path = pdf_path.with_suffix(".json")
        if json_path.exists():
            entry["has_schema_json"] = True
            entry["schema_filename"] = json_path.name
            try:
                sidecar_data = json.loads(json_path.read_text(encoding="utf-8"))
                # Override title/description if provided in the JSON, and attach field details
                if isinstance(sidecar_data, dict):
                    entry["title"] = sidecar_data.get("title") or entry["title"]
                    entry["description"] = (
                        sidecar_data.get("description") or entry["description"]
                    )
                    entry["field_details"] = sidecar_data.get("fields", sidecar_data)
                else:
                    entry["field_details"] = sidecar_data
            except Exception as exc:
                entry["schema_error"] = f"Failed to parse {json_path.name}: {exc}"

        result.append(entry)

    return json.dumps(result, indent=2)


def inspect_form_fields(
    form_filename: str, working_pdf_path: Optional[str] = None
) -> str:
    """Inspect all fillable AcroForm widgets by sequential index, enriched with sidecar JSON meanings."""
    clean_name = Path(form_filename).name
    template_path = TEMPLATES_DIR / clean_name
    pdf_path = (
        Path(working_pdf_path)
        if (working_pdf_path and Path(working_pdf_path).exists())
        else template_path
    )

    if not pdf_path.exists():
        return json.dumps({"error": f"Form '{form_filename}' not found."})

    schema_by_idx = _load_sidecar_schema(template_path)
    doc = fitz.open(pdf_path)
    fields = []
    widget_idx = 0

    for page_num, page in enumerate(doc, start=1):
        for widget in page.widgets():
            idx_str = str(widget_idx)
            meta = schema_by_idx.get(idx_str, {})
            options = meta.get("options")

            # Reverse-map current PDF value back to friendly option key if options exist
            current_val = widget.field_value or ""
            if isinstance(options, dict):
                current_val = next(
                    (k for k, v in options.items() if v == current_val), current_val
                )

            field_info: Dict[str, Any] = {
                "field_index": idx_str,
                "ori_name": widget.field_name or "",
                "field_type": widget.field_type_string,
                "meaning": meta.get("meaning") or widget.field_label or "",
                "current_value": current_val,
                "page": page_num,
            }

            if widget.field_type_string in {"CheckBox", "RadioButton"}:
                field_info["on_state"] = widget.on_state()
            elif widget.field_type_string in {"ComboBox", "ListBox"}:
                if isinstance(options, dict):
                    field_info["choice_values"] = list(options.keys())
                elif widget.choice_values:
                    field_info["choice_values"] = list(widget.choice_values)

            fields.append(field_info)
            widget_idx += 1

    doc.close()
    return json.dumps(
        {
            "form_filename": clean_name,
            "active_file": str(pdf_path),
            "fields": fields,
        },
        indent=2,
    )


def fill_pdf_form(
    form_filename: str,
    field_values: Dict[str, Any],
    working_pdf_path: Optional[str] = None,
) -> str:
    """Fill or update widgets in the working PDF using field_index keys."""
    clean_name = Path(form_filename).name
    template_path = TEMPLATES_DIR / clean_name

    if working_pdf_path and Path(working_pdf_path).exists():
        source_path = out_path = Path(working_pdf_path)
    else:
        source_path = template_path
        if not source_path.exists():
            return json.dumps({"error": f"Form '{form_filename}' not found."})
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = COMPLETED_DIR / f"{source_path.stem}_working_{timestamp}.pdf"

    schema_by_idx = _load_sidecar_schema(template_path)
    normalized_values = {str(k): v for k, v in field_values.items()}

    doc = fitz.open(source_path)
    updated = 0
    widget_idx = 0

    for page in doc:
        for widget in page.widgets():
            idx_str = str(widget_idx)
            meta = schema_by_idx.get(idx_str, {})
            widget_idx += 1

            if idx_str in normalized_values:
                val = normalized_values[idx_str]
            elif widget.field_name and widget.field_name in normalized_values:
                val = normalized_values[widget.field_name]
            else:
                continue

            options = meta.get("options")
            if isinstance(options, dict) and str(val) in options:
                val = options[str(val)]

            if widget.field_type_string in {"CheckBox", "RadioButton"}:
                widget.field_value = (
                    (widget.on_state() if val else "Off")
                    if isinstance(val, bool)
                    else str(val)
                )
            else:
                widget.field_value = "" if val is None else str(val)

            widget.update()
            updated += 1

    if out_path == source_path:
        temp_path = out_path.with_suffix(".tmp.pdf")
        doc.save(temp_path, deflate=True)
        doc.close()
        temp_path.replace(out_path)
    else:
        doc.save(out_path, deflate=True)
        doc.close()

    return json.dumps(
        {
            "status": "success",
            "fields_updated": updated,
            "output_path": str(out_path),
        }
    )
