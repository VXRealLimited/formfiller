# Local PDF Form-Filling Agent

A local, single-user AI assistant powered by **Ollama**, **Gradio**, and **PyMuPDF**. Upload source documents (`.pdf`, `.docx`, `.xlsx`, or images), and the agent reads both text and embedded images to fill out your prepared PDF form templates.

## Prerequisites

1. **Anaconda / Miniconda** installed on your machine.
2. **Ollama** installed and running locally, with a multimodal + tool-capable model downloaded:
   ```bash
   ollama pull qwen3.5
   ```

_(To use a different model, update `OLLAMA_MODEL` in `form_agent/config.py`.)_

## Installation

1. **Create and activate a Conda environment:**

```bash
conda create -n form-agent python=3.11 pip -y
conda activate form-agent

```

2. **Install Python dependencies:**

```bash
pip install -r requirements.txt

```

## How to Use

1. **Add Your PDF Templates:**

- Place your fillable AcroForm PDF forms inside the `templates/` folder.
- Make sure each field in the PDF has a descriptive **Tooltip** (`TU` / field label) so the AI understands what information belongs in each field.

2. **Start the Application:**

```bash
conda activate form-agent
python app.py

```

3. **Fill a Form:**

- Open **`http://127.0.0.1:7860`** in your browser.
- Attach your source files (PDFs, Word docs with embedded images, Excel spreadsheets, or photos) and tell the agent which form you want to fill.
- Answer any follow-up questions if required fields are missing, then download the completed PDF directly from the chat (also saved in `completed/`).
