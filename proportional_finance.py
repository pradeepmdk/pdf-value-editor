"""Explicit proportional BWA scenarios, separate from recorded transactions."""
from decimal import Decimal, ROUND_HALF_UP
import pymupdf
from finance import analyze as source_analyze, amount, fmt, COSTS
from finance_workflow import plan, apply


def scenario(data, extracted, edits, export=False):
    source = source_analyze(data)
    if not source['verified'] or extracted.get('export_mode') != 'direct':
        raise ValueError('Proportional simulation supports verified annual DATEV BWA 01 PDFs only.')
    cells = {c['id']: c for c in extracted['cells']}
    rows = {r['id']: r for r in source['rows']}
    factors = {}; explicit = {}
    for edit in edits:
        identifier = edit['id']; cell = cells.get(identifier)
        if not cell or cell.get('editable') is False or cell['row'] not in ['revenue', *COSTS] or cell['column_index'] >= 12:
            raise ValueError('Select monthly sales revenue or a monthly operating expense for proportional simulation.')
        column = cell['column_index']; row = cell['row']
        baseline = amount(rows[row]['values'][column]); replacement = amount(edit['value'].strip())
        if baseline <= 0 or replacement < 0:
            raise ValueError('The driving amount must originally be positive and its replacement must be non-negative. A zero baseline has no percentage ratio.')
        factor = replacement / baseline
        if column in factors and factors[column] != factor:
            raise ValueError('Use one driving amount per month. Multiple changes in the same month must imply exactly the same percentage.')
        factors[column] = factor; explicit[identifier] = fmt(replacement)
    if not factors:
        raise ValueError('Enter at least one changed monthly revenue or expense amount.')
    expanded = []
    for column, factor in factors.items():
        for row in ['revenue', *COSTS]:
            identifier = f'{row}_{column}'
            value = (amount(rows[row]['values'][column]) * factor).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            expanded.append({'id': identifier, 'value': explicit.get(identifier, fmt(value))})
    # The proportional assumption supplies input values. Standard BWA formulas
    # then calculate all subtotals, profit, and annual sums without cycles.
    rules = extracted['candidate_rules']
    result = plan(data, extracted, expanded, rules)
    for change in result['changes']:
        if change['id'] not in explicit and change['reason'] == 'Input edit':
            change['reason'] = 'Proportional simulation'
    result['simulation'] = True
    result['note'] = 'SIMULATION: monthly sales and operating expenses scaled proportionally from the original. Other inputs stay fixed. Rounded to cents; BWA totals verified. Not actual bookkeeping or a tax filing.'
    if not export:
        return result
    output, _ = apply(data, extracted, expanded, rules)
    with pymupdf.open(stream=output, filetype='pdf') as doc:
        for page in doc:
            page.insert_text((24, 12), 'SIMULATION - PROPORTIONAL PLANNING ONLY - NOT ACTUAL BOOKKEEPING / TAX FILING', fontsize=8, color=(.8, 0, 0))
        doc.set_metadata({'title': 'BWA proportional planning simulation', 'subject': result['note']})
        output = doc.tobytes(garbage=3, deflate=True)
    return output, result
