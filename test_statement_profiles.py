from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import pymupdf

from finance_workflow import analyze, plan, apply
from general_finance import validate_analysis, format_amount
from openrouter_dependencies import decide, inspect_document
from statement_profiles import calculate_profile
from change_preview import previews

ROOT=Path(__file__).resolve().parent.parent


class CashBasisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=(ROOT/'10-10-docs/10257_BWA_2024-12_261009_205509.pdf').read_bytes()
        cls.source=validate_analysis(cls.data,analyze(cls.data))

    def test_full_structure_and_deterministic_intake(self):
        self.assertTrue(self.source['verified'])
        self.assertEqual(self.source['pages'],10)
        self.assertEqual(len(self.source['profile_rules']),433)
        with patch('urllib.request.urlopen') as network:
            self.assertEqual(inspect_document(self.source)['model'],'verified-format-rules')
            result=decide(self.source,[{'id':'c1','value':'3.837,82'}])
            network.assert_not_called()
        self.assertFalse(result['unresolved'])

    def test_income_updates_year_comparisons_percentages_and_liquidity(self):
        result=calculate_profile(self.source,[{'id':'c1','value':'3.837,82'}])
        values={c['id']:c['new'] for c in result['changes']}
        self.assertEqual(values['c3'],'42.623,64')
        self.assertEqual(values['c115'],'-10.613,65')
        self.assertEqual(values['c157'],'-1.841,09')
        self.assertEqual(values['c158'],'-32,42')
        self.assertEqual(values['c153'],'-3.895,54')
        self.assertEqual(values['c38'],'-17,67')
        self.assertNotIn('c13',values)  # No invented VAT calculation.
        self.assertNotIn('c37',values)  # Payroll remains independent.
        self.assertFalse(any(c['page']>6 for c in result['changes']))

    def test_explicit_annual_input_and_multiple_inputs(self):
        result=calculate_profile(self.source,[{'id':'c1','value':'3.837,82'},{'id':'c3','value':'44.623,64'},{'id':'c43','value':'2.886,00'}])
        values={c['id']:c['new'] for c in result['changes']}
        self.assertEqual(values['c3'],'44.623,64')
        self.assertEqual(values['c46'],'13.731,53')
        self.assertNotIn('c115',values)  # Equal monthly income/cost increases.
        self.assertEqual(values['c117'],'-32.873,94')

    def test_year_to_date_correction_updates_current_month_and_recalculates_reports(self):
        monthly=next(c for c in self.source['cells'] if c['id']=='c1')
        annual=next(c for c in self.source['cells'] if c['page']==1 and c.get('row')==monthly['row'] and c.get('column_index')==4)
        target=format_amount(Decimal(annual['value'])*2,'de')
        result=calculate_profile(self.source,[{'id':annual['id'],'value':target}])
        change=next(c for c in result['changes'] if c['id']==monthly['id'])
        self.assertEqual(change['new'],format_amount(Decimal(monthly['value'])+Decimal(annual['value']),'de'))
        self.assertIn('YTD correction',change['reason'])
        self.assertEqual({c['page'] for c in result['changes']},set(range(1,7)))
        # The historical comparison inputs are retained.
        self.assertFalse(any(c['page']==3 and c.get('column_index') in (1,5) for c in result['changes']))

    def test_monthly_insurance_tax_cost_correction_updates_year_to_date_and_result(self):
        from statement_profiles import normalized
        monthly=next(c for c in self.source['cells'] if c['page']==1 and c.get('row')==normalized('Steuern/Versicherungen/Beiträge') and c.get('column_index')==0)
        annual=next(c for c in self.source['cells'] if c['page']==1 and c.get('row')==monthly['row'] and c.get('column_index')==4)
        result=calculate_profile(self.source,[{'id':monthly['id'],'value':format_amount(Decimal(monthly['value'])+1,'de')}])
        changes={c['id']:c for c in result['changes']}
        self.assertEqual(changes[annual['id']]['new'],format_amount(Decimal(annual['value'])+1,'de'))
        for c in self.source['cells']:
            if c['page']==1 and c.get('row')==normalized('Einnahmen-Ausgaben-BWA') and c.get('column_index') in (0,4):
                self.assertEqual(changes[c['id']]['new'],format_amount(Decimal(c['value'])-1,'de'))

    def test_year_to_date_export_rechecks_allocated_month_and_preserves_ledger(self):
        monthly=next(c for c in self.source['cells'] if c['id']=='c1')
        annual=next(c for c in self.source['cells'] if c['page']==1 and c.get('row')==monthly['row'] and c.get('column_index')==4)
        edits=[{'id':annual['id'],'value':format_amount(Decimal(annual['value'])*2,'de')}]
        output,_=apply(self.data,self.source,edits,self.source['profile_rules'])
        saved=validate_analysis(output,analyze(output))
        self.assertTrue(saved['verified'],saved['discrepancies'])
        self.assertEqual(next(c['value'] for c in saved['cells'] if c['id']=='c1'),str((Decimal(monthly['value'])+Decimal(annual['value'])).quantize(Decimal('.01'))))
        with pymupdf.open(stream=self.data,filetype='pdf') as original,pymupdf.open(stream=output,filetype='pdf') as modified:
            for i in range(6,len(original)):
                self.assertEqual(original[i].get_pixmap().samples,modified[i].get_pixmap().samples)

    def test_reject_derived_inputs_rules_and_undefined_percentages(self):
        with self.assertRaisesRegex(ValueError,'independent'):
            calculate_profile(self.source,[{'id':'c115','value':'100,00'}])
        with self.assertRaisesRegex(ValueError,'incomplete'):
            plan(self.data,self.source,[{'id':'c1','value':'3.837,82'}],self.source['profile_rules'][:-1])
        with self.assertRaisesRegex(ValueError,'denominator'):
            calculate_profile(self.source,[{'id':'c1','value':'0,00'}])

    def test_native_export_preserves_fonts_pixels_and_ledger_pages(self):
        edits=[{'id':'c1','value':'12.837,82'}]
        output,result=apply(self.data,self.source,edits,self.source['profile_rules'])
        saved=validate_analysis(output,analyze(output))
        self.assertTrue(saved['verified'])
        self.assertEqual(next(c['text'] for c in saved['cells'] if c['id']=='c1'),'12.837,82')
        with pymupdf.open(stream=self.data,filetype='pdf') as before,pymupdf.open(stream=output,filetype='pdf') as after:
            for a,b in zip(before,after):
                self.assertEqual(a.rect,b.rect);self.assertEqual(a.rotation,b.rotation)
                if a.number>=6:self.assertEqual(a.get_pixmap().samples,b.get_pixmap().samples)
                if a.number>=6:continue
                zoom=2
                pa=a.get_pixmap(matrix=pymupdf.Matrix(zoom,zoom),alpha=False);pb=b.get_pixmap(matrix=pymupdf.Matrix(zoom,zoom),alpha=False)
                diff=np.any(np.frombuffer(pa.samples,dtype=np.uint8).reshape(pa.height,pa.width,3)!=np.frombuffer(pb.samples,dtype=np.uint8).reshape(pb.height,pb.width,3),axis=2)
                allowed=np.zeros(diff.shape,dtype=bool)
                for c in result['changes']:
                    if c['page']!=a.number+1:continue
                    old=pymupdf.Rect(c['box']);new=next(pymupdf.Rect(w[:4]) for w in b.get_text('words') if w[4]==c['new'] and abs(w[2]-old.x1)<.03 and abs(w[1]-old.y0)<.03)
                    region=(old|new)+(-1,-1,1,1)
                    allowed[max(0,int(region.y0*zoom)):int(region.y1*zoom)+1,max(0,int(region.x0*zoom)):int(region.x1*zoom)+1]=True
                self.assertFalse(np.any(diff&~allowed))
        self.assertTrue(previews(self.data,output,result['changes'])['after'])


class JulyCashBasisTests(CashBasisTests):
    @classmethod
    def setUpClass(cls):
        cls.data=(ROOT/'10-10-docs/10257_BWA_2026-07_261009_205545.pdf').read_bytes()
        cls.source=validate_analysis(cls.data,analyze(cls.data))

    def test_full_structure_and_deterministic_intake(self):
        self.assertTrue(self.source['verified'],self.source['discrepancies'])
        self.assertEqual(self.source['pages'],8)
        self.assertEqual(len(self.source['profile_rules']),454)
        self.assertTrue(any(c.get('column_index')==8 for c in self.source['cells'] if c['page']==5))
        with patch('urllib.request.urlopen') as network:
            self.assertEqual(inspect_document(self.source)['model'],'verified-format-rules')
            network.assert_not_called()

    # Fixture-specific amounts are asserted only for the December report.
    def test_income_updates_year_comparisons_percentages_and_liquidity(self):
        result=calculate_profile(self.source,[{'id':'c1','value':'12.837,82'}])
        self.assertEqual({c['page'] for c in result['changes']},set(range(1,7)))

    def test_explicit_annual_input_and_multiple_inputs(self):
        monthly=next(c for c in self.source['cells'] if c['page']==1 and c.get('column_index')==0 and c.get('editable'))
        annual=next(c for c in self.source['cells'] if c['page']==1 and c.get('row')==monthly['row'] and c.get('column_index')==4)
        result=calculate_profile(self.source,[{'id':monthly['id'],'value':'12.837,82'},{'id':annual['id'],'value':'100.000,00'}])
        self.assertEqual(next(c['new'] for c in result['changes'] if c['id']==annual['id']),'100.000,00')

    def test_reject_derived_inputs_rules_and_undefined_percentages(self):
        derived=next(c for c in self.source['cells'] if c['page']==1 and not c.get('editable'))
        with self.assertRaisesRegex(ValueError,'independent'):
            calculate_profile(self.source,[{'id':derived['id'],'value':'100,00'}])


class SuSaSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=(ROOT/'AB Service GmbH, SuSa per 042026_260927_211659.pdf').read_bytes()
        cls.source=validate_analysis(cls.data,analyze(cls.data))

    def inputs(self):
        cells=self.source['cells']
        bank=next(c for c in cells if c['row']=='1805' and c['column_index']==1)
        cash=next(c for c in cells if c['row']=='1600' and c['column_index']==2)
        return [{'id':c['id'],'value':format_amount(Decimal(c['value'])+1000,'de')} for c in (bank,cash)]

    def test_sideways_original_has_complete_verified_six_columns(self):
        self.assertEqual(self.source['profile'],'addison_susa')
        self.assertTrue(self.source['verified'])
        self.assertEqual(len(self.source['cells']),666)
        self.assertEqual({c['rotation'] for c in self.source['cells']},{90})
        self.assertEqual(len(self.source['profile_rules']),211)

    def test_single_unbalanced_movement_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'counterpart'):
            calculate_profile(self.source,self.inputs()[:1])

    def test_balanced_batch_propagates_ytd_and_closing_balances(self):
        result=calculate_profile(self.source,self.inputs())
        changed={(c['row'],c['column_index']):c['new'] for c in result['changes']}
        self.assertEqual(changed[('1805',5)],'20.184,70S')
        self.assertEqual(changed[('1600',5)],'181.406,31S')
        self.assertIn(('1805',3),changed);self.assertIn(('1600',4),changed)
        self.assertNotIn(('summeklasse1',5),changed)

    def test_scan_export_consent_resolution_orientation_and_saved_formulas(self):
        edits=self.inputs();rules=self.source['profile_rules']
        with self.assertRaisesRegex(ValueError,'Enable image'):
            apply(self.data,self.source,edits,rules)
        output,result=apply(self.data,self.source,edits,rules,allow_raster=True)
        with pymupdf.open(stream=self.data,filetype='pdf') as before,pymupdf.open(stream=output,filetype='pdf') as after:
            for a,b in zip(before,after):
                self.assertEqual(a.rotation,b.rotation);self.assertEqual(a.rect,b.rect)
                self.assertEqual(a.get_images()[0][2:4],b.get_images()[0][2:4])
                if a.number not in {c['page']-1 for c in result['changes']}:self.assertEqual(a.get_pixmap().samples,b.get_pixmap().samples)
            after[1].get_pixmap(matrix=pymupdf.Matrix(1.3,1.3)).save(ROOT/'tmp/pdfs/formats/susa-after.png')
        self.assertTrue(previews(self.data,output,result['changes'])['after'])
        saved=validate_analysis(output,analyze(output))
        self.assertTrue(saved['verified'],saved['discrepancies'])

    def test_reviewed_copy_discrepancies_are_reported_and_blocked(self):
        data=(ROOT/'10-10-docs/AB Service GmbH, SuSa per 042026_260927_211659-reviewed-recalculated.pdf').read_bytes()
        source=validate_analysis(data,analyze(data))
        self.assertEqual(source['profile'],'addison_susa')
        self.assertFalse(source['verified'])
        self.assertTrue(source['discrepancies'])
        with self.assertRaisesRegex(ValueError,'discrepancies'):
            calculate_profile(source,self.inputs())


if __name__=='__main__':unittest.main()


class BuhlBwaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=(ROOT/'57 BWA Amaron Management 7-2025_261008_193942.pdf').read_bytes()
        cls.source=validate_analysis(cls.data,analyze(cls.data))

    def test_structure_is_verified_without_ai(self):
        self.assertEqual(self.source['profile'],'buhl_bwa')
        self.assertTrue(self.source['verified'])
        self.assertEqual(len(self.source['profile_rules']),250)
        self.assertEqual(sum(c['editable'] for c in self.source['cells']),56)
        with patch('urllib.request.urlopen') as network:
            result=decide(self.source,[{'id':'c7','value':'36.825,00'}])
            network.assert_not_called()
        self.assertFalse(result['unresolved'])

    def test_revenue_updates_sums_year_percentages_and_summary(self):
        values={c['id']:c['new'] for c in calculate_profile(self.source,[{'id':'c7','value':'36.825,00'}])['changes']}
        self.assertEqual(values['c1'],'125.958,09')    # Umsatzerlöse group
        self.assertEqual(values['c10'],'340.731,00')   # same delta in the annual column
        self.assertEqual(values['c14'],'70,76')        # other revenue account share
        self.assertEqual(values['c253'],'24.839,62')   # Summe Betriebsergebnis
        self.assertEqual(values['c280'],'128.740,17')  # Summe Ergebnis, year
        self.assertEqual(values['c285'],'55.765,98')   # Rohertrag
        self.assertEqual(values['c289'],'79,45')
        self.assertNotIn('c61',values)                 # payroll is independent

    def test_cost_edit_updates_expense_percentages(self):
        values={c['id']:c['new'] for c in calculate_profile(self.source,[{'id':'c61','value':'-25.166,35'}])['changes']}
        self.assertEqual(values['c55'],'-30.869,24')
        self.assertEqual(values['c247'],'-40.926,36')
        self.assertEqual(values['c253'],'4.839,62')
        self.assertEqual(values['c3'],'-283,33')

    def test_rejects_derived_input(self):
        with self.assertRaises(ValueError):
            calculate_profile(self.source,[{'id':'c1','value':'1,00'}])

    def test_export_keeps_fonts_and_untouched_pixels(self):
        edits=[{'id':'c7','value':'36.825,00'}]
        output,result=apply(self.data,self.source,edits,self.source['profile_rules'])
        saved=validate_analysis(output,analyze(output))
        self.assertTrue(saved['verified'])
        new={c['id']:c['new'] for c in result['changes']}
        self.assertEqual({c['id']:c['text'] for c in saved['cells']},{c['id']:new.get(c['id'],c['text']) for c in self.source['cells']})
        with pymupdf.open(stream=self.data) as a,pymupdf.open(stream=output) as b:
            for page in range(len(a)):
                self.assertEqual(a[page].get_fonts(),b[page].get_fonts())
                x,y=(np.frombuffer(d[page].get_pixmap(dpi=100).samples,np.uint8).reshape(-1,a[page].get_pixmap(dpi=100).w,3) for d in (a,b))
                mask=np.ones(x.shape[:2],bool)
                for c in result['changes']:
                    if c['page']==page+1:
                        x0,y0,x1,y1=(v*100/72 for v in c['box']);mask[int(y0)-2:int(y1)+3,int(x1-84):int(x1)+3]=False
                self.assertFalse((x!=y).any(axis=2)[mask].any())
