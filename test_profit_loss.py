from decimal import Decimal
from pathlib import Path
import unittest

from finance_workflow import analyze, plan, apply
from general_finance import validate_analysis, format_amount, parse_amount
from profit_loss import options, resolve

ROOT = Path(__file__).resolve().parent.parent


class BWAGoalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.annual_data = (ROOT/'10-10-docs/BWA-ganzjaehrig-2025.pdf').read_bytes()
        cls.annual = validate_analysis(cls.annual_data, analyze(cls.annual_data))
        cls.cash_data = (ROOT/'10-10-docs/10257_BWA_2024-12_261009_205509.pdf').read_bytes()
        cls.cash = validate_analysis(cls.cash_data, analyze(cls.cash_data))

    def goal(self, statement, period, source, kind='profit', amount='1.000,00'):
        return {'period': period, 'source': source, 'kind': kind, 'amount': amount}

    def test_annual_month_profit_and_loss_with_expense_input(self):
        for kind, expected in [('profit','1.000,00'), ('loss','-1.000,00')]:
            with self.subTest(kind=kind):
                result = resolve(self.annual, [], self.goal(self.annual,'final_0','staff_0',kind))
                changes = {c['id']:c['new'] for c in result['changes']}
                self.assertEqual(changes['final_0'],expected)
                self.assertNotIn('revenue_0',changes)
                plan(self.annual_data,self.annual,result['edits'],result['rules'])

    def test_annual_total_target_with_existing_other_month_edit(self):
        result = resolve(self.annual,[{'id':'staff_1','value':'4.000,00'}],
                         self.goal(self.annual,'final_12','revenue_0'))
        self.assertEqual(result['profit_loss']['after'],'1.000,00')
        self.assertIn({'id':'staff_1','value':'4.000,00'},result['edits'])
        plan(self.annual_data,self.annual,result['edits'],result['rules'])

    def test_annual_export_has_verified_target(self):
        result=resolve(self.annual,[],self.goal(self.annual,'final_0','revenue_0'))
        output,_=apply(self.annual_data,self.annual,result['edits'],result['rules'])
        saved=validate_analysis(output,analyze(output))
        self.assertEqual(next(c['text'] for c in saved['cells'] if c['id']=='final_0'),'1.000,00')

    def test_cash_periods_and_monthly_ytd_delta(self):
        config=options(self.cash)
        self.assertEqual(len(config['periods']),2)
        monthly,annual=config['periods']
        source=next(c for c in self.cash['cells'] if c['id'] in monthly['sources'] and c['column_index']==0)
        result=resolve(self.cash,[],self.goal(self.cash,monthly['id'],source['id']))
        changes={c['id']:c for c in result['changes']}
        self.assertEqual(changes[monthly['target']]['new'],'1.000,00')
        # Both period results move by the same input delta.
        monthly_original=next(c for c in self.cash['cells'] if c['id']==monthly['target'])
        annual_original=next(c for c in self.cash['cells'] if c['id']==annual['target'])
        annual_new=Decimal(changes[annual['target']]['new'].replace('.','').replace(',','.'))
        self.assertEqual(annual_new-Decimal(annual_original['value']),Decimal(1000)-Decimal(monthly_original['value']))
        self.assertFalse(any(c['page']>6 for c in result['changes']))

    def test_cash_ytd_loss_export(self):
        annual=options(self.cash)['periods'][1]
        source=next(c for c in self.cash['cells'] if c['id'] in annual['sources'] and c['column_index']==4)
        result=resolve(self.cash,[],self.goal(self.cash,annual['id'],source['id'],'loss','5.000,00'))
        output,_=apply(self.cash_data,self.cash,result['edits'],result['rules'])
        saved=validate_analysis(output,analyze(output))
        self.assertTrue(saved['verified'])
        self.assertEqual(next(c['text'] for c in saved['cells'] if c['id']==annual['target']),'-5.000,00')

    def test_monthly_input_can_reach_million_profit_ytd_target(self):
        monthly,annual=options(self.cash)['periods']
        self.assertIn('c1',annual['sources'])
        result=resolve(self.cash,[],self.goal(self.cash,annual['id'],'c1','profit','1.000.000,00'))
        self.assertEqual(result['profit_loss']['after'],'1.000.000,00')
        self.assertEqual([e['id'] for e in result['edits']],['c1'])
        output,_=apply(self.cash_data,self.cash,result['edits'],result['rules'])
        saved=validate_analysis(output,analyze(output))
        self.assertTrue(saved['verified'])
        self.assertEqual(next(c['text'] for c in saved['cells'] if c['id']==annual['target']),'1.000.000,00')

    def test_explicit_ytd_override_blocks_monthly_goal_adjustment(self):
        annual=options(self.cash)['periods'][1]
        with self.assertRaisesRegex(ValueError,'contributes'):
            resolve(self.cash,[{'id':'c3','value':'50.000,00'}],self.goal(self.cash,annual['id'],'c1'))

    def test_invalid_goals_cannot_edit_derived_or_unrelated_fields(self):
        for changes in [{'source':'final_0'},{'source':'revenue_1'},{'period':'invented'},
                        {'kind':'unknown'},{'amount':'-1.000,00'},{'amount':'1.000,00H'}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                resolve(self.annual,[],{**self.goal(self.annual,'final_0','revenue_0'),**changes})


class SuSaGoalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=(ROOT/'AB Service GmbH, SuSa per 042026_260927_211659.pdf').read_bytes()
        cls.source=validate_analysis(cls.data,analyze(cls.data))

    def goal(self,period='susa_month',kind='profit',amount='1.000,00'):
        debit,credit=(1,2) if period=='susa_month' else (3,4)
        source_row,source_col,counter_row,counter_col=('4400',credit,'1805',debit) if kind=='profit' else ('6020',debit,'3300',credit)
        def identifier(row,col):return next(c['id'] for c in self.source['cells'] if c['row']==row and c['column_index']==col)
        return {'kind':kind,'amount':amount,'period':period,'source':identifier(source_row,source_col),'counterpart':identifier(counter_row,counter_col)}

    def test_susa_both_periods_support_profit_and_loss(self):
        self.assertEqual(len(options(self.source)['periods']),2)
        for period in ('susa_month','susa_ytd'):
            for kind in ('profit','loss'):
                with self.subTest(period=period,kind=kind):
                    goal=self.goal(period,kind)
                    result=resolve(self.source,[],goal)
                    self.assertEqual(result['profit_loss']['after'],'1.000,00' if kind=='profit' else '-1.000,00')
                    self.assertEqual({e['id'] for e in result['edits']},{goal['source'],goal['counterpart']})
                    plan(self.data,self.source,result['edits'],result['rules'])

    def test_missing_or_wrong_counterpart_rejected(self):
        goal=self.goal()
        for counterpart in ('',goal['source'],next(c['id'] for c in self.source['cells'] if c['row']=='1805' and c['column_index']==2)):
            with self.subTest(counterpart=counterpart),self.assertRaisesRegex(ValueError,'counterpart'):
                resolve(self.source,[],{**goal,'counterpart':counterpart})

    def test_monthly_susa_inputs_can_set_ytd_result(self):
        goal={**self.goal(kind='loss'),'period':'susa_ytd'}
        annual=options(self.source)['periods'][1]
        current=parse_amount(annual['current'],'de')[0]
        desired=min(current,Decimal(0))-Decimal(1000)
        goal['amount']=format_amount(-desired,'de')
        self.assertIn(goal['source'],annual['sources'])
        result=resolve(self.source,[],goal)
        self.assertEqual(result['profit_loss']['after'],format_amount(desired,'de'))
        self.assertEqual({e['id'] for e in result['edits']},{goal['source'],goal['counterpart']})

    def test_profit_loss_scan_export_and_saved_balances(self):
        goal=self.goal(kind='loss')
        result=resolve(self.source,[],goal)
        with self.assertRaisesRegex(ValueError,'image'):
            apply(self.data,self.source,result['edits'],result['rules'])
        output,_=apply(self.data,self.source,result['edits'],result['rules'],allow_raster=True)
        saved=validate_analysis(output,analyze(output))
        self.assertTrue(saved['verified'],saved['discrepancies'])
        monthly=options(saved)['periods'][0]
        self.assertEqual(monthly['current'],'-1.000,00')


if __name__=='__main__':unittest.main()
