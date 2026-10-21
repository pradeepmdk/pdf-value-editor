import io
import json
import os
from pathlib import Path
from decimal import Decimal
import unittest
from unittest.mock import patch

from document_summary import facts,summarize
from finance_workflow import analyze
from general_finance import validate_analysis,parse_amount

ROOT=Path(__file__).resolve().parent.parent


class DocumentSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cash=validate_analysis((ROOT/'10-10-docs/10257_BWA_2024-12_261009_205509.pdf').read_bytes(),analyze((ROOT/'10-10-docs/10257_BWA_2024-12_261009_205509.pdf').read_bytes()))
        data=(ROOT/'10-10-docs/BWA-ganzjaehrig-2025.pdf').read_bytes();cls.annual=validate_analysis(data,analyze(data))

    def response(self,request,**kwargs):
        payload=json.loads(request.data);self.assertEqual(payload['model'],'openai/gpt-4.1')
        state=json.loads(payload['messages'][1]['content']);self.assertNotIn('pdf',state)
        self.assertEqual(len(state['fields']),len(self.cash['cells']))
        self.assertIn(self.language,payload['messages'][0]['content'])
        summary={'title':'Document summary','overview':'Cash-basis income and expenses, separated by reporting period.',
            'highlights':['Source totals were checked.'],'cautions':['Year to date is not automatically a full year.'],
            'cost_labels':[{'key':key,'label':'Translated '+label} for key,label in state['cost_labels_to_translate'].items()],
            'periods':[{'id':p['id'],'label':'Period '+p['id'],'kind':'year_to_date' if p['kind']=='ytd' else 'month'} for p in state['facts']['periods']]}
        return io.BytesIO(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(summary)}}]}).encode())

    def test_cash_source_values_periods_and_expense_breakdown(self):
        result=facts(self.cash);self.assertEqual([p['kind'] for p in result['periods']],['ytd','month'])
        annual=result['periods'][0];metrics={v['key']:v for v in annual['metrics']}
        self.assertEqual(metrics['result']['amount'],'-34.873,94')
        self.assertEqual(metrics['income']['amount'],'41.623,64')
        self.assertEqual(len(annual['costs']),11)
        self.assertTrue(result['source_verified'])

    def test_annual_computed_income_less_expenses_matches_printed_final(self):
        result=facts(self.annual);self.assertEqual(len(result['periods']),13)
        self.assertEqual(result['periods'][0]['kind'],'annual')
        for period in result['periods']:
            metrics={v['key']:v for v in period['metrics']}
            self.assertEqual(parse_amount(metrics['income']['amount'],'de')[0]-parse_amount(metrics['expenses']['amount'],'de')[0],parse_amount(metrics['result']['amount'],'de')[0])
            self.assertTrue(period['costs'])

    def test_english_and_german_prompt_keep_exact_amounts(self):
        for locale,name in [('en','English'),('de','German')]:
            self.language=name
            with self.subTest(locale=locale),patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=self.response):
                result=summarize(self.cash,locale)
            self.assertEqual(result['facts'],facts(self.cash));self.assertEqual(result['language'],locale)

    def test_unknown_language_rejected_before_network(self):
        with patch('urllib.request.urlopen') as network,self.assertRaises(ValueError):summarize(self.cash,'fr')
        network.assert_not_called()

    def test_invented_translation_key_is_rejected(self):
        self.language='English'
        def invalid(request,**kwargs):
            value=json.loads(self.response(request).read());summary=json.loads(value['choices'][0]['message']['content']);summary['cost_labels'][0]['key']='invented';value['choices'][0]['message']['content']=json.dumps(summary)
            return io.BytesIO(json.dumps(value).encode())
        with patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=invalid),self.assertRaisesRegex(ValueError,'invented'):
            summarize(self.cash)

    def test_ai_period_labels_are_returned_and_invented_periods_rejected(self):
        self.language='German'
        with patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=self.response):
            result=summarize(self.cash,'de')
        self.assertEqual({p['id']:p['label'] for p in result['summary']['periods']},{'4':'Period 4','0':'Period 0'})
        def invented(request,**kwargs):
            value=json.loads(self.response(request).read());summary=json.loads(value['choices'][0]['message']['content'])
            summary['periods'].append({'id':'99','label':'Q3 2031','kind':'quarter'});value['choices'][0]['message']['content']=json.dumps(summary)
            return io.BytesIO(json.dumps(value).encode())
        with patch.dict(os.environ,{'OPEN_ROUTER_KEY':'test'}),patch('urllib.request.urlopen',side_effect=invented),self.assertRaisesRegex(ValueError,'Periods'):
            summarize(self.cash,'de')

    def test_buhl_overview_lists_editable_accounts_per_period(self):
        data=(ROOT/'57 BWA Amaron Management 7-2025_261008_193942.pdf').read_bytes()
        result=facts(validate_analysis(data,analyze(data)))
        self.assertEqual([(p['id'],p['kind']) for p in result['periods']],[('0','month'),('3','ytd')])
        month=result['periods'][0];metrics={v['key']:v for v in month['metrics']}
        self.assertEqual(metrics['income']['amount'],'115.958,09')
        self.assertEqual(metrics['result']['amount'],'14.839,62')
        self.assertEqual(metrics['revenue_8125steuerfrinnergemlief4abs1bustg']['amount'],'26.825,00')
        self.assertEqual(len(month['costs']),26)

    def test_susa_movements_exclude_opening_and_bank_balances(self):
        source={'profile':'addison_susa','report_type':'SuSa','pages':1,'locale':'de','verified':True,'cells':[]}
        for row,amounts in [('4400',['0','200','0','500']),('6805',['100','0','250','0']),('1800',['99999','99999','99999','99999'])]:
            for column,value in enumerate(amounts,1):source['cells'].append({'id':f'{row}_{column}','page':1,'row':row,'column_index':column,'value':value,'label':row})
        result=facts(source);self.assertTrue(result['susa_computed'])
        metrics={v['key']:v['amount'] for v in result['periods'][0]['metrics']}
        self.assertEqual(metrics,{'income':'500,00','expenses':'250,00','result':'250,00'})


if __name__=='__main__':unittest.main()
