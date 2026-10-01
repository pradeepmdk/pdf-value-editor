import io
import json
import os
import unittest
from unittest.mock import patch
from ai_rules import suggest


class AIRulesTests(unittest.TestCase):
    statement={'locale':'en','cells':[{'id':key,'page':1,'text':value,'value':value,'context':label,'box':[0,0,100,20],'suffix':''} for key,label,value in [('c1','Revenue','100.00'),('c2','Costs','30.00'),('c3','Profit','70.00')]]}
    valid={'target':'c3','terms':[{'source':'c1','sign':1},{'source':'c2','sign':-1}],'reason':'Profit is revenue minus costs.'}

    def mock_response(self,rules):
        return io.BytesIO(json.dumps({'message':{'content':json.dumps({'rules':rules,'uncertainties':[]})}}).encode())

    def test_no_model_call_before_approval(self):
        with patch.dict(os.environ,{'PDF_EDITOR_AI_APPROVED':'0','PDF_EDITOR_OLLAMA_MODEL':'test'}),patch('urllib.request.urlopen') as call:
            with self.assertRaises(ValueError):suggest(self.statement)
            call.assert_not_called()

    def test_valid_rules_are_only_suggestions(self):
        with patch.dict(os.environ,{'PDF_EDITOR_AI_APPROVED':'1','PDF_EDITOR_OLLAMA_MODEL':'test'}),patch('urllib.request.urlopen',return_value=self.mock_response([self.valid])):
            result=suggest(self.statement)
        self.assertEqual(len(result['suggestions']),1)
        self.assertTrue(result['advisory_only'])

    def test_wrong_arithmetic_is_rejected(self):
        wrong={'target':'c3','terms':[{'source':'c1','sign':1}],'reason':'Unsupported guess'}
        with patch.dict(os.environ,{'PDF_EDITOR_AI_APPROVED':'1','PDF_EDITOR_OLLAMA_MODEL':'test'}),patch('urllib.request.urlopen',return_value=self.mock_response([wrong])):
            result=suggest(self.statement)
        self.assertFalse(result['suggestions'])
        self.assertEqual(len(result['rejected']),1)

    def test_circular_relationships_are_rejected(self):
        reverse={'target':'c2','terms':[{'source':'c1','sign':1},{'source':'c3','sign':-1}],'reason':'Circular guess'}
        with patch.dict(os.environ,{'PDF_EDITOR_AI_APPROVED':'1','PDF_EDITOR_OLLAMA_MODEL':'test'}),patch('urllib.request.urlopen',return_value=self.mock_response([self.valid,reverse])):
            result=suggest(self.statement)
        self.assertFalse(result['suggestions'])


if __name__=='__main__':unittest.main()
