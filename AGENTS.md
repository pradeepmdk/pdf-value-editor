# PDF value editor rules

## Scope and structure

- Keep application code, frontend, tests, and documentation in this folder.
- `pdf_editor.py` serves the website and implements the reusable editing API.
- `editor.html` contains the frontend. Keep it usable without a frontend build step.
- Original PDFs and the existing shared virtual environment live in the parent folder.
- Never overwrite original PDFs. Return edited copies with descriptive filenames.

## PDF fidelity

- Change only the exact numeric values and occurrences selected by the user.
- Preserve page dimensions, rotation, fonts, text positions, lines, tables, and other content.
- Do not recalculate dependent values or totals unless explicitly requested.
- Preserve the user's number separators exactly. Do not silently normalize input.
- Reject unsupported scans, encodings, split text, and replacements that cannot preserve layout safely. Explain the limitation in the UI.
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
