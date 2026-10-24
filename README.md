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

Large uploads use a binary prepare request and a bounded, expiring in-memory document reference for subsequent finance requests. OCR/AI intake runs as a background job with short polling requests so a long scan does not hold one proxy request open. Non-JSON proxy errors now show actionable upload/timeout messages. Scanned general statements require the explicit image-based export checkbox: changed pages are raster images with approximate replacement fonts, while untouched pages are preserved. Proportional DATEV simulation is disabled for unsupported formats such as scanned SuSa. Run `..\.venv\Scripts\python.exe -m unittest test_scan_workflow -v` for scan consent, untouched-page preservation, upload expiry and analysis-job checks.

The current finance page shows two previews: the original at the selected amount's page and the recalculated result. Calculation tables stay hidden. The amount selector shows a loading indicator during intake and analysis.

Ordinary recalculation is the default. Proportional planning simulation is an optional checkbox for verified annual DATEV BWA 01 PDFs. One monthly sales or operating-expense edit supplies a percentage factor from the original value. That factor scales the same month's sales and all eleven operating-expense categories, rounded to cents with Decimal ROUND_HALF_UP. Other months and other independent inputs stay unchanged; standard BWA formulas recalculate subtotals, profit, and annual sums. Zero original amounts cannot drive a ratio; zero expenses remain zero. Conflicting ratios in one month's pending edits are rejected. Simulation planning/export uses deterministic verified formulas without a dependency-model call. Analysis still uses the existing AI intake. Every simulation export carries a visible SIMULATION label and metadata; these scenarios are not actual bookkeeping or tax filings. Regression checks: `..\.venv\Scripts\python.exe -m unittest test_proportional_finance test_finance_workflow test_pdf_editor -v`.

See [LINKED_REPORTS.md](LINKED_REPORTS.md). The same `/finance` URL now supports a pending list of simultaneous input changes and reviewed cross-document rules with ZIP/individual exports. Finance export requires exact native fonts/sizes; changed scans and unsupported encodings are blocked instead of rasterized. Older image-export descriptions below apply to the legacy general APIs, not the current finance export.

Modified finance PDFs now show original/modified preview copies with orange outlines for input edits and blue outlines for recalculated fields. Select a changed page to compare all affected pages. Downloaded PDFs remain unmarked; highlights are preview annotations only.

The modified preview displays change outlines locally and through the tunnel. **Download highlighted PDF** saves the marked copy; **Download clean PDF** saves the source-styled copy. Replacement inputs automatically format on blur/submit for the selected locale (e.g. `62315.78` to `62.315,78` in German mode); ambiguous separators and excessive precision are rejected rather than rounded. This explicitly authorized input formatting does not normalize original PDF content. Dependency verification remains disabled until reviewed suggestions are accepted.

## Additional verified layouts

`/finance` supports the supplied `10-10-docs/BWA-ganzjaehrig-2025.pdf` through the existing annual DATEV rules. It also recognizes the ten-page `10257_BWA_2024-12_261009_205509.pdf` cash-basis layout and the six-page ADDISON SuSa layout in both supplied AB Service files. Detection uses report headings, column geometry, row identities and source arithmetic, not filenames. Recognized cash-basis/ADDISON layouts use deterministic format rules without paid model calls; other general formats retain GPT review.

Cash-basis BWA checks 433 relationships: income and expense totals, result, printed percentage ratios, liquidity, repeated current-period values, absolute previous-year differences and percentage changes. Monthly input edits propagate their delta to year-to-date unless that annual input is explicitly replaced in the same batch. Prior-year values and independent payroll, VAT and tax amounts stay unchanged. Percentage calculations use Decimal and ROUND_HALF_UP; source ratios may differ by 0.01 due to rounded printed currency, while additive totals must match exactly. Undefined percentage denominators block export. Attached native DATEV SuSa pages now receive separate monthly and year-to-date checks against supported SKR04 revenue, VAT, expense and money-account movements. Unexplained differences block recalculation. Scenario calculations remain available on matching sources, but PDF export with ledger attachments is blocked because the editor cannot create synchronized accounting entries. Regenerate matching BWA and SuSa exports from the accounting system. Cross-file prior-year and capital continuity, unmapped accounts and universal VAT-rate validation remain unsupported; no fraud score is inferred. Native export edits existing WinAnsi glyph operators, including split TJ amounts, retaining fonts, sizes, right alignment and unrelated text/graphics.

ADDISON SuSa automatically reads the sideways scan upright and validates all six columns: signed opening balance, monthly debit/credit, year-to-date debit/credit and signed closing balance. It checks account balances, category subtotals, class totals and grand totals. Monthly changes propagate to year-to-date by the same delta. Enter counterpart movements explicitly in the pending batch: debit/credit totals and signed grand balances must stay balanced. Direction reversals and changed low-confidence OCR fields are blocked. German OCR punctuation/O-versus-zero corrections and suspicious numeric crop retries improve extraction; source arithmetic is still mandatory. Scan export requires the image-export checkbox, uses approximate replacement fonts, retains original image resolution and page orientation, and verifies saved decoded pixels with no changes outside selected regions. Untouched pages remain unchanged. Preview highlights account for the OCR rotation.

The supplied reviewed/recalculated SuSa copy is recognized but contains an inconsistent PKW opening balance while its closing balance/subtotals remain unchanged. Its discrepancies are shown and recalculation is blocked. Original uploads are never overwritten. Cross-report account allocation for the two new profiles remains unsupported.

Run `..\.venv\Scripts\python.exe -m unittest test_statement_profiles -v` for the supplied native and scanned sample checks; OCR tests take several minutes. Annual sample fixtures now use the `10-10-docs` path.

## Legacy profit / loss targets (UI hidden)

The target UI below is retained only in legacy files/API for compatibility. The
current page hides these controls and uses bounded expense planning instead.

In **Change an amount**, enable **Set a profit / loss target**, choose Profit or
Loss and a result period. The input selected above (or in the PDF preview) is
used automatically; there is no second input selector. If there is no eligible
selection for the result period, a verified input is selected automatically and
shown above the preview action. Changing the input dropdown is optional. Enter a positive
target magnitude, then click **Preview profit / loss changes**. Review the input
adjustments and dependent totals before choosing **Create PDF with these changes**.
Pending changes are included; the chosen adjustment input is solved to reach the
desired final result. This mode uses verified formulas and Decimal, without an AI
dependency request, and cannot be combined with proportional simulation.

For the cash-basis BWA and SuSa, a selected monthly input can also reach a
year-to-date target through the verified monthly-to-year-to-date propagation.
An explicit pending override of that year-to-date input takes precedence and
must be removed before solving the annual target through the monthly input.

Supported references: annual DATEV BWA 01 (monthly or annual result), DATEV
cash-basis BWA (month or year-to-date), and the recognized ADDISON SuSa sample
(month or year-to-date). SuSa shows a computed net credit-minus-debit result from
account classes 4–7; it does not insert a new result row. Select an explicit
opposite-column balance-sheet counterpart. Balanced totals, OCR confidence,
original S/H direction and scan-export consent remain required. Sources with
unexplained discrepancies remain blocked.

Checks: `node test_profit_loss_ui.js` and
`..\.venv\Scripts\python.exe -m unittest test_profit_loss -v`.

## Realistic AI scenario (current UI)

The prompts are plain text files in `prompts/`: `scenario_research.txt` (web search), `scenario_extract.txt` (figures with cited sources) and `scenario_drivers.txt` (driver per account). They are read on every request, so an edit applies without a restart; `{language}` becomes English or German. The JSON output schemas and all arithmetic stay in `realistic_scenario.py`.

For the DATEV BWA 01, the DATEV cash-basis BWA and the Buhl BWA, the finance
page enables **Realistic AI scenario (web research for the document year)** by
default. Enter your own change(s), then click **Preview realistic AI scenario**
(`realistic_scenario.py`, endpoints `/api/finance/scenario-start` and
`/api/finance/scenario-apply`):

1. **Web research.** GPT-4.1 with OpenRouter's web search reads the page-1 header
   and account labels, determines the year, region and industry, and looks up
   real figures for that year (inflation, wages, energy, fuel, rents, industry
   prices).
2. **Citations only.** A second, structured call extracts the figures; each must
   point at a numbered page the search actually returned (`url_citation`
   annotations). Invented links are impossible; figures without a source are
   dropped. Changes outside ±100 % are rejected.
3. **Drivers, not amounts.** A third call decides for every other editable account
   in the edited period column(s) whether it follows **sales**, one or more
   **researched figures** (averaged), or stays **unchanged**, and flags revenue
   accounts. The AI does no arithmetic.
4. **Python calculates.** Python computes the exact total-revenue change of each
   column from your edits, applies it or the researched percentages with Decimal,
   propagates month changes into year-to-date and recalculates every total with
   the verified format rules. Zero accounts stay zero.

The review lists the figures with source links, each account's driver, reason and
before/after amounts, and every changed field. The PDF is created only after you
confirm, from a signed preview. One scenario uses three OpenRouter calls (about
$0.10–0.15 with web search). SuSa is not supported because movements need balanced
counterpart bookings. Checks: `..\.venv\Scripts\python.exe -m unittest
test_realistic_scenario -v` and `node test_finance_forecast.js`.

## Bounded expense planning (legacy API, UI replaced)

The UI described below was replaced by the realistic AI scenario; the
`/api/finance/forecast-*` endpoints remain. Previously the UI hid **Set a profit / loss target** and replaces uniform scaling
with **Realistic expense planning**, enabled by default for recognized BWA/SuSa.
Choose income or an expense from the normal input dropdown. Annual DATEV income
also has an **Annual income** planning option: Python allocates the entered total
across months using the printed revenue shares, with an exact cent total.

After entering changes, **Preview realistic adjustments** asks the existing
OpenRouter GPT-4.1 model to classify cost behaviour and propose tighter bounds.
Only extracted expense labels, amounts, periods, positions and the requested
changes are sent; the PDF file is not sent to the model. Python verifies response
coverage and evidence IDs, then enforces conservative planning ceilings. These
are assumptions for review, not industry standards or verified contract limits:

- Telephone/internet: at most ±10%, with at most 0.25 revenue-response elasticity.
- Rent, insurance, depreciation and taxes: fixed by default; no inferred tax rates.
- Payroll: at most −10% / +25%, with at most 0.5 elasticity.
- Eligible variable costs: at most −30% / +100%, with at most 1.0 elasticity.
- Unknown costs and zero/negative baselines: remain unchanged.

For a revenue change, `proposed cost = baseline × (1 + revenue change × elasticity)`,
clamped to the reviewed range and rounded to cents. Explicit expense inputs outside
their range are rejected with the permitted minimum/maximum. No cost absorbs a
profit target. The model cannot widen the server ceilings or calculate money.

Review the before/after values, limits, reasons and dependent totals before creating
the PDF. The reviewed proposal is signed and bound to the original analysis; export
does not call the model again and rejects altered/unreviewed proposals. Downloads
preserve the original PDF content and metadata, with only the reviewed amount
changes. No planning banner is added. The application displays the assumptions;
the PDF preview highlights changed inputs and recalculated totals. Ordinary exact
edits remain available by switching planning off.

SuSa expense limits are checked on explicitly supplied entries. Automatic revenue-
driven cost bookings are not invented: debit/credit counterparts, balance checks,
source verification, OCR confidence and scan-export consent are still required.
Unbalanced entries and the supplied discrepant reviewed SuSa remain blocked.

Checks: `node test_finance_forecast.js`, `node test_finance_loading.js`,
`..\.venv\Scripts\python.exe -m unittest test_expense_forecast -v`, and
`..\.venv\Scripts\python.exe verify_expense_forecast.py` (one live paid model request).

## Upload-time English/German analysis

Select **Analysis language / Analysesprache** at the top of `/finance`. Upload
extracts the PDF locally, then automatically requests an OpenRouter GPT-4.1
explanation, including for recognized cash-basis BWA and ADDISON SuSa. Format
validation and monetary calculations remain local. The PDF file is not sent:
the model receives the extracted amount fields, labels, periods, header/footer
context and source-backed facts. These upload explanations use OpenRouter credits.

The side-panel overview shows income, expenses, result and expense categories in
English or German. Monetary values come from printed fields or explicit Decimal
calculations with source-page references. Year-to-date is kept distinct from a
full-year total. SuSa net movements are labelled as computed figures, not printed
BWA profit. The annual BWA shows all-year totals and individual months, including
a distinction between total expense inputs and the printed operating-cost row.

Language selection does not change number parsing, PDF contents or accounting
rules. Each finished language summary is cached for the current upload. AI errors
show a Retry button and do not prevent using the locally extracted fields.

Checks: `node test_finance_summary.js`,
`..\.venv\Scripts\python.exe -m unittest test_document_summary -v`, and
`..\.venv\Scripts\python.exe verify_document_summary.py` (two live paid requests).

The original preview displays the complete PDF by default. The separate page-image
selection preview is removed; inputs are selected from the analysis or dropdown.
The analysis overview includes page coverage with the amount count, reading method
and editable-field count for every page. Click an editable amount in the overview
or expense breakdown to select its input. Calculated totals remain read-only; SuSa
net expense rows offer their individual debit/credit movements when applicable.

After the overview is ready, **Change an amount** lists only the editable income
and expense values represented in that overview. Option labels use the same
translated category and reporting period, rather than the complete raw extraction
list. Calculated totals remain read-only. Switching language updates the dropdown
labels while preserving an eligible selected input and its replacement amount.

The change-amount controls remain disabled until the upload's AI summary has
finished. They never expose the temporary raw extraction list. Failed summaries
keep editing disabled and offer a retry; only the completed analysis populates
the dropdown.

The **AI model** selector supports GPT-4.1 (default), GPT-6 Astra, GPT-6.1 Sol,
and GPT-6 Luna through OpenRouter. The browser remembers
the choice and sends it with each request. Background jobs retain their own
selection; users do not change each other's model. Changing models refreshes
the AI summary and invalidates the old preview. Pricing and account availability
depend on OpenRouter. Source validation and Decimal calculations remain local.

Income changes leave expense inputs unchanged by default. The optional
**Assume the income change comes from sales volume** scenario allows bounded
variable-cost proposals, assuming unchanged prices and a similar sales mix.
Payroll, telephone, rent, taxes and other non-variable expenses do not scale
automatically. The review explains each changed or unchanged expense and flags
estimates that reach a safeguard. Safeguards are not evidence of actual budgets,
capacity or achievable profit. Explicit expense edits remain subject to review.

Cash-basis BWA period links work in both directions: a monthly edit adds its delta
to year-to-date, preserving earlier months; a YTD edit allocates the current month
by assigning the full correction delta to that month, preserving earlier-month
cumulative amounts. This correction policy is labeled in the preview; explicit
monthly entries take precedence. SuSa does not reverse-
allocate movements or invent counterpart bookings. Prior-year inputs stay fixed;
current-period repeats, totals, variances and percentages are recalculated.
