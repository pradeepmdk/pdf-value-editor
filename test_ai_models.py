import io
import json
import os
import time
import unittest
from unittest.mock import patch
from ai_models import selected_model, select_model, reset_model, model_payload, DEFAULT_MODEL
from analysis_jobs import start, poll
from expense_forecast import classify


class ModelSelectionTests(unittest.TestCase):
    def test_selection_is_captured_per_background_job(self):
        jobs=[]
        for model in ('openai/gpt-6-astra','google/gemini-4-argon'):
            token=select_model(model)
            try:jobs.append((model,start(selected_model)))
            finally:reset_model(token)
        for model,job in jobs:
            deadline=time.monotonic()+5
            while (result:=poll(job['job']))['state']!='complete':
                self.assertLess(time.monotonic(),deadline);time.sleep(.01)
            self.assertEqual(result['result'],model)
        self.assertEqual(selected_model(),DEFAULT_MODEL)

    def test_invalid_model_cannot_change_context(self):
        with self.assertRaises(ValueError):select_model('invented/model')
        self.assertEqual(selected_model(),DEFAULT_MODEL)

    def test_both_providers_reach_forecast_payload_and_retry(self):
        groups={'phone':[{'id':'p','page':1,'text':'10,00','label':'Telephone','context':'Telephone','box':[0,0,1,1],'value':'10'}]}
        for model in ('openai/gpt-6-astra','google/gemini-4-argon'):
            calls=[]
            def response(request,**kwargs):
                payload=json.loads(request.data);calls.append(payload)
                self.assertEqual(payload['model'],model)
                self.assertEqual('temperature' in payload,model.startswith('google/'))
                cost={'category':'limited','decrease_percent':'10','increase_percent':'10','elasticity':'.1','reason':'Telephone label','evidence_ids':['p']}
                costs={'phone':cost} if len(calls)>1 else {}
                return io.BytesIO(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'summary':'Planning','costs':costs})}}]}).encode())
            token=select_model(model)
            try:
                with patch.dict(os.environ,{'OPENROUTER_API_KEY':'test'}),patch('urllib.request.urlopen',side_effect=response):
                    result,_=classify({'locale':'de','cells':groups['phone']},[],groups)
                self.assertEqual(result['phone']['increase'],'10');self.assertEqual(len(calls),2)
            finally:reset_model(token)

    def test_default_payload_unchanged(self):
        self.assertEqual(model_payload({'temperature':0})['model'],DEFAULT_MODEL)
        self.assertEqual(model_payload({'temperature':0})['temperature'],0)
