import io
import json
import os
import unittest
from unittest.mock import patch
from copy import deepcopy
from jev_dependencies import decide, candidates


class DependencyTests(unittest.TestCase):
    def statement(self):
        rows = [('Revenue', '100.00'), ('Costs', '30.00'), ('Profit', '70.00'), ('Other expense', '10.00'), ('Net profit', '60.00')]
        return {'locale': 'en', 'cells': [{'id': f'c{i+1}', 'page': 1, 'text': amount, 'value': amount,
            'context': label, 'box': [100, i*25, 160, i*25+15], 'suffix': '', 'mode': 'text', 'rotation': 0}
            for i, (label, amount) in enumerate(rows)]}

    def response(self, request, **kwargs):
        payload = json.loads(request.data)
        answers = {}
        formulas = {'c3': {('c1', 1), ('c2', -1)}, 'c5': {('c3', 1), ('c4', -1)}}
        for target, question in payload['questions'].items():
            choice = 'unknown'
            for name, rule in payload['state']['candidates'][target].items():
                if {(t['source'], t['sign']) for t in rule['terms']} == formulas.get(target): choice = name
            answers[target] = {'type': 'choice', 'choice': choice, 'confidence': .9,
                'probabilities': {c: float(c == choice) for c in question['criteria']}}
        return io.BytesIO(json.dumps({'answers': answers}).encode())

    def test_jev_selects_transitive_dependencies_and_decimal_changes(self):
        statement = self.statement(); original = deepcopy(statement)
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}), patch('urllib.request.urlopen', side_effect=self.response):
            result = decide(statement, [{'id': 'c1', 'value': '120.00'}])
        self.assertEqual({r['target'] for r in result['suggestions']}, {'c3', 'c5'})
        self.assertEqual({c['id']: c['new'] for c in result['changes']}, {'c1': '120.00', 'c3': '90.00', 'c5': '80.00'})
        self.assertEqual(statement, original)
        self.assertTrue(result['advisory_only'])

    def test_only_baseline_matching_candidates(self):
        statement = self.statement(); by_id = {c['id']: c for c in statement['cells']}
        from decimal import Decimal
        for target, rules in candidates(statement, 'c1').items():
            for rule in rules or []:
                total = sum((Decimal(by_id[t['source']]['value']) * t['sign'] for t in rule['terms']), Decimal(0))
                self.assertEqual(total, Decimal(by_id[target]['value']))
                self.assertNotIn(target, [t['source'] for t in rule['terms']])

    def test_bad_edit_before_network(self):
        with patch('urllib.request.urlopen') as call:
            for edits in ([], [{'id': 'bad', 'value': '120.00'}], [{'id': 'c1', 'value': '100.00'}]):
                with self.assertRaises(ValueError): decide(self.statement(), edits)
            call.assert_not_called()

    def test_unresolved_does_not_claim_unaffected(self):
        def unknown(request, **kwargs):
            payload = json.loads(request.data)
            return io.BytesIO(json.dumps({'answers': {k: {'type': 'choice', 'choice': 'unknown', 'confidence': 1,
                'probabilities': {c: float(c == 'unknown') for c in q['criteria']}} for k, q in payload['questions'].items()}}).encode())
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}), patch('urllib.request.urlopen', side_effect=unknown):
            result = decide(self.statement(), [{'id': 'c1', 'value': '120.00'}])
        self.assertEqual(result['suggestions'], [])
        self.assertEqual(len(result['changes']), 1)
        self.assertTrue(result['unresolved'])

    def test_invalid_choice_rejected(self):
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}), patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"answers": {}}')):
            with self.assertRaises(ValueError): decide(self.statement(), [{'id': 'c1', 'value': '120.00'}])

    def test_cross_page_relationship_not_invented(self):
        statement = self.statement(); statement['cells'][2]['page'] = 2
        self.assertEqual(candidates(statement, 'c1')['c3'], [])
