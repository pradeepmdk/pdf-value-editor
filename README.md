# Local PDF value editor

Python serves both the website and the PDF editing API. No frontend build tools are needed. AI dependency analysis requires OpenRouter access.

AI analysis uses **OpenRouter GPT-4.1 (`openai/gpt-4.1`)** through the chat completions API with structured formula output. Put `OPEN_ROUTER_KEY=your-key` (or `OPENROUTER_API_KEY`) in this folder's `.env` and restart. Keys remain server-side. The active backend no longer uses Jev or exposes its routes. Existing Jev modules and tests are retained as legacy code only. Select one or several independent edits, click **Analyze affected values with GPT**, inspect affected values and the optional **Calculation details**, check the review box, then click **Preview recalculated changes** and download. One GPT request processes the batch. Requests use API credits; there is a 350 KB context budget, with no silent truncation. The old Jev 150-amount limit does not apply to this workflow.

The current UI runs automatically: **upload → GPT document analysis → select and enter changes → Recalculate & create PDF → preview and download**. Upload starts Python text extraction or OCR on all pages, then GPT interprets the BWA/SuSa/KER structure and identifies independent editable inputs. The Analyze button is hidden; format and rotation are optional settings, and failed analysis exposes a Retry button. Changing settings reanalyzes the file. Upload interpretation and change-dependent formula discovery are separate paid GPT requests. No original file is overwritten.

After you enter or queue changes, **Recalculate & create PDF** asks GPT for dependencies, then Python verifies and calculates them and creates the modified PDF with highlighted previews and download links. No separate review checkbox or accept/verify/create buttons are required. Inspect the resulting PDF before downloading. Unresolved relationships and failed verification still block PDF creation.

GPT identifies additive accounting relationships using the uploaded labels, columns, positions and original figures. Python validates original totals, cycles, input IDs and complete coverage for the recognized BWA, then computes changes with Decimal. GPT never supplies authoritative monetary results. Revenue does not automatically scale payroll or other independent costs: edit those inputs separately when required. Unknown tax rates, percentages, account allocations and ambiguous dependencies remain unresolved and block the simplified preview action. Different companies or periods must not be synchronized by matching numbers.

Native finance exports preserve supported original fonts and sizes. Scanned documents can be analyzed with OCR, but exact-font finance export still rejects changed scans; GPT does not recover the original fonts. Universal BWA/SuSa/KER recognition and synchronization are not guaranteed.

SuSa rules distinguish opening balances, monthly movements, year-to-date debit/credit and closing balances. Year-to-date and monthly movements must not be added together when the year-to-date already includes the month. S/H amounts are non-negative magnitudes; formulas encode their direction. The calculator rejects changes to S/H suffixes and balances that cross direction rather than emitting an incorrect negative amount with the old suffix. Counterpart postings and account allocations cannot be invented from a turnover edit. Baseline arithmetic alone does not prove complete accounting correctness for an unfamiliar SuSa.

Text PDFs, scanned PDFs and images share the same controls. Read [GENERAL_FINANCE.md](GENERAL_FINANCE.md) for dependency and image-export limitations. Source discrepancies block supported statement recalculation; incomplete reviewed dependency coverage blocks its export.

For LAN or domain access, see [NETWORK.md](NETWORK.md). Both launchers accept `--host`, `--port`, and repeatable `--allowed-origin` arguments. Localhost remains the default.

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

To identify downstream changes with AI, use **Identify affected fields** in the reviewed-rule workflow after entering a replacement amount. AI selects from baseline-verified dependency candidates; Python calculates and previews affected amounts. Accept the reviewed formula set, then verify changes before export. Unresolved or unsupported dependencies require manual rules; see [GENERAL_FINANCE.md](GENERAL_FINANCE.md) for candidate discovery limits. Tests: `..\.venv\Scripts\python.exe -m unittest test_finance_workflow -v`.

## Select text directly from a preview

In either editor, drag a rectangle around a complete value or text in the original preview. In text mode, the current text is filled automatically and **One occurrence** is selected. If the area contains multiple text spans, choose one from **Text in selected area**. In OCR mode, only the selected crop is read, and detected text is shown with its page number. Choose the region, enter replacement text, confirm it, and create the edited PDF. Give scanned text some surrounding space when drawing a selection.

OCR's **Find across whole PDF** searches every page for entered text and lists all confident matches with page numbers. Choosing a match automatically previews that page and highlights that region. Unsupported pages are reported. Full-document searches may take several minutes. The preview page number controls manual viewing, not search scope.

Edited previews cannot be used for area selection because edits start from the uploaded original. Click **Show original to select another area** to return to the original preview. A new edit creates another copy from the original; it does not accumulate previous edits.

### Supported text PDFs

Both editors accept numbers, letters, and mixed single-line text. Direct text mode changes exact complete literal text strings in supported standard fonts. It retains PDF drawing commands, fonts, and text starting positions. Longer replacements use a reduced font size to fit the original width; shorter text starts at the original position. Only the chosen text changes; calculations and totals are not updated.

Direct text mode does not support scans, custom/encoded fonts, text split across operators, or password-protected PDFs. Western European characters supported by the font encoding are accepted; arbitrary Unicode scripts require additional font support. Replacements too long to remain legible are rejected. Some unrelated PDFs may have no editable match even when the text is visible. Review edited documents before use. The source file is never overwritten.

## Scanned PDFs and OCR

Examples: `373,00S` → `473,00S`, `373,00S` → `Invoice 1`, or `AB Service GmbH` → `AB Service Ltd`. Enter a complete OCR text region exactly, including case and punctuation. When both inputs are numbers without suffixes, an existing S/H marker is retained. Otherwise the entered replacement text replaces the entire selected region, including any suffix.

All scan pages load automatically after upload in one scrollable preview. Each page has a page number and supports drag selection when editable. Changing OCR rotation reloads all previews. Selecting a search result highlights and scrolls to its page. Unsupported pages still have a preview but cannot be selected for OCR editing. Gray example text in the input is a placeholder, not an entered value.

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

Identify affected fields calls the configured AI for dependency review. Amounts come from the uploaded document. Recognized BWA layouts offer source-validated predefined formulas; other layouts use bounded candidate discovery. Run the backend with outbound HTTPS access to openrouter.ai; restricted sandbox launches can block sockets (Windows error 10013). Normal start.bat/start.sh launches do not use the agent sandbox. No rules or PDF edits are applied by a failed AI request.

## Linked reports and multiple edits

The current finance page shows two previews: the original at the selected amount's page and the recalculated result. Calculation tables stay hidden. The amount selector shows a loading indicator during intake and analysis.

Proportional planning simulation is enabled by default in the finance UI and can be unchecked for ordinary recorded-value corrections. It supports verified annual DATEV BWA 01 PDFs. One monthly sales or operating-expense edit supplies a percentage factor from the original value. That factor scales the same month's sales and all eleven operating-expense categories, rounded to cents with Decimal ROUND_HALF_UP. Other months and other independent inputs stay unchanged; standard BWA formulas recalculate subtotals, profit, and annual sums. Zero original amounts cannot drive a ratio; zero expenses remain zero. Conflicting ratios in one month's pending edits are rejected. Simulation planning/export uses deterministic verified formulas without a dependency-model call. Analysis still uses the existing AI intake. Every simulation export carries a visible SIMULATION label and metadata; these scenarios are not actual bookkeeping or tax filings. Regression checks: `..\.venv\Scripts\python.exe -m unittest test_proportional_finance test_finance_workflow test_pdf_editor -v`.

See [LINKED_REPORTS.md](LINKED_REPORTS.md). The same `/finance` URL now supports a pending list of simultaneous input changes and reviewed cross-document rules with ZIP/individual exports. Finance export requires exact native fonts/sizes; changed scans and unsupported encodings are blocked instead of rasterized. Older image-export descriptions below apply to the legacy general APIs, not the current finance export.

Modified finance PDFs now show original/modified preview copies with orange outlines for input edits and blue outlines for recalculated fields. Select a changed page to compare all affected pages. Downloaded PDFs remain unmarked; highlights are preview annotations only.

The modified preview displays change outlines locally and through the tunnel. **Download highlighted PDF** saves the marked copy; **Download clean PDF** saves the source-styled copy. Replacement inputs automatically format on blur/submit for the selected locale (e.g. `62315.78` to `62.315,78` in German mode); ambiguous separators and excessive precision are rejected rather than rounded. This explicitly authorized input formatting does not normalize original PDF content. Dependency verification remains disabled until reviewed suggestions are accepted.
