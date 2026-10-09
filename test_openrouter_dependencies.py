import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from finance_workflow import analyze, plan
from general_finance import validate_analysis
from openrouter_dependencies import decide


class GPTDependenciesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = (Path(__file__).parent.parent / 'BWA-ganzjaehrig-2025.pdf').read_bytes()
        cls.source = validate_analysis(cls.data, analyze(cls.data))

    def response(self, request, **kwargs):
        payload = json.loads(request.data)
        self.assertEqual(payload['model'], 'openai/gpt-4.1')
        state = json.loads(payload['messages'][1]['content'])
        self.assertEqual(len(state['edits']), 2)
        rules = [{**r, 'reason': 'Monthly subtotal and annual relationship'} for r in state['source_validated_relationships']]
        content = json.dumps({'rules': rules, 'unresolved': [], 'summary': 'Revenue and payroll inputs affect their own totals and result.'})
        return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}).encode())

    def edits(self):
        return [{'id': 'revenue_0', 'value': '12.315,78'}, {'id': 'staff_0', 'value': '20.000,00'}]

    def test_multiple_inputs_update_real_costs_and_results(self):
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}), patch('urllib.request.urlopen', side_effect=self.response):
            result = decide(self.source, self.edits())
        actual = plan(self.data, self.source, self.edits(), result['suggestions'])
        changed = {c['id'] for c in actual['changes']}
        self.assertTrue({'staff_0', 'staff_12', 'total_costs_0', 'total_costs_12', 'final_0', 'final_12'} <= changed)
        self.assertNotIn('rent_0', changed)

    def test_missing_bwa_formula_is_rejected(self):
        def incomplete(request, **kwargs):
            answer = json.loads(self.response(request).read())
            value = json.loads(answer['choices'][0]['message']['content'])
            value['rules'] = value['rules'][:-1]
            answer['choices'][0]['message']['content'] = json.dumps(value)
            return io.BytesIO(json.dumps(answer).encode())
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}), patch('urllib.request.urlopen', side_effect=incomplete):
            with self.assertRaisesRegex(ValueError, 'Incomplete verified BWA'):
                decide(self.source, self.edits())

    def test_derived_input_is_rejected_without_api_call(self):
        with patch('urllib.request.urlopen') as call:
            with self.assertRaisesRegex(ValueError, 'independent'):
                decide(self.source, [{'id': 'final_0', 'value': '0,00'}])
            call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
