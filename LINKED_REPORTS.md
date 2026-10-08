# Linked finance reports / Verknuepfte Finanzberichte

Open `/finance` and choose **Linked reports (BWA / SuSa / KER)**. This is a reviewed scenario calculator, not a replacement for the source accounting ledger.

1. Upload two to six PDF reports, combined under 20 MB. Enter the company and the same accounting-period basis for each. Check these declarations against the actual report headers.
2. Analyze. Native amounts are extracted; scanned pages use OCR for inspection. Recognized annual DATEV BWA reports include source-validated monthly and annual relationships.
3. Review the relationships. Add cross-report allocation rules and generic report totals using target/source selectors and explicit plus/minus operations. No link is inferred just because two amounts are equal. Every formula must match original printed amounts. S/H suffixes are labels; reviewed signs establish debit/credit direction.
4. Select an independent input, enter a replacement and click **Add / update pending change**. Repeat for other inputs. All pending edits are applied simultaneously to the original values, then the dependency graph is recalculated using Decimal.
5. Confirm formula/allocation review and click **Recalculate all linked reports**. Review the before/after table and unlinked fields. Cycles, conflicting targets, incorrect baselines and incomplete recognized BWA graphs block export.
6. Confirm dependency coverage, create copies, and inspect the previews. Download individual PDFs or a ZIP with a calculation-review manifest. Source files and accounting software remain untouched.

## Exact appearance

Finance export no longer uses approximate page images. Supported native Base14-font amount operators retain their original font resources and sizes; right edges remain aligned and adjacent text is checked for overlap. Saved amounts/fonts/sizes are checked again. Oversized amounts, encoded/split text and unsupported fonts/transforms fail closed. Scanned changed amounts have no editable original font, so strict export is unavailable. Supply native exports or regenerate through DATEV/Lexware to meet exact appearance requirements.

Single-report analysis still offers optional Jev dependency selection. Multiple edits use separate model requests and one combined Python calculation; conflicting formulas are rejected. Linked-report account allocation is reviewed/manual at present. Linked analysis never selects or invokes a new model automatically.

## German accounting context / Deutscher Kontext

- **BWA (Betriebswirtschaftliche Auswertung):** business performance evaluation; aggregates bookkeeping accounts into revenue/cost reporting positions.
- **SuSa (Summen- und Saldenliste):** account totals and balances, including debit/credit movements. Synchronization requires accounts, periods, aggregation signs and counterpart/VAT rules.
- **KER (Kurzfristige Erfolgsrechnung):** short-term profit report, commonly a BWA view rather than a third independent ledger.

A turnover edit does not determine VAT, debtor/bank allocation, account allocation, month allocation or unrelated expenses. Supply and review these rules. Earlier BWA/SuSa samples concern different companies/periods; no matching KER has been provided. They must not be presented as one synchronized real client set.

References: [DATEV reporting overview](https://www.datev.de/web/de/unternehmen/loesungen/rechnungswesen/controlling/transparente-auswertungen), [Lexware accounting reports](https://help.lexware.de/de-form/collections/1335699-buchhalterische-auswertungen).

Tests: `..\.venv\Scripts\python.exe -m unittest test_linked_finance test_jev_dependencies test_finance_workflow -v`.
