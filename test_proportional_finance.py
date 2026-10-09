from pathlib import Path
import unittest
import pymupdf
from finance import analyze as verify
from finance_workflow import analyze
from general_finance import validate_analysis
from proportional_finance import scenario


class ProportionalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = (Path(__file__).resolve().parent.parent / 'BWA-ganzjaehrig-2025.pdf').read_bytes()
        cls.source = validate_analysis(cls.data, analyze(cls.data))

    def test_income_halved_scales_costs_and_keeps_other_months(self):
        result = scenario(self.data, self.source, [{'id': 'revenue_0', 'value': '26.157,89'}])
        changes = {c['id']: c['new'] for c in result['changes']}
        self.assertEqual(changes['staff_0'], '13.559,95')
        self.assertEqual(changes['rent_0'], '834,04')
        self.assertNotIn('staff_1', changes)
        self.assertNotIn('special_0', changes)
        self.assertIn('total_costs_12', changes)
        self.assertIn('final_12', changes)

    def test_expense_doubled_scales_income_and_export_is_labelled(self):
        output, result = scenario(self.data, self.source, [{'id': 'staff_0', 'value': '54.239,80'}], export=True)
        changes = {c['id']: c['new'] for c in result['changes']}
        self.assertEqual(changes['revenue_0'], '104.631,56')
        self.assertEqual(changes['rent_0'], '3.336,14')
        self.assertTrue(verify(output)['verified'])
        with pymupdf.open(stream=output, filetype='pdf') as doc:
            self.assertIn('SIMULATION', doc[0].get_text())
        from change_preview import previews
        self.assertTrue(previews(self.data, output, result['changes'])['after'])

    def test_zero_baseline_and_conflicting_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError, 'zero baseline'):
            scenario(self.data, self.source, [{'id': 'special_0', 'value': '100,00'}])
        with self.assertRaisesRegex(ValueError, 'one driving amount'):
            scenario(self.data, self.source, [{'id': 'revenue_0', 'value': '26.157,89'}, {'id': 'staff_0', 'value': '54.239,80'}])


if __name__ == '__main__':
    unittest.main()
