# BWA recalculation and optional local AI

Open `/finance`, or click **BWA analysis & automatic recalculation** on the main page. Upload the original one-page annual DATEV BWA 01 text PDF. The app extracts all 32 rows and checks monthly formulas and annual sums before enabling edits.

Choose a monthly input row and month, enter a new EUR amount such as `62.315,78`, and click **Preview affected amounts**. Review the before/after list. Then click **Create recalculated PDF** and inspect/download the result. The source PDF is preserved. Each operation starts from the uploaded original. The Python API accepts multiple input edits in a single recalculation, while the current website handles one input edit per operation.

## Verified rules

- Gesamtleistung = revenue + inventory changes + activated own work.
- Rohertrag = Gesamtleistung - material/purchases.
- Betrieblicher Rohertrag = Rohertrag + other operating income.
- Gesamtkosten = the eleven cost-category rows.
- Betriebsergebnis = Betrieblicher Rohertrag - Gesamtkosten.
- Neutraler Aufwand = interest expense + other neutral expense.
- Neutraler Ertrag = interest income + other neutral income + imputed costs credited back.
- Ergebnis vor Steuern = operating result - neutral expense + neutral income.
- Vorläufiges Ergebnis = pretax result - income/profit tax.
- Annual amounts = sum of the twelve monthly amounts.

Reference: [DATEV explanation of BWA 01](https://www.datev.de/dnlexom/v2/content/files/st2110633099_de.pdf). Income/profit tax is an input amount, not an automatically estimated tax. Nonzero unassigned accounts are blocked until their treatment is verified. Printed amounts must already agree with these rules; existing discrepancies are shown and block automatic edits. Calculated rows and annual totals cannot be edited directly.

The parser requires the supported annual layout and exact numeric operators matching extracted cell positions. Unsupported layouts, scanned BWA documents, SuSa trial balances, and other statement formats are rejected for automatic recalculation. Their basic text/OCR editing remains available. Amounts use exact Decimal arithmetic; no AI computes money. Changed numbers keep their right edges and original font sizes; excessively wide amounts are rejected. The output is re-extracted and all rules are checked before returning it.

For the sample, changing January revenue from `52.315,78` to `62.315,78` updates 14 cells, including the annual revenue to `863.623,36` and annual provisional result to `5.150,72`.

## Optional local AI with Ollama

A local model can classify row roles and flag uncertain interpretations. It does not replace extraction validation, calculation rules, or exact arithmetic. The optional **Ask local AI to review row roles** button sends row labels and IDs to Ollama on `127.0.0.1:11434`; it does not upload the PDF to a cloud API. Suggestions are displayed for review and cannot change formulas or amounts.

Install [Ollama](https://ollama.com/download) separately. A practical starting model is [Qwen3 8B](https://ollama.com/library/qwen3:8b). Hardware performance and available memory should be checked locally. Download the model once:

```powershell
ollama pull qwen3:8b
```

Keep Ollama running. If its background service is not running, start `ollama serve` in a separate terminal. Configure the model in the same PowerShell terminal used to launch this application:

```powershell
$env:PDF_EDITOR_OLLAMA_MODEL = 'qwen3:8b'
.\start.bat --host 0.0.0.0 --port 8000 --allowed-origin http://192.168.1.39:8000 --allowed-origin http://117.247.105.96:8000
```

In Bash:

```bash
export PDF_EDITOR_OLLAMA_MODEL=qwen3:8b
bash start.sh
```

The connector uses [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) and validates the returned IDs and roles. Ollama and a real model have not been installed or evaluated by these code changes. Automated tests exercise the connector with a mocked response. The deterministic BWA workflow works without Ollama or Jev.

Jev could serve the same advisory classification role through its Choice primitive, with supplied row-role options. A Jev connector is not included in this version. Any AI-proposed formula for a new format must be reviewed and translated into explicit Python rules before automatic PDF updates are enabled.

## Tests

```powershell
..\.venv\Scripts\python.exe -m unittest test_finance -v
```

Tests verify exact revenue propagation, multiple edits, cent precision, baseline discrepancy rejection, unsupported scans, PDF pixel preservation outside changed cells, and the local-model adapter's advisory boundary.
