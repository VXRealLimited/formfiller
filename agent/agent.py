import json
from typing import List, Dict, Any, Tuple, Optional

import ollama
from agent.config import OLLAMA_MODEL, SYSTEM_PROMPT
from agent.extractor import process_attachments
from agent.pdf_engine import list_available_forms, inspect_form_fields, fill_pdf_form

TOOLS = [list_available_forms, inspect_form_fields, fill_pdf_form]
TOOL_MAP = {fn.__name__: fn for fn in TOOLS}


def run_agent_turn(
    user_text: str,
    file_paths: List[str],
    ollama_messages: List[Dict[str, Any]],
    working_pdf_path: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
    if not ollama_messages:
        ollama_messages.append({"role": "system", "content": SYSTEM_PROMPT})

    extracted_text, images_b64 = process_attachments(file_paths)

    content = user_text.strip()
    if working_pdf_path:
        content += f"\n\n[Active Working PDF: {working_pdf_path}]"
    if extracted_text:
        content += f"\n\n--- ATTACHMENTS ---\n{extracted_text}"

    user_msg: Dict[str, Any] = {
        "role": "user",
        "content": content or "Review the attached files.",
    }
    if images_b64:
        user_msg["images"] = images_b64

    ollama_messages.append(user_msg)
    active_pdf = working_pdf_path

    while True:
        response = ollama.chat(
            model=OLLAMA_MODEL, messages=ollama_messages, tools=TOOLS
        )
        msg = response.message
        ollama_messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return msg.content or "", ollama_messages, active_pdf

        for call in msg.tool_calls:
            fn_name = call.function.name
            fn_args = dict(call.function.arguments or {})
            tool_fn = TOOL_MAP.get(fn_name)

            # Automatically bind the session's active working PDF so edits accumulate in one file
            if fn_name in {"inspect_form_fields", "fill_pdf_form"} and active_pdf:
                fn_args["working_pdf_path"] = active_pdf

            try:
                tool_result = (
                    tool_fn(**fn_args)
                    if tool_fn
                    else json.dumps({"error": f"Unknown tool: {fn_name}"})
                )
            except Exception as exc:
                tool_result = json.dumps({"error": str(exc)})

            if fn_name == "fill_pdf_form":
                parsed = json.loads(tool_result)
                if parsed.get("status") == "success":
                    active_pdf = parsed.get("output_path")

            ollama_messages.append(
                {"role": "tool", "tool_name": fn_name, "content": tool_result}
            )
