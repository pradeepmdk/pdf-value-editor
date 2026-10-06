import io
import json
import os
import unittest
from unittest.mock import patch
from jev_review import review, ROLES, ENDPOINT


class JevTests(unittest.TestCase):
    statement = {'cells': [{'id': 'c1', 'page': 1, 'text': '100,00', 'context': 'Revenue', 'box': [0, 0, 10, 10]}]}

    def response(self, choice='input', confidence=0.9):
        return io.BytesIO(json.dumps({'answers': {'c1': {'type': 'choice', 'choice': choice,
            'confidence': confidence, 'probabilities': {r: float(r == 'input') for r in ROLES}}}}).encode())

    def test_missing_key_no_call(self):
        with patch.dict(os.environ, {}, clear=True), patch('urllib.request.urlopen') as call:
            with self.assertRaises(ValueError): review(self.statement)
            call.assert_not_called()

    def test_valid_advisory_request(self):
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}, clear=True), patch('urllib.request.urlopen', return_value=self.response()) as call:
            result = review(self.statement)
            request = call.call_args.args[0]
            self.assertEqual(request.full_url, ENDPOINT)
            self.assertEqual(json.loads(request.data)['model'], 'typesafe/jev-1.13')
        self.assertTrue(result['advisory_only'])
        self.assertEqual(result['decisions'][0]['role'], 'input')
        self.assertNotIn('rules', result)

    def test_unknown_choice_rejected(self):
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}), patch('urllib.request.urlopen', return_value=self.response('apply')):
            with self.assertRaises(ValueError): review(self.statement)

    def test_bad_confidence_rejected(self):
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}), patch('urllib.request.urlopen', return_value=self.response(confidence=2)):
            with self.assertRaises(ValueError): review(self.statement)

    def test_incomplete_response_rejected(self):
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}), patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"answers": {}}')):
            with self.assertRaises(ValueError): review(self.statement)

    def test_large_statement_no_call(self):
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}), patch('urllib.request.urlopen') as call:
            with self.assertRaises(ValueError): review({'cells': self.statement['cells'] * 151})
            call.assert_not_called()

    def test_label_and_column_sent_with_amount(self):
        import pymupdf
        from general_finance import extract
        doc = pymupdf.open(); page = doc.new_page()
        page.insert_text((300, 80), 'Jan'); page.insert_text((400, 80), 'Feb')
        page.insert_text((50, 120), 'Revenue'); page.insert_text((300, 120), '100,00'); page.insert_text((400, 120), '150,00')
        statement = extract(doc.tobytes(), 'de')
        feb = [c for c in statement['cells'] if c['text'] == '150,00'][0]
        self.assertEqual((feb['label'], feb['column']), ('Revenue', 'Feb'))
        body = io.BytesIO(json.dumps({'answers': {c['id']: {'type': 'choice', 'choice': 'input', 'confidence': .9,
            'probabilities': {r: float(r == 'input') for r in ROLES}} for c in statement['cells']}}).encode())
        with patch.dict(os.environ, {'OPEN_ROUTER_KEY': 'test'}, clear=True), patch('urllib.request.urlopen', return_value=body) as call:
            review(statement)
        sent = json.loads(call.call_args.args[0].data)
        self.assertEqual(sent['state']['cells'][feb['id']]['label'], 'Revenue')
        self.assertEqual(sent['state']['cells'][feb['id']]['column'], 'Feb')
        self.assertIn('Revenue / Feb', sent['questions'][feb['id']]['instructions'])
