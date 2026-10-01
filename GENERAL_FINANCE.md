# General financial PDFs

Open `/finance` and select **Other PDFs / scans / images**, or upload a document that does not match the automatic BWA layout. This workflow appears within the same finance screen, with no URL change or duplicate upload. The older `/general` URL redirects to `/finance`. It accepts readable text PDFs and PNG, JPEG, TIFF, BMP, or WebP images. Images are converted to an in-memory PDF, including TIFF frames. Existing RapidOCR handles scanned pages. Select German or international number separators and, for sideways scans, a rotation before analyzing. The original document is previewed with all pages in the browser's PDF viewer.

The extractor lists amounts with exactly two decimals, their page numbers, identifiers, and text context or OCR confidence. OCR may miss or misread values. Currency-symbol-attached strings, unusual monetary formats, unreadable scans, and complex fragmented text may not extract completely. This is general document intake, not a guarantee of understanding every financial statement.

Choose an input amount to see its location highlighted on the original PDF. Define each calculated target using source amounts with explicit plus/minus signs. Add rules for every downstream subtotal or total you want updated. Rules can depend on other rule targets; cycles and duplicate/invalid sources are rejected. Before recalculating, the app verifies each rule against the original printed amount. A mismatch blocks the update. The backend uses Decimal for exact arithmetic. Only defined dependencies are updated; undisclosed relationships cannot be inferred reliably.

Example: if `c1` is revenue 100.00, `c2` is costs 30.00, and `c3` is profit 70.00, define `c3 = +c1 -c2`. Editing `c1` to 120.00 then changes `c3` to 90.00. To update an annual total as well, add its rule explicitly. S/H accounting markers are preserved as labels; the rule's signs must represent the verified debit/credit interpretation. Taxes, exchange rates, rounding policies, and complex accounting relationships are not guessed.

Click **Verify rules & preview changes**, review the list, and then export. The general-format output uses image-based changed pages with approximate fonts in the edited regions. The UI requires explicit consent to this output. Unchanged pages are copied from the source. Changed pages preserve visual page dimensions and rotation but lose searchable text, vector detail, and interactive features. Existing PDF form widgets on a changed page block export. Original PDFs are never overwritten. Use the dedicated `/finance` BWA workflow when its format is supported; it edits original numeric text and preserves fonts.

No new LLM is used unless explicitly approved and enabled. The **Suggest rules with approved local LLM** feature is prepared but disabled by default. It sends extracted amounts, coordinates, and row context to local Ollama. Responses are constrained to additive/subtractive relationships using existing cell IDs. Invalid IDs, wrong arithmetic, duplicate targets, self-reference, and cycles are rejected. Baseline-consistent suggestions are displayed; the user must select and accept reviewed proposals before they become rules. Arithmetic agreement does not establish accounting meaning or complete dependency coverage.

Before enabling a model, obtain the user's explicit approval of that model and its role. After approval, configure `PDF_EDITOR_OLLAMA_MODEL` and `PDF_EDITOR_AI_APPROVED=1` in the server process environment and restart. No model has been invoked during implementation; automated tests use mocked responses. The current Ollama installation lists `qwen3:14b`, which is proposed for user approval, not enabled. There is no cloud API call or automatic model download in this feature.

The analysis is signed by the server and tied to the uploaded PDF. Reanalyze after restarting the server. Multiple edits are supported by the backend; the current form edits one input at a time.

Tests:

```powershell
..\.venv\Scripts\python.exe -m unittest test_general_finance -v
```
