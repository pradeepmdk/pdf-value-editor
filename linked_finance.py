"""Reviewed cross-report scenario graph. Never fabricates account allocations."""
import base64
import hashlib
import hmac
import io
import json
from pathlib import PurePath
import zipfile
import pymupdf
from decimal import Decimal

from finance_workflow import analyze as analyze_document
from general_finance import calculate, parse_amount, validate_analysis
from scan_editor import _signature


def demo():
    """Explicitly fictitious zero-VAT scenario, never used to infer real reports."""
    rows = [[('Revenue / Umsatzerloese', '200.000,00'), ('Costs / Kosten', '60.000,00'), ('Profit / Ergebnis', '140.000,00')],
            [('Sales credit / Erloese Haben', '200.000,00'), ('Debtor debit / Forderungen Soll', '200.000,00'),
             ('Expense debit / Aufwand Soll', '60.000,00'), ('Bank credit / Bank Haben', '60.000,00')],
            [('Revenue / Umsatzerloese', '200.000,00'), ('Costs / Kosten', '60.000,00'), ('Profit / Ergebnis', '140.000,00')]]
    documents = []
    for title, data in zip(('BWA', 'SuSa', 'KER'), rows):
        with pymupdf.open() as doc:
            p = doc.new_page(); p.insert_text((50, 40), f'DEMO - FICTITIOUS {title}', fontsize=16)
            p.insert_text((50, 65), 'Demo company | January 2026 | Simplified zero-VAT scenario', fontsize=10)
            for i, (label, value) in enumerate(data):
                p.insert_text((50, 120+i*35), label, fontsize=10)
                p.insert_text((390, 120+i*35), value, fontname='hebo', fontsize=10)
            documents.append({'name': title+'-demo.pdf', 'pdf': base64.b64encode(doc.tobytes()).decode(), 'entity':'Demo company', 'period':'2026-01'})
    def rule(target, *terms): return {'target':target, 'terms':[{'source':s,'sign':sign} for s,sign in terms]}
    return {'documents':documents, 'rules':[rule('d1:c1',('d2:c1',1)), rule('d2:c2',('d2:c1',1)),
        rule('d3:c1',('d1:c1',1)), rule('d1:c2',('d2:c3',1)), rule('d2:c4',('d2:c3',1)), rule('d3:c2',('d1:c2',1)),
        rule('d1:c3',('d1:c1',1),('d1:c2',-1)), rule('d3:c3',('d3:c1',1),('d3:c2',-1))],
        'edits':[{'id':'d2:c1','value':'1.000.000,00'}, {'id':'d2:c3','value':'80.000,00'}]}


def _documents(items):
    if not isinstance(items, list) or not 2 <= len(items) <= 6:
        raise ValueError('Upload two to six related reports.')
    result = []; total = 0
    for i, item in enumerate(items):
        data = base64.b64decode(item['pdf'], validate=True); total += len(data)
        name = str(item.get('name', f'report-{i+1}.pdf')).replace('\\', '/').split('/')[-1]
        entity = str(item.get('entity', '')).strip(); period = str(item.get('period', '')).strip()
        if not entity or not period or len(entity) > 160 or len(period) > 80:
            raise ValueError('Confirm the company and accounting period for every report.')
        result.append({'id': f'd{i+1}', 'name': name[:180], 'entity': entity, 'period': period, 'data': data,
                       'digest': hashlib.sha256(data).hexdigest()})
    if total > 20 * 1024 * 1024:
        raise ValueError('Combined reports must be smaller than 20 MB.')
    if len({d['entity'].casefold() for d in result}) != 1 or len({d['period'].casefold() for d in result}) != 1:
        raise ValueError('Reports must belong to the same company and accounting period. Do not link unrelated samples.')
    return result


def analyze(items, locale='de', rotation=0):
    documents = _documents(items); cells = []; rules = []; reports = []
    for d in documents:
        signed = analyze_document(d['data'], locale, rotation)
        s = validate_analysis(d['data'], signed)
        if s.get('profile'):
            raise ValueError('Use the individual verified finance workflow for this cash-basis BWA or scanned ADDISON SuSa. Cross-report account allocation for these layouts is not supported.')
        if s['locale'] != locale:
            raise ValueError('All reports must use the selected number format.')
        for c in s['cells']:
            cells.append({**c, 'local_id': c['id'], 'id': d['id'] + ':' + c['id'],
                          'document': d['id'], 'document_name': d['name'],
                          'context': d['name'] + ' | ' + c['context']})
        for r in s.get('candidate_rules', []):
            rules.append({'target': d['id'] + ':' + r['target'],
                          'terms': [{'source': d['id'] + ':' + t['source'], 'sign': t['sign']} for t in r['terms']]})
        reports.append({k: d[k] for k in ('id', 'name', 'entity', 'period', 'digest')})
        reports[-1].update({'analysis': signed, 'pages': s['pages'], 'ocr': any(c['mode'] == 'ocr' for c in s['cells'])})
    value = {'kind': 'linked_finance', 'reports': reports, 'cells': cells, 'locale': locale, 'base_rules': rules,
             'note': 'Only reviewed relationships are synchronized. Matching numbers alone do not establish an accounting relationship. Source ledgers are not changed.'}
    return {'analysis': value, 'signature': _signature(value)}


def validate(items, signed):
    value = signed['analysis']
    if value.get('kind') != 'linked_finance' or not hmac.compare_digest(_signature(value), signed['signature']):
        raise ValueError('Linked analysis is invalid or expired. Analyze the reports again.')
    documents = _documents(items)
    expected = [{k: d[k] for k in ('id', 'name', 'entity', 'period', 'digest')} for d in documents]
    actual = [{k: d[k] for k in ('id', 'name', 'entity', 'period', 'digest')} for d in value['reports']]
    if actual != expected:
        raise ValueError('Reports or company/period settings changed. Analyze again.')
    return value, documents


def plan(items, signed, edits, rules, reviewed=False):
    value, documents = validate(items, signed)
    if reviewed is not True:
        raise ValueError('Review and confirm the account allocation and report relationships before calculating.')
    if not isinstance(rules, list) or not isinstance(edits, list) or not edits:
        raise ValueError('Select an independent input and reviewed report rules.')
    base_targets = {r['target'] for r in value['base_rules']}
    if any(r['target'] in base_targets for r in rules):
        raise ValueError('A verified report subtotal cannot be replaced by another formula.')
    by_id = {c['id']: c for c in value['cells']}
    if len({e['id'] for e in edits}) != len(edits):
        raise ValueError('Each input field can be changed only once in a calculation.')
    for e in edits:
        cell = by_id.get(e['id'])
        if not cell or cell.get('editable') is False:
            raise ValueError('Change an independent input, not a report subtotal.')
        _, suffix = parse_amount(e['value'], value['locale'])
        if suffix != cell['suffix']:
            raise ValueError('Preserve the original S/H suffix. Debit/credit direction must be encoded in reviewed rules.')
    combined = value['base_rules'] + rules
    result = calculate(value, edits, combined)
    result['rules'] = combined
    changed_documents = {c['document'] for c in result['changes']}
    if len(changed_documents) < 2:
        raise ValueError('No other report is affected. Add and review the cross-report allocation/link rules before synchronized export.')
    # A recognized BWA must still satisfy its complete source-validated formulas.
    for report, document in zip(value['reports'], documents):
        s = validate_analysis(document['data'], report['analysis'])
        if s.get('export_mode') == 'direct' and report['id'] in changed_documents:
            from finance import plan as bwa_plan
            changes = [c for c in result['changes'] if c['document'] == report['id']]
            mapped = [{'row': c['row'], 'column': c['column_index'], 'value': c['new']} for c in changes if c.get('editable')]
            expected = bwa_plan(document['data'], mapped)['changes']
            if {f"{c['row_id']}_{c['column_index']}": c['new'] for c in expected} != {c['local_id']: c['new'] for c in changes}:
                raise ValueError('Linked BWA changes do not cover all verified monthly and annual relationships.')
    result['exact_export_possible'] = all(c['mode'] == 'text' for c in result['changes'])
    result['note'] = value['note'] + ' Unlinked fields remain unchanged. Review coverage; baseline arithmetic alone is not proof of accounting meaning.'
    return result


def apply(items, signed, edits, rules, reviewed=False, coverage=False):
    if coverage is not True:
        raise ValueError('Review all changed fields and confirm dependency coverage before export.')
    result = plan(items, signed, edits, rules, reviewed)
    value, documents = validate(items, signed)
    from exact_finance import apply_exact
    outputs = []; archive = io.BytesIO()
    # Finish every edit before returning any output: no partially exported bundle.
    for document in documents:
        changes = [c for c in result['changes'] if c['document'] == document['id']]
        output = apply_exact(document['data'], changes, value['locale']) if changes else document['data']
        name = document['id'] + '-' + PurePath(document['name']).stem + '-scenario.pdf'
        outputs.append({'name': name, 'pdf': base64.b64encode(output).decode(), 'changed': len(changes)})
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for output in outputs: z.writestr(output['name'], base64.b64decode(output['pdf']))
        z.writestr('calculation-review.json', json.dumps({'company': documents[0]['entity'], 'period': documents[0]['period'],
            'rules': result['rules'], 'changes': result['changes'], 'note': result['note']}, ensure_ascii=False, indent=2))
    return {'documents': outputs, 'zip': base64.b64encode(archive.getvalue()).decode(), **result}
