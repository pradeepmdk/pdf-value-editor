# PDF value editor rules

## Scope and structure

- Keep application code, frontend, tests, and documentation in this folder.
- `pdf_editor.py` serves the website and implements the reusable editing API.
- `editor.html` contains the frontend. Keep it usable without a frontend build step.
- Original PDFs and the existing shared virtual environment live in the parent folder.
- Never overwrite original PDFs. Return edited copies with descriptive filenames.

## PDF fidelity

- Accept numbers, letters, and mixed single-line text in both editors. Change only the exact text and occurrences selected by the user.
- Preserve page dimensions, rotation, fonts, text positions, lines, tables, and other content. Longer replacements may use a reduced font size to fit the original region; keep other text unchanged and disclose this behavior.
- Do not recalculate dependent values or totals unless explicitly requested.
- Recalculation is authorized in the dedicated BWA finance workflow. Validate the source structure and formulas, use Decimal, preview all dependent changes, preserve unrelated cells, and verify the saved PDF against the same rules. Reject unsupported formats and unexplained source discrepancies.
- Model classifications are advisory only. Never let Jev or a local LLM silently replace formulas, calculate authoritative amounts, or apply unreviewed accounting interpretations.
- The user requires advance notice before choosing or using a new LLM. Do not install, download, configure, or invoke a new model without the user's approval. Existing RapidOCR usage is authorized; the optional local LLM connector remains unused until a model is explicitly selected.
- General statement rules must be user-reviewed and match original printed values before recalculation. Never claim universal automatic formula recognition. General-format image export requires its explicit UI consent; preserve untouched pages and explain loss of searchable text/features on changed pages.
- Preserve the user's number separators exactly. Do not silently normalize input.
- Direct text mode must reject scans, encodings, split text, and replacements that cannot preserve layout safely. Explain the limitation in the UI.
- OCR mode is authorized for scanned PDFs. Require a confident exact OCR match and explicit selection; preserve source image pixels outside the selected region and keep image placement and other pages unchanged. Replacement fonts are approximate; expose that limitation and require preview review.
- Do not substitute rasterized pages, white rectangles, or reconstructed layouts for direct text editing without explicit authorization.

## Backend and frontend

- Keep the default server bound to localhost and process uploads in memory.
- Retain upload limits and origin checks. Do not log PDF contents or base64 payloads.
- Validate input server-side and show actionable errors in the website.
- Each edit starts from the uploaded original. Invalidate stale download links after input changes.
- Keep a preview and download step so users can inspect results.
- Update requirements and README when dependencies or startup instructions change.

## Verification

- From this folder run: `..\.venv\Scripts\python.exe -m unittest test_pdf_editor -v`.
- Tests require NumPy and the original BWA sample in the parent folder.
- For editing changes, check exact text replacements, match counts, single-occurrence selection, and rejected unsupported edits.
- Render before and after: pixels outside the selected numbers must be identical for the supported sample. Account for page rotation when comparing regions.
- For server changes, verify the website, preview endpoint, and edited PDF response.
- Report supported formats and any remaining limitations honestly.
