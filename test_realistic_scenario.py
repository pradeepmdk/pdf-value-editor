import json
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

import pymupdf

from finance_workflow import analyze
from general_finance import validate_analysis, parse_amount
import realistic_scenario as rs

ROOT=Path(__file__).resolve().parent.parent
SOURCES=['https://www.destatis.de/cpi','https://www.destatis.de/wages','https://www.bundesnetzagentur.de/energy']


def research_message():
    return {'content':'CPI rose 2.2 %, nominal wages 4.2 %, energy -3.4 %.',
            'annotations':[{'type':'url_citation','url_citation':{'url':u+'?utm_source=openai','title':'Source '+str(i)}} for i,u in enumerate(SOURCES,1)]}


def extraction(invented=False):
    items=[{'id':'cpi','name':'Inflation','change_percent':'2.2','period':'2025','source':1},
           {'id':'wages','name':'Nominal wages','change_percent':'4.2','period':'2025','source':2},
           {'id':'energy','name':'Energy','change_percent':'-3.4','period':'2025','source':3}]
    if invented:items.append({'id':'made_up','name':'Invented','change_percent':'9','period':'2025','source':9})
    return {'content':json.dumps({'document_year':'2025','region':'Germany','industry':'Trade','indicators':items})}


class RealisticScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=(ROOT/'57 BWA Amaron Management 7-2025_261008_193942.pdf').read_bytes()
        cls.source=validate_analysis(cls.data,analyze(cls.data))
        cls.cells={c['id']:c for c in cls.source['cells']}
        cls.month={c['label'][:4]:c for c in cls.source['cells'] if c.get('editable') and c['column_index']==0}

    def proposal(self,payload):
        state=json.loads(payload['messages'][1]['content'])
        accounts={}
        for a in state['accounts']:
            code=a['label'][:4]
            if code.startswith('8'):accounts[a['id']]={'revenue':True,'driver':'none','indicators':[],'reason':'Other revenue unchanged.'}
            elif code in ('3400','3106'):accounts[a['id']]={'revenue':False,'driver':'sales','indicators':[],'reason':'Moves with sales.'}
            elif code=='4100':accounts[a['id']]={'revenue':False,'driver':'indicator','indicators':['wages'],'reason':'Wage growth.'}
            elif code=='4240':accounts[a['id']]={'revenue':False,'driver':'indicator','indicators':['energy','cpi'],'reason':'Energy and CPI.'}
            else:accounts[a['id']]={'revenue':False,'driver':'none','indicators':[],'reason':'No driver.'}
        return {'content':json.dumps({'user_changes':{u['id']:{'revenue':True} for u in state['user_changes']},
                                      'accounts':accounts,'summary':'Planning scenario.'})}

    def run_scenario(self,invented=False):
        calls=[]
        def fake(payload,timeout=180):
            calls.append(payload)
            if len(calls)==1:return research_message()
            if len(calls)==2:return extraction(invented)
            return self.proposal(payload)
        edit={'id':self.month['8125']['id'],'value':'32.190,00'}
        with patch.dict('os.environ',{'OPENROUTER_API_KEY':'test'}),patch.object(rs,'_call',side_effect=fake):
            return rs.preview(self.data,self.source,[edit],'en'),calls

    def test_only_web_search_sources_are_kept(self):
        result,calls=self.run_scenario(invented=True)
        self.assertEqual(calls[0]['plugins'],[{'id':'web','max_results':8}])
        self.assertNotIn('plugins',calls[1])
        self.assertEqual([v['source_url'] for v in result['research']['indicators']],SOURCES)
        # The extraction step may only point at numbered search citations.
        self.assertEqual(calls[1]['response_format']['json_schema']['schema']['properties']['indicators']['items']['properties']['source']['enum'],[1,2,3])

    def test_exact_prompts_are_returned_for_display(self):
        result,calls=self.run_scenario()
        shown=result['prompts']
        self.assertEqual([p['file'] for p in shown],['prompts/scenario_research.txt','prompts/scenario_extract.txt','prompts/scenario_drivers.txt'])
        self.assertEqual([p['web_search'] for p in shown],[True,False,False])
        for p,call in zip(shown,calls):
            self.assertEqual([p['system'],p['user']],[m['content'] for m in call['messages']])
        self.assertEqual(shown[0]['response'],research_message()['content'])

    def test_python_calculates_sales_and_indicator_changes(self):
        result,_=self.run_scenario()
        rows={r['context'][:4]:r for r in result['accounts']}
        revenue=[c for c in self.month.values() if c['label'].startswith('8')]
        old=sum(Decimal(c['value']) for c in revenue)
        expected=((old+Decimal('32190.00')-Decimal('26825.00'))/old-1)*100
        self.assertEqual(rows['3400']['change_percent'],str(expected.quantize(Decimal('.01'))))
        self.assertEqual(rows['4100']['change_percent'],'4.20')
        self.assertEqual(rows['4240']['change_percent'],'-0.60')
        self.assertEqual(rows['4830']['change_percent'],'0.00')
        wage=self.month['4100']
        self.assertEqual(parse_amount(rows['4100']['after'],'de')[0],(Decimal(wage['value'])*Decimal('1.042')).quantize(Decimal('.01')))

    def test_year_to_date_follows_month_and_totals_recalculate(self):
        result,_=self.run_scenario()
        ids={r['id'] for r in result['accounts']}
        self.assertTrue(all(self.cells[i]['column_index']==0 for i in ids))
        changed={c['id']:c for c in result['changes']}
        wage=self.month['4100'];year=next(a for m,a in self.source['period_pairs'] if m==wage['id'])
        delta=parse_amount(changed[wage['id']]['new'],'de')[0]-Decimal(wage['value'])
        self.assertEqual(parse_amount(changed[year]['new'],'de')[0],Decimal(self.cells[year]['value'])+delta)
        self.assertTrue(any(c['reason']=='Verified statement formula' for c in result['changes']))

    def test_export_writes_every_calculated_amount(self):
        result,_=self.run_scenario()
        output,saved=rs.export(self.data,self.source,result['scenario'],True)
        self.assertEqual(len(saved['changes']),len(result['changes']))
        with pymupdf.open(stream=output,filetype='pdf') as doc:
            words={w[4] for p in doc for w in p.get_text('words')}
        self.assertTrue({c['new'] for c in result['changes']}<=words)
        tampered={**result['scenario'],'proposal':{**result['scenario']['proposal'],'edits':result['scenario']['proposal']['edits'][:1]}}
        with self.assertRaises(ValueError):rs.export(self.data,self.source,tampered,True)
        with self.assertRaises(ValueError):rs.export(self.data,self.source,result['scenario'],False)

    def test_repeated_figure_ids_are_kept_and_numbered(self):
        message={'content':json.dumps({'document_year':'2025','region':'Germany','industry':'Trade','indicators':[
            {'id':'fuel','name':'Diesel','change_percent':'-7.9','period':'July 2025','source':1},
            {'id':'fuel','name':'Petrol','change_percent':'-3.9','period':'July 2025','source':1},
            {'id':'Gas Prices','name':'Gas','change_percent':'1.6','period':'July 2025','source':2}]})}
        with patch.object(rs,'_call',side_effect=[research_message(),message]):
            found=rs.research('header',self.source,'en')
        self.assertEqual([v['id'] for v in found['indicators']],['fuel','fuel_2','gas_prices'])

    def test_stuck_request_is_retried(self):
        answer=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'ok'}}]}).encode()
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,limit):return answer
        tries=[]
        def flaky(request,timeout):
            tries.append(timeout)
            if len(tries)<3:raise TimeoutError()
            return Response()
        with patch.dict('os.environ',{'OPENROUTER_API_KEY':'test'}),patch('urllib.request.urlopen',flaky):
            self.assertEqual(rs._call({'model':'m','messages':[]}),{'content':'ok'})
        self.assertEqual(len(tries),3)
        tries.clear()
        with patch.dict('os.environ',{'OPENROUTER_API_KEY':'test'}),patch('urllib.request.urlopen',side_effect=TimeoutError()),self.assertRaises(ValueError):
            rs._call({'model':'m','messages':[]})

    def test_provider_errors_are_explained(self):
        import io,urllib.error
        def failing(code,body):
            def raise_(request,timeout):raise urllib.error.HTTPError('u',code,'x',{},io.BytesIO(json.dumps(body).encode()))
            return raise_
        limited={'error':{'message':'The operation was aborted','code':504,'metadata':{'previous_errors':[{'code':429,'raw':'google/gemini-4-argon is temporarily rate-limited upstream.'}]}}}
        bad={'error':{'message':'Provider returned error','code':400,'metadata':{'raw':'Invalid JSON schema: enum too large'}}}
        with patch.dict('os.environ',{'OPENROUTER_API_KEY':'test'}),patch('time.sleep'):
            with patch('urllib.request.urlopen',failing(504,limited)),self.assertRaisesRegex(ValueError,'rate-limited by its provider. Choose another AI model'):
                rs._call({'model':'google/gemini-4-argon','messages':[]})
            with patch('urllib.request.urlopen',failing(400,bad)),self.assertRaisesRegex(ValueError,r'HTTP 400.*Reason: Provider returned error Invalid JSON schema'):
                rs._call({'model':'m','messages':[]})

    def test_cash_basis_ytd_edit_keeps_month_realistic(self):
        data=(ROOT/'10-10-docs'/'10257_BWA_2026-07_261009_205545.pdf').read_bytes()
        source=validate_analysis(data,analyze(data))
        ytd={(c.get('label') or c['context']):c for c in source['cells'] if c.get('editable') and c['column_index']==4}
        month={a:m for m,a in source['period_pairs']}
        cells={c['id']:c for c in source['cells']}
        def drivers(payload):
            state=json.loads(payload['messages'][1]['content'])
            pick={'Umsatzsteuer':'sales','Personalkosten':'indicator'}
            return {'content':json.dumps({'user_changes':{u['id']:{'revenue':True} for u in state['user_changes']},'summary':'Planning scenario.',
                'accounts':{a['id']:{'revenue':False,'driver':pick.get(a['label'],'none'),'indicators':['wages'] if a['label']=='Personalkosten' else [],'reason':'Test.'}
                            for a in state['accounts']}})}
        answers=iter([research_message(),extraction()])
        def fake(payload,timeout=180):return next(answers,None) or drivers(payload)
        with patch.dict('os.environ',{'OPENROUTER_API_KEY':'test'}),patch.object(rs,'_call',side_effect=fake):
            result=rs.preview(data,source,[{'id':ytd['betrieblicher Tätigkeit']['id'],'value':'100.000,00'}],'en')
        changed={c['id']:parse_amount(c['new'],'de')[0] for c in result['changes']}
        # Revenue +41.558,78 lands in July (+453 %); VAT follows exactly, without a cap.
        vat=ytd['Umsatzsteuer']
        self.assertEqual(changed[vat['id']]-Decimal(vat['value']),(Decimal('41558.78')*Decimal(vat['value'])/Decimal('58441.22')).quantize(Decimal('.01')))
        self.assertEqual(changed[month[vat['id']]]-Decimal(cells[month[vat['id']]]['value']),changed[vat['id']]-Decimal(vat['value']))
        # Wages +4.2 % apply to the July amount, not the whole year-to-date amount.
        wage=ytd['Personalkosten'];july=cells[month[wage['id']]]
        self.assertEqual(changed[month[wage['id']]],(Decimal(july['value'])*Decimal('1.042')).quantize(Decimal('.01')))
        self.assertEqual(changed[wage['id']],Decimal(wage['value'])+changed[month[wage['id']]]-Decimal(july['value']))
        with self.assertRaisesRegex(ValueError, 'Export blocked.*attached SuSa'):
            rs.export(data,source,result['scenario'],True)

    def test_susa_is_rejected_before_any_ai_call(self):
        with patch.object(rs,'_call') as call,self.assertRaises(ValueError):
            rs.preview(self.data,{**self.source,'profile':'addison_susa','export_mode':'image'},[{'id':'x','value':'1,00'}])
        call.assert_not_called()


if __name__=='__main__':
    unittest.main()
