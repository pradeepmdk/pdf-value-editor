"""One intake/decision/review/export workflow with format-specific fidelity checks."""
import hashlib
import pymupdf
from general_finance import signed_extract, calculate, render_changes


def analyze(data, locale='de', rotation=0):
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        text = ''.join(page.get_text() for page in doc)
    if 'DATEV-BWA' not in text or 'BWA Form 01' not in text:
        result = signed_extract(data, locale, rotation)
        result['analysis']['statement']['export_mode'] = 'image'
    else:
        from finance import analyze as analyze_bwa, RULES, amount
        source = analyze_bwa(data)
        if not source['verified']:
            raise ValueError('The source contains unexplained printed total discrepancies. Resolve them before recalculation.')
        cells = []; candidate_rules = []
        for row in source['rows']:
            for column, cell in enumerate(row['cells']):
                identifier = f"{row['id']}_{column}"
                cells.append({'id': identifier, 'page': 1, 'text': cell['text'],
                    'value': str(amount(cell['text'])), 'suffix': '', 'context': row['label'] + ' / ' + source['columns'][column],
                    'label': row['label'], 'column': source['columns'][column],
                    'box': cell['rect'], 'mode': 'text', 'rotation': 0, 'row': row['id'], 'column': column,
                    'editable': row['editable'] and column < 12})
                if column < 12 and row['id'] in RULES:
                    candidate_rules.append({'target': identifier, 'terms': [{'source': f'{key}_{column}', 'sign': sign} for key, sign in RULES[row['id']]]})
                elif column == 12:
                    candidate_rules.append({'target': identifier, 'terms': [{'source': f"{row['id']}_{i}", 'sign': 1} for i in range(12)]})
        statement = {'pages': 1, 'cells': cells, 'locale': 'de', 'notes': ['Original printed relationships passed validation. AI selects affected dependencies for review.'],
                     'export_mode': 'direct', 'candidate_rules': candidate_rules, 'automatic_rules': False}
        result = {'analysis': {'kind': 'general_finance', 'digest': hashlib.sha256(data).hexdigest(), 'statement': statement}}
    from scan_editor import _signature
    result['signature'] = _signature(result['analysis'])
    return result


def plan(data, extracted, edits, rules):
    result = calculate(extracted, edits, rules)
    if extracted.get('export_mode') == 'direct':
        from finance import plan as source_plan
        by_id = {c['id']: c for c in extracted['cells']}
        mapped = [{'row': by_id[e['id']]['row'], 'column': by_id[e['id']]['column'], 'value': e['value']} for e in edits]
        expected = source_plan(data, mapped)['changes']
        expected_values = {f"{c['row_id']}_{c['column_index']}": c['new'] for c in expected}
        actual = {c['id']: c['new'] for c in result['changes']}
        if actual != expected_values:
            missing = ', '.join(sorted(set(expected_values) - set(actual)))
            raise ValueError('Reviewed dependencies do not cover the complete affected statement, or amounts disagree. Review unresolved AI decisions and add missing rules. Missing fields: ' + (missing or 'amount mismatch'))
    return result


def apply(data, extracted, edits, rules, allow_raster=False):
    result = plan(data, extracted, edits, rules)
    if extracted.get('export_mode') != 'direct':
        from exact_finance import apply_exact
        output = apply_exact(data, result['changes'], extracted['locale'])
        result['note'] = 'Original native fonts and sizes preserved and saved amounts verified. Only reviewed formulas were applied; source ledgers were not changed.'
        return output, result
    from finance import apply as direct_apply
    by_id = {c['id']: c for c in extracted['cells']}
    mapped = [{'row': by_id[e['id']]['row'], 'column': by_id[e['id']]['column'], 'value': e['value']} for e in edits]
    output, _ = direct_apply(data, mapped)
    result['note'] = 'The edited copy preserved original text and fonts and passed saved-statement formula verification.'
    return output, result
