# General financial PDFs

Open `/general` from **General financial PDF analysis** on the main page. This workflow is independent of the BWA and SuSa templates. It accepts readable text PDFs and uses the existing local RapidOCR engine on scanned pages. Select German or international number separators and, for sideways scans, a rotation before analyzing.

The extractor lists amounts with exactly two decimals, their page numbers, identifiers, and text context or OCR confidence. OCR may miss or misread values. Currency-symbol-attached strings, unusual monetary formats, unreadable scans, and complex fragmented text may not extract completely. This is general document intake, not a guarantee of understanding every financial statement.

Choose an input amount to see its location highlighted on the original PDF. Define each calculated target using source amounts with explicit plus/minus signs. Add rules for every downstream subtotal or total you want updated. Rules can depend on other rule targets; cycles and duplicate/invalid sources are rejected. Before recalculating, the app verifies each rule against the original printed amount. A mismatch blocks the update. The backend uses Decimal for exact arithmetic. Only defined dependencies are updated; undisclosed relationships cannot be inferred reliably.

Example: if `c1` is revenue 100.00, `c2` is costs 30.00, and `c3` is profit 70.00, define `c3 = +c1 -c2`. Editing `c1` to 120.00 then changes `c3` to 90.00. To update an annual total as well, add its rule explicitly. S/H accounting markers are preserved as labels; the rule's signs must represent the verified debit/credit interpretation. Taxes, exchange rates, rounding policies, and complex accounting relationships are not guessed.

Click **Verify rules & preview changes**, review the list, and then export. The general-format output uses image-based changed pages with approximate fonts in the edited regions. The UI requires explicit consent to this output. Unchanged pages are copied from the source. Changed pages preserve visual page dimensions and rotation but lose searchable text, vector detail, and interactive features. Existing PDF form widgets on a changed page block export. Original PDFs are never overwritten. Use the dedicated `/finance` BWA workflow when its format is supported; it edits original numeric text and preserves fonts.

No new LLM is used by this workflow. The user requires advance notice before a model is selected or used. A future local model may propose candidate relationships for user review; those suggestions must still pass source arithmetic checks and never become authoritative merely because a model produced them. The optional Ollama BWA classification connector remains unconfigured unless the user explicitly selects a model.

The analysis is signed by the server and tied to the uploaded PDF. Reanalyze after restarting the server. Multiple edits are supported by the backend; the current form edits one input at a time.

Tests:

```powershell
..\.venv\Scripts\python.exe -m unittest test_general_finance -v
```
