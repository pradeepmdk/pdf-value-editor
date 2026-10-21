from copy import deepcopy
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from expense_forecast import preview, export, cost_groups, validate_classifications, _annual_edits
from finance_workflow import analyze
from general_finance import validate_analysis, parse_amount
import pymupdf

ROOT=Path(__file__).resolve().parent.parent


def response(request, **kwargs):
    payload=json.loads(request.data)
    assert payload['model']=='openai/gpt-4.1'
    assert 'pdf' not in json.loads(payload['messages'][1]['content'])
    state=json.loads(payload['messages'][1]['content'])
    schema=payload['response_format']['json_schema']['schema']['properties']['costs']
    assert schema['type']=='object'
    assert schema['required']==list(state['cost_rows'])
    assert set(schema['properties'])==set(state['cost_rows'])
    assert schema['additionalProperties'] is False
    costs=[{'row':row,'category':'variable','decrease_percent':'30','increase_percent':'100','elasticity':'1',
            'reason':'Proposed planning assumption from the printed row label; contracts are not available.',
            'evidence_ids':[items[0]['id']]} for row,items in state['cost_rows'].items()]
    body={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'costs':costs,'summary':'Conservative planning assumptions for review.'})}}]}
    return io.BytesIO(json.dumps(body).encode())


class BoundedForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cash_data=(ROOT/'10-10-docs/10257_BWA_2024-12_261009_205509.pdf').read_bytes()
        cls.cash=validate_analysis(cls.cash_data,analyze(cls.cash_data))
        cls.annual_data=(ROOT/'10-10-docs/BWA-ganzjaehrig-2025.pdf').read_bytes()
        cls.annual=validate_analysis(cls.annual_data,analyze(cls.annual_data))

    def run_preview(self,data,source,edits):
        with patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=response):
            return preview(data,source,edits)

    def test_phone_model_cannot_bypass_ten_percent_ceiling(self):
        c={'id':'phone','label':'6805 Telefon','context':'Telephone'}
        result=validate_classifications({'6805':[c]}, {'summary':'Planning', 'costs':[{'row':'6805','category':'variable',
            'decrease_percent':'100','increase_percent':'900','elasticity':'100','reason':'Label', 'evidence_ids':['phone']}]})
        self.assertEqual(result['6805']['category'],'limited')
        self.assertEqual(result['6805']['increase'],'10')
        self.assertEqual(result['6805']['decrease'],'10')
        self.assertEqual(result['6805']['elasticity'],'0.25')

    def test_july_template_recovers_invalid_ai_row_then_exports(self):
        data=(ROOT/'10-10-docs/10257_BWA_2026-07_261009_205545.pdf').read_bytes()
        source=validate_analysis(data,analyze(data))
        calls=[]
        def malformed_then_correct(request,**kwargs):
            calls.append(json.loads(request.data))
            valid=response(request,**kwargs)
            if len(calls)>1:return valid
            body=json.load(valid)
            generated=json.loads(body['choices'][0]['message']['content'])
            generated['costs'][0]['row']='Material-/Wareneinkauf'
            body['choices'][0]['message']['content']=json.dumps(generated)
            return io.BytesIO(json.dumps(body).encode())
        with patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=malformed_then_correct):
            result=preview(data,source,[{'id':'c1','value':'12.000,00'}])
        self.assertEqual(len(calls),2)
        self.assertIn('Validation failed',calls[1]['messages'][-1]['content'])
        output,_=export(data,source,result['forecast'],reviewed=True)
        saved=validate_analysis(output,analyze(output))
        self.assertTrue(saved['verified'],saved['discrepancies'])
        self.assertEqual(saved['pages'],8)

    def test_repeated_duplicate_ai_rows_still_rejected(self):
        def duplicate(request,**kwargs):
            body=json.load(response(request,**kwargs))
            generated=json.loads(body['choices'][0]['message']['content'])
            generated['costs'][1]['row']=generated['costs'][0]['row']
            body['choices'][0]['message']['content']=json.dumps(generated)
            return io.BytesIO(json.dumps(body).encode())
        with patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=duplicate) as network:
            with self.assertRaisesRegex(ValueError,'duplicated'):
                preview(self.cash_data,self.cash,[{'id':'c1','value':'3.000,00'}])
        self.assertEqual(network.call_count,2)

    def test_keyed_classification_binds_exact_source_rows(self):
        groups={'phone':[{'id':'p','label':'Telefon','context':'Telephone'}]}
        item={'category':'limited','decrease_percent':'10','increase_percent':'10',
              'elasticity':'.1','reason':'Label','evidence_ids':['p']}
        result=validate_classifications(groups,{'summary':'Planning','costs':{'phone':item}})
        self.assertEqual(result['phone']['category'],'limited')
        with self.assertRaisesRegex(ValueError,'missing cost row'):
            validate_classifications(groups,{'summary':'Planning','costs':{'invented':item}})

    def test_huge_revenue_cannot_inflate_fixed_costs(self):
        result=self.run_preview(self.cash_data,self.cash,[{'id':'c1','value':'1.000.000,00'}])
        for v in result['limits']:
            before=parse_amount(v['before'],'de')[0];after=parse_amount(v['after'],'de')[0]
            if v['category']=='fixed' or before<=0:self.assertEqual(before,after)
            elif before>0:self.assertLessEqual(after,before*(1+Decimal(v['increase'])/100)+Decimal('.01'))
        self.assertNotIn('Raumkosten / Month',{c['context'] for c in result['changes']})

    def test_income_change_alone_does_not_invent_expense_changes(self):
        result=self.run_preview(self.cash_data,self.cash,[{'id':'c1','value':'1.000.000,00'}])
        self.assertTrue(result['limits'])
        for item in result['limits']:
            self.assertEqual(item['before'],item['after'])
            self.assertIn('Unchanged',item['adjustment_basis'])
        self.assertFalse(result['forecast']['proposal']['assume_volume'])

    def test_volume_scenario_only_proposes_variable_costs_and_reports_caps(self):
        with patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=response):
            result=preview(self.cash_data,self.cash,[{'id':'c3','value':'1.000.000,00'}],assume_volume=True)
        changed=[v for v in result['limits'] if v['before']!=v['after']]
        self.assertTrue(changed)
        self.assertTrue(all(v['category']=='variable' for v in changed))
        self.assertTrue(any(v['capped'] for v in changed))
        for v in result['limits']:
            if v['category'] in ('fixed','staff','limited','unknown'):self.assertEqual(v['before'],v['after'])
        self.assertTrue(result['forecast']['proposal']['assume_volume'])

    def test_explicit_expense_correction_is_not_blocked_by_planning_caps(self):
        c=next(c for c in self.cash['cells'] if c.get('row')=='raumkosten' and c.get('column_index')==0 and c['editable'])
        result=self.run_preview(self.cash_data,self.cash,[{'id':c['id'],'value':'100.000,00'}])
        self.assertEqual(next(v['new'] for v in result['changes'] if v['id']==c['id']),'100.000,00')
        self.assertIn('explicit expense correction',next(v['adjustment_basis'] for v in result['limits'] if v['id']==c['id']))

    def test_annual_income_spreads_to_months_with_exact_cents(self):
        edits=_annual_edits(self.annual,[{'id':'revenue_12','value':'100.000,01'}])
        values={c['id']:Decimal(c['value']) for c in self.annual['cells']}
        for e in edits:values[e['id']]=parse_amount(e['value'],'de')[0]
        self.assertEqual(sum(values[f'revenue_{i}'] for i in range(12)),Decimal('100000.01'))
        with self.assertRaisesRegex(ValueError,'not both'):
            _annual_edits(self.annual,[{'id':'revenue_12','value':'100.000,01'},{'id':'revenue_0','value':'100,00'}])

    def test_annual_preview_and_saved_totals(self):
        result=self.run_preview(self.annual_data,self.annual,[{'id':'revenue_12','value':'100.000,00'}])
        output,calculated=export(self.annual_data,self.annual,result['forecast'],reviewed=True)
        saved=validate_analysis(output,analyze(output))
        self.assertEqual(next(c['text'] for c in saved['cells'] if c['id']=='revenue_12'),'100.000,00')
        self.assertTrue(calculated['simulation'])
        with pymupdf.open(stream=output,filetype='pdf') as doc,pymupdf.open(stream=self.annual_data,filetype='pdf') as original:
            self.assertNotIn('PLANNING SIMULATION',doc[0].get_text());self.assertEqual(doc.metadata,original.metadata)

    def test_review_and_signature_required_no_repeated_model_call(self):
        result=self.run_preview(self.cash_data,self.cash,[{'id':'c1','value':'3.000,00'}])
        with self.assertRaisesRegex(ValueError,'Review'):
            export(self.cash_data,self.cash,result['forecast'])
        forged=deepcopy(result['forecast']);forged['proposal']['edits'][0]['value']='999.999,00'
        with self.assertRaisesRegex(ValueError,'invalid'):
            export(self.cash_data,self.cash,forged,reviewed=True)
        with patch('urllib.request.urlopen') as network:
            output,_=export(self.cash_data,self.cash,result['forecast'],reviewed=True)
            self.assertTrue(output);network.assert_not_called()

    def test_ai_incomplete_or_invented_evidence_is_rejected(self):
        groups={'phone':[{'id':'p','label':'Telefon','context':'Telephone'}]}
        with self.assertRaisesRegex(ValueError,'coverage'):
            validate_classifications(groups,{'summary':'Planning','costs':[]})
        with self.assertRaisesRegex(ValueError,'evidence'):
            validate_classifications(groups,{'summary':'Planning','costs':[{'row':'phone','category':'limited',
                'decrease_percent':'10','increase_percent':'10','elasticity':'.1','reason':'Label','evidence_ids':['invented']}]})

    def test_source_discrepancy_rejected_before_ai_request(self):
        source=deepcopy(self.cash);source['verified']=False
        with patch('urllib.request.urlopen') as network,self.assertRaisesRegex(ValueError,'discrepancies'):
            preview(self.cash_data,source,[{'id':'c1','value':'3.000,00'}])
        network.assert_not_called()


class SuSaForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=(ROOT/'AB Service GmbH, SuSa per 042026_260927_211659.pdf').read_bytes()
        cls.source=validate_analysis(cls.data,analyze(cls.data))

    def test_explicit_telephone_correction_still_requires_balanced_bookings(self):
        phone=next(c for c in self.source['cells'] if c['row']=='6805' and c['column_index']==3)
        with patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=response),self.assertRaisesRegex(ValueError,'counterpart'):
            preview(self.data,self.source,[{'id':phone['id'],'value':'1.000.000,00'}])

    def test_ai_does_not_invent_susa_counterpart_bookings(self):
        bank=next(c for c in self.source['cells'] if c['row']=='1805' and c['column_index']==1)
        with patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=response),self.assertRaisesRegex(ValueError,'counterpart'):
            preview(self.data,self.source,[{'id':bank['id'],'value':'100.000,00'}])

    def test_balanced_scan_export_keeps_ocr_and_original_orientation(self):
        def movement(row,col):return next(c for c in self.source['cells'] if c['row']==row and c['column_index']==col)
        bank=movement('1805',1);cash=movement('1600',2)
        from general_finance import format_amount
        edits=[{'id':c['id'],'value':format_amount(Decimal(c['value'])+1000,'de')} for c in (bank,cash)]
        with patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=response):
            result=preview(self.data,self.source,edits)
        output,_=export(self.data,self.source,result['forecast'],reviewed=True,allow_raster=True)
        with pymupdf.open(stream=output,filetype='pdf') as after,pymupdf.open(stream=self.data,filetype='pdf') as before:
            for a,b in zip(before,after):
                self.assertEqual(a.rotation,b.rotation);self.assertEqual(a.rect,b.rect)
                self.assertEqual(a.get_text(),b.get_text())
                self.assertEqual(a.get_images()[0][2:4],b.get_images()[0][2:4])
            self.assertEqual(after.metadata,before.metadata)
            self.assertTrue(after[1].get_pixmap().samples)


if __name__=='__main__':unittest.main()
