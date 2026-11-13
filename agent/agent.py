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
) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
    """
    Processes one user turn (text + attachments), executes Ollama tool calls in a loop,
    and returns (assistant_reply, updated_ollama_messages, generated_pdf_path).
    """
    if not ollama_messages:
        ollama_messages.append({"role": "system", "content": SYSTEM_PROMPT})

    extracted_text, images_b64 = process_attachments(file_paths)

    combined_content = user_text.strip()
    if extracted_text:
        combined_content += f"\n\n--- UPLOADED ATTACHMENTS ---\n{extracted_text}"

    user_msg: Dict[str, Any] = {
        "role": "user",
        "content": combined_content or "Please review the attached files.",
    }
    if images_b64:
        user_msg["images"] = images_b64

    ollama_messages.append(user_msg)
    generated_pdf: Optional[str] = None

    # Agent tool-calling loop
    while True:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=ollama_messages,
            tools=TOOLS,
        )
        msg = response.message
        ollama_messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return msg.content or "", ollama_messages, generated_pdf

        for call in msg.tool_calls:
            fn_name = call.function.name
            fn_args = call.function.arguments or {}
            tool_fn = TOOL_MAP.get(fn_name)

            if tool_fn is None:
                tool_result = json.dumps({"error": f"Unknown tool: {fn_name}"})
            else:
                try:
                    tool_result = tool_fn(**fn_args)
                except Exception as exc:
                    tool_result = json.dumps({"error": str(exc)})

            # Capture output PDF path when fill_pdf_form succeeds
            if fn_name == "fill_pdf_form":
                try:
                    parsed = json.loads(tool_result)
                    if parsed.get("status") == "success":
                        generated_pdf = parsed.get("output_path")
                except json.JSONDecodeError:
                    pass

            ollama_messages.append(
                {
                    "role": "tool",
                    "tool_name": fn_name,
                    "content": tool_result,
                }
            )
