import time
from urllib.parse import quote
import gradio as gr
from agent.agent import run_agent_turn
from agent.config import COMPLETED_DIR


def _build_pdf_iframe(pdf_path: str | None) -> str:
    if not pdf_path:
        return "<div style='padding:24px;color:#666;text-align:center;'>Working PDF preview will appear here.</div>"
    encoded_path = quote(str(pdf_path))
    cache_bust = int(time.time() * 1000)
    return (
        f'<iframe src="/gradio_api/file={encoded_path}?t={cache_bust}" '
        f'width="100%" height="700px" style="border:1px solid #ccc; border-radius:8px;"></iframe>'
    )


def reset_session():
    return [], [], None, None, _build_pdf_iframe(None)


with gr.Blocks(title="Local PDF Form Agent") as demo:
    with gr.Row():
        gr.Markdown("## Local PDF Form-Filling Agent")
        reset_btn = gr.Button("Start New Form / Reset", size="sm", scale=0)

    ollama_state = gr.State([])
    working_pdf_state = gr.State(None)

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(height=620)
            chat_input = gr.MultimodalTextbox(
                file_count="multiple",
                file_types=[
                    ".pdf",
                    ".docx",
                    ".xlsx",
                    ".xlsm",
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                ],
                placeholder="Drop files or type updates to add to the working form...",
            )

        with gr.Column(scale=2):
            pdf_download = gr.File(label="Download Working PDF", interactive=False)
            pdf_preview = gr.HTML(value=_build_pdf_iframe(None))

    def respond(
        message: dict, history: list, ollama_messages: list, working_pdf: str | None
    ):
        user_text = message.get("text", "")
        file_paths = message.get("files", [])

        user_display = user_text
        if file_paths:
            names = ", ".join(p.split("/")[-1].split("\\")[-1] for p in file_paths)
            user_display = f"{user_text}\n*(Attached: {names})*".strip()
        history = history + [{"role": "user", "content": user_display}]

        try:
            reply_text, updated_state, updated_pdf = run_agent_turn(
                user_text=user_text,
                file_paths=file_paths,
                ollama_messages=ollama_messages,
                working_pdf_path=working_pdf,
            )
        except Exception as exc:
            updated_state = {}
            history = history + [{"role": "assistant", "content": f"Error: {exc}"}]
            return history, updated_state, working_pdf, gr.update(), gr.update(), None

        history = history + [{"role": "assistant", "content": reply_text}]

        if updated_pdf:
            return (
                history,
                updated_state,
                updated_pdf,
                updated_pdf,
                _build_pdf_iframe(updated_pdf),
                None,
            )

        return history, updated_state, working_pdf, gr.update(), gr.update(), None

    chat_input.submit(
        fn=respond,
        inputs=[chat_input, chatbot, ollama_state, working_pdf_state],
        outputs=[
            chatbot,
            ollama_state,
            working_pdf_state,
            pdf_download,
            pdf_preview,
            chat_input,
        ],
    )

    reset_btn.click(
        fn=reset_session,
        outputs=[chatbot, ollama_state, working_pdf_state, pdf_download, pdf_preview],
    )

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        allowed_paths=[str(COMPLETED_DIR)],
    )
