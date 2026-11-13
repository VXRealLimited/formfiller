import gradio as gr
from agent.agent import run_agent_turn


def chat_handler(message: dict, history: list, ollama_state: list):
    """Gradio multimodal chat callback."""
    user_text = message.get("text", "")
    file_paths = message.get("files", [])

    reply_text, updated_state, generated_pdf = run_agent_turn(
        user_text=user_text,
        file_paths=file_paths,
        ollama_messages=ollama_state,
    )

    responses = []
    if reply_text:
        responses.append(reply_text)
    if generated_pdf:
        # Gradio renders file paths as downloadable file cards in the chat bubble
        responses.append(gr.File(value=generated_pdf))

    return responses, updated_state


with gr.Blocks(title="Local PDF Form Agent") as demo:
    gr.Markdown("## Local PDF Form-Filling Agent (Ollama Multimodal)")
    gr.Markdown(
        "Upload your source documents (`.pdf`, `.docx`, `.xlsx`, or images) and tell me which form to fill."
    )

    ollama_state = gr.State([])

    gr.ChatInterface(
        fn=chat_handler,
        multimodal=True,
        additional_inputs=[ollama_state],
        additional_outputs=[ollama_state],
        textbox=gr.MultimodalTextbox(
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
            placeholder="Describe which form to fill or drop your PDF / Word / Excel files here...",
        ),
    )


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
