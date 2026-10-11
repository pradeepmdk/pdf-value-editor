import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import os
import pymupdf
from finance_workflow import analyze, plan, apply
from general_finance import validate_analysis
from jev_dependencies import decide, candidates


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = (Path(__file__).resolve().parent.parent / '10-10-docs' / 'BWA-ganzjaehrig-2025.pdf').read_bytes()

    def source(self):
        return validate_analysis(self.data, analyze(self.data))

    def test_signed_intake_preserves_all_fields(self):
        source = self.source()
        self.assertEqual(len(source['cells']), 416)
        self.assertEqual(source['export_mode'], 'direct')
        self.assertFalse(source['automatic_rules'])
        revenue = next(c for c in source['cells'] if c['id']=='revenue_0')
        self.assertEqual(revenue['column'], 'Jan/2025')
        self.assertEqual(revenue['column_index'], 0)
        annual = next(c for c in source['cells'] if c['id']=='revenue_12')
        self.assertEqual(annual['column'], 'Annual total')

    def test_no_reviewed_rules_explains_required_step(self):
        with self.assertRaisesRegex(ValueError, 'Accept reviewed dependencies'):
            plan(self.data, self.source(), [{'id':'revenue_0','value':'62.315,78'}], [])

    def test_browser_number_round_trip_keeps_signature_valid(self):
        signed = analyze(self.data)
        def browser_json(value):
            if isinstance(value, dict): return {k: browser_json(v) for k, v in value.items()}
            if isinstance(value, list): return [browser_json(v) for v in value]
            if isinstance(value, float) and value.is_integer(): return int(value)
            return value
        signed = browser_json(signed)
        self.assertEqual(len(validate_analysis(self.data, signed)['cells']), 416)
        signed['analysis']['statement']['cells'][0]['box'][0] += 1
        with self.assertRaises(ValueError): validate_analysis(self.data, signed)

    def test_restart_invalidates_analysis_for_safe_client_refresh(self):
        signed = analyze(self.data)
        with patch('scan_editor._secret', b'a different server session'):
            with self.assertRaisesRegex(ValueError, 'expired'): validate_analysis(self.data, signed)
            fresh = analyze(self.data)
            self.assertEqual(len(validate_analysis(self.data, fresh)['cells']), 416)

    def test_jev_decisions_cover_monthly_and_annual_fields(self):
        def answer(request, **kwargs):
            payload = json.loads(request.data)
            self.assertLess(len(payload['state']['cells']), 150)
            return io.BytesIO(json.dumps({'answers': {key: {'type': 'choice', 'choice': 'f0', 'confidence': .9,
                'probabilities': {'f0': 1, 'unknown': 0}} for key in payload['questions']}}).encode())
        source = self.source(); edits = [{'id': 'revenue_0', 'value': '42.315,78'}]
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}), patch('urllib.request.urlopen', side_effect=answer):
            selected = decide(source, edits)
        self.assertEqual(selected['model'], 'typesafe/jev-1.13')
        self.assertTrue(selected['decisions'])
        targets = {r['target'] for r in selected['suggestions']}
        self.assertIn('final_0', targets)
        self.assertIn('final_12', targets)
        result = plan(self.data, source, edits, selected['suggestions'])
        self.assertEqual(len(result['changes']), 14)
        output, _ = apply(self.data, source, edits, selected['suggestions'])
        from finance import analyze as verify
        self.assertTrue(verify(output)['verified'])
        with pymupdf.open(stream=self.data, filetype='pdf') as original, pymupdf.open(stream=output, filetype='pdf') as saved:
            self.assertEqual(original[0].rect, saved[0].rect)
            self.assertFalse(saved[0].get_images())

    def test_missing_annual_dependency_blocks_export(self):
        source = self.source(); edits = [{'id': 'revenue_0', 'value': '42.315,78'}]
        rules = [options[0] for options in candidates(source, 'revenue_0').values()]
        rules = [r for r in rules if r['target'] != 'final_12']
        with self.assertRaisesRegex(ValueError, 'complete affected'):
            apply(self.data, source, edits, rules)

    def test_derived_input_rejected_before_model_call(self):
        with patch('urllib.request.urlopen') as call:
            with self.assertRaises(ValueError): decide(self.source(), [{'id': 'final_0', 'value': '100,00'}])
            call.assert_not_called()

    def test_generic_source_uses_same_signed_workflow(self):
        with pymupdf.open() as doc:
            doc.new_page().insert_text((50, 50), 'Sales 100.00')
            data = doc.tobytes()
        source = validate_analysis(data, analyze(data, 'en'))
        self.assertEqual(source['export_mode'], 'image')
        self.assertEqual(len(source['cells']), 1)
        with self.assertRaises(ValueError): apply(data, source, [{'id': 'c1', 'value': '120.00'}], [])
