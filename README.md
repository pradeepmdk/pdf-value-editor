# Local PDF value editor

Python serves both the website and the PDF editing API. No frontend build tools or external services are needed.

## Run with Bash (Linux, macOS, or Git Bash on Windows)

From the project root:

```bash
bash pdf-value-editor/start.sh
```

Or, from inside the app folder:

```bash
bash start.sh
```

Open **http://127.0.0.1:8000**. The script uses an existing local or parent virtual environment, or creates one if needed. Missing dependencies are installed automatically. Python 3 must be installed; installation of packages requires internet access. Keep the terminal open and press **Ctrl+C** to stop the app.

## Run on Windows

### Easiest: launcher

Double-click `start.bat` in this folder. Then open **http://127.0.0.1:8000** in your browser.

The launcher uses an existing Python environment in this folder or its parent. If neither exists, it creates one using Python on your PATH. Missing required packages are installed automatically (internet access is needed for installation). Keep the command window open while using the website; press **Ctrl+C** to stop it.

You can also launch it from PowerShell in the project root:

```powershell
.\pdf-value-editor\start.bat
```

If the app is already running, use the existing website or stop that instance before starting another one.

### Manual commands

Run these commands inside the `pdf-value-editor` folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe pdf_editor.py
```

Open http://127.0.0.1:8000. Upload your PDF, enter `52.315,78` and `62.315,78`, choose all matches or one occurrence, create the result, review the preview, and download it. Each edit starts from the uploaded original. Stop the server with Ctrl+C.

To use the existing virtual environment in the parent folder:

```powershell
..\.venv\Scripts\python.exe pdf_editor.py
```

Run regression checks with the parent environment (which includes NumPy):

```powershell
..\.venv\Scripts\python.exe -m unittest test_pdf_editor -v
```

The tests use `BWA-ganzjaehrig-2025.pdf` in the parent folder. For a fresh environment, install NumPy to run the tests: `python -m pip install numpy`.

## Supported PDFs

This app changes exact numeric strings in standard-font literal PDF text operators. It retains the existing PDF drawing commands, fonts, and layout instead of rebuilding the page. Replacement values must have equal rendered width (normally the same digit count). Only the chosen numbers change; dependent calculations and totals are not updated.

Scans, custom/encoded fonts, text split across operators, and password-protected PDFs are unsupported. Longer or shorter numbers are rejected to prevent layout damage. Some unrelated PDFs may have no editable match even when the value is visible. Review edited documents before use. The source file is never overwritten.

Uploads and results are processed in memory with a 20 MB upload limit. The server binds to localhost for personal use. Public hosting requires a production server, authentication, request limits, and isolated PDF processing workers; this local development server is not a public deployment.

## Python API

```python
from pathlib import Path
from pdf_editor import edit_pdf

source = Path('../BWA-ganzjaehrig-2025.pdf').read_bytes()
result, count, changed_pages = edit_pdf(source, '52.315,78', '62.315,78')
Path('edited.pdf').write_bytes(result)
```

Use `occurrence=1` to edit the first occurrence only; the default `0` edits all matches. `/api/preview` and `/api/edit` accept JSON with a base64 `pdf` field. The website is in `editor.html`; backend and reusable editing function are in `pdf_editor.py`.
