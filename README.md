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
..\.venv\Scripts\python.exe -m unittest test_scan_editor -v
```

The tests use `BWA-ganzjaehrig-2025.pdf` in the parent folder. For a fresh environment, install NumPy to run the tests: `python -m pip install numpy`.

## Supported PDFs

Both editors accept numbers, letters, and mixed single-line text. Direct text mode changes exact complete literal text strings in supported standard fonts. It retains PDF drawing commands, fonts, and text starting positions. Longer replacements use a reduced font size to fit the original width; shorter text starts at the original position. Only the chosen text changes; calculations and totals are not updated.

Direct text mode does not support scans, custom/encoded fonts, text split across operators, or password-protected PDFs. Western European characters supported by the font encoding are accepted; arbitrary Unicode scripts require additional font support. Replacements too long to remain legible are rejected. Some unrelated PDFs may have no editable match even when the text is visible. Review edited documents before use. The source file is never overwritten.

## Scanned PDFs and OCR

Examples: `373,00S` → `473,00S`, `373,00S` → `Invoice 1`, or `AB Service GmbH` → `AB Service Ltd`. Enter a complete OCR text region exactly, including case and punctuation. When both inputs are numbers without suffixes, an existing S/H marker is retained. Otherwise the entered replacement text replaces the entire selected region, including any suffix.

The scan preview loads automatically after upload, before entering any values or running OCR. Changing the page number or OCR rotation updates the preview. Type the current value shown in the preview; gray example text in the input is a placeholder, not an entered value.

Install/update all dependencies first:

```powershell
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Restart the app and open http://127.0.0.1:8000/scan (or click **OCR editor**). Upload the scan, choose a page, and enter the exact current and replacement values. Click **Find value with OCR**, inspect the numbered red regions, select one match, confirm it, and create the result. Review the edited preview and download. If the source image is sideways, select an OCR rotation and find again. The SuSa sample has an upright source image, so try 0 degrees first.

OCR mode supports one non-shared, unmasked image per page with no existing text. It changes only the selected image region, retains the page image placement, and preserves decoded image pixels outside that region. Other pages remain unchanged. Font shape and scan texture inside the edited region are approximate; PDF bytes and image compression may change. OCR can miss or misread text, so only confident exact matches are offered, with explicit user selection. Replacement text is fitted into the region, and excessively long text is rejected. The installed Arial or DejaVu Sans font determines available replacement characters. No totals are recalculated. Images over 25 megapixels are rejected.

OCR runs locally with RapidOCR and packaged ONNX models. It may take a minute per page. Keep uploads private by using the default localhost server. `scan_editor.py` implements OCR finding and signed candidate selection; `scan.html` provides the review interface. Candidate selections expire when the server restarts.

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
