import base64
import io
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path
import numpy as np
import pymupdf
from linked_finance import analyze, plan, apply
from exact_finance import apply_exact


def pdf(rows):
    with pymupdf.open() as doc:
        page = doc.new_page()
        for i, (label, amount) in enumerate(rows):
            page.insert_text((50, 60+i*30), label, fontname='helv', fontsize=10)
            page.insert_text((310, 60+i*30), amount, fontname='hebo', fontsize=10)
        return doc.tobytes()


class LinkedTests(unittest.TestCase):
    def setUp(self):
        rows = [[('Revenue', '100.00'), ('Costs', '30.00'), ('Profit', '70.00')],
                [('Sales credit', '100.00'), ('Debtor debit', '100.00')],
                [('Revenue', '100.00'), ('Costs', '30.00'), ('Profit', '70.00')]]
        self.data = [pdf(r) for r in rows]
        self.items = [{'name': name+'.pdf', 'pdf': base64.b64encode(data).decode(), 'entity': 'Demo company', 'period': '2026-01'}
                      for name, data in zip(['BWA', 'SuSa', 'KER'], self.data)]
        self.signed = analyze(self.items, 'en')
        def rule(target, *terms): return {'target': target, 'terms': [{'source': s, 'sign': sign} for s, sign in terms]}
        self.rules = [rule('d1:c1', ('d2:c1', 1)), rule('d2:c2', ('d2:c1', 1)), rule('d3:c1', ('d1:c1', 1)),
                      rule('d1:c3', ('d1:c1', 1), ('d1:c2', -1)), rule('d3:c3', ('d3:c1', 1), ('d3:c2', -1))]
        self.edits = [{'id': 'd2:c1', 'value': '1,000,000.00'}]

    def test_three_reports_recalculate_exact_fonts_and_outside_pixels(self):
        result = apply(self.items, self.signed, self.edits, self.rules, True, True)
        self.assertEqual(len(result['changes']), 6)
        self.assertEqual({c['new'] for c in result['changes']}, {'1,000,000.00', '999,970.00'})
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(result['zip']))) as z:
            self.assertEqual(len(z.namelist()), 4)
        for i, output in enumerate(result['documents']):
            with pymupdf.open(stream=self.data[i], filetype='pdf') as old, pymupdf.open(stream=base64.b64decode(output['pdf']), filetype='pdf') as new:
                old_spans = [s for b in old[0].get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']]
                new_spans = [s for b in new[0].get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']]
                self.assertEqual([(s['font'], s['size']) for s in old_spans], [(s['font'], s['size']) for s in new_spans])
                before = old[0].get_pixmap(alpha=False); after = new[0].get_pixmap(alpha=False)
                a = np.frombuffer(before.samples, dtype=np.uint8).reshape(before.height, before.width, 3)
                b = np.frombuffer(after.samples, dtype=np.uint8).reshape(after.height, after.width, 3)
                mask = np.ones(a.shape[:2], dtype=bool)
                for s in old_spans+new_spans:
                    if s['bbox'][0] > 200:
                        x0,y0,x1,y1 = s['bbox']; mask[max(0,int(y0)-2):int(y1)+3,max(0,int(x0)-2):int(x1)+3] = False
                self.assertTrue(np.array_equal(a[mask], b[mask]))

    def test_company_period_mismatch_and_modified_analysis_rejected(self):
        items = deepcopy(self.items); items[1]['period'] = '2026-02'
        with self.assertRaisesRegex(ValueError, 'same company'): analyze(items, 'en')
        signed = deepcopy(self.signed); signed['analysis']['cells'][0]['value'] = '999.00'
        with self.assertRaisesRegex(ValueError, 'invalid'): plan(self.items, signed, self.edits, self.rules, True)

    def test_review_wrong_formula_cycle_and_unlinked_change_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Review'): plan(self.items, self.signed, self.edits, self.rules)
        with self.assertRaisesRegex(ValueError, 'coverage'): apply(self.items, self.signed, self.edits, self.rules, True)
        with self.assertRaisesRegex(ValueError, 'No other report'): plan(self.items, self.signed, self.edits, [], True)
        rules = deepcopy(self.rules); rules[3]['terms'][1]['sign'] = 1
        with self.assertRaisesRegex(ValueError, 'original statement'): plan(self.items, self.signed, self.edits, rules, True)
        rules = deepcopy(self.rules); rules.append({'target':'d2:c1','terms':[{'source':'d1:c1','sign':1}]})
        with self.assertRaisesRegex(ValueError, 'cycle'): plan(self.items, self.signed, self.edits, rules, True)

    def test_scans_and_font_size_overflow_blocked(self):
        change = {**self.signed['analysis']['cells'][0], 'new': '200.00', 'mode': 'ocr'}
        with self.assertRaisesRegex(ValueError, 'scanned'): apply_exact(self.data[0], [change], 'en')
        change['mode'] = 'text'; change['new'] = '1' * 100 + '.00'
        with self.assertRaisesRegex(ValueError, 'original font size'): apply_exact(self.data[0], [change], 'en')

    def test_original_bwa_native_amounts(self):
        from finance import plan as bwa_plan, analyze as bwa_analyze
        data = (Path(__file__).parent.parent/'10-10-docs'/'BWA-ganzjaehrig-2025.pdf').read_bytes()
        changes = bwa_plan(data, [{'row':'revenue','column':0,'value':'62.315,78'}])['changes']
        mapped = [{**c, 'page':1, 'box':c['rect'], 'text':c['old'], 'mode':'text'} for c in changes]
        output = apply_exact(data, mapped, 'de')
        self.assertTrue(bwa_analyze(output)['verified'])

    def test_multiple_simultaneous_inputs(self):
        edits = self.edits + [{'id':'d1:c2','value':'40.00'}, {'id':'d3:c2','value':'40.00'}]
        result = apply(self.items, self.signed, edits, self.rules, True, True)
        values = {c['id']:c['new'] for c in result['changes']}
        self.assertEqual(values['d1:c3'], '999,960.00')
        self.assertEqual(values['d3:c3'], '999,960.00')
        with self.assertRaisesRegex(ValueError, 'only once'):
            plan(self.items, self.signed, edits + [edits[0]], self.rules, True)

    def test_demo_reports_balance_and_profit(self):
        from linked_finance import demo
        sample = demo(); signed = analyze(sample['documents'])
        result = apply(sample['documents'], signed, sample['edits'], sample['rules'], True, True)
        values = {c['id']:c['new'] for c in result['changes']}
        self.assertEqual(values['d1:c3'], '920.000,00')
        self.assertEqual(values['d3:c3'], '920.000,00')
        self.assertEqual(values['d2:c1'], values['d2:c2'])
        self.assertEqual(values['d2:c3'], values['d2:c4'])


if __name__ == '__main__': unittest.main()
