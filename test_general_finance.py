import unittest
import pymupdf
from general_finance import extract,calculate,render_changes,signed_extract,validate_analysis


class GeneralFinanceTests(unittest.TestCase):
    def setUp(self):
        with pymupdf.open() as doc:
            page=doc.new_page(width=500,height=400)
            page.insert_text((40,60),'Sales 100.00',fontsize=14)
            page.insert_text((40,100),'Costs 30.00',fontsize=14)
            page.insert_text((40,140),'Profit 70.00',fontsize=14)
            doc.new_page(width=500,height=400).insert_text((40,60),'Unchanged appendix')
            self.data=doc.tobytes()
        self.extracted=extract(self.data,'en')
        self.rules=[{'target':'c3','terms':[{'source':'c1','sign':1},{'source':'c2','sign':-1}]}]
        self.edits=[{'id':'c1','value':'120.00'}]

    def test_arbitrary_template_and_reviewed_formula(self):
        self.assertEqual(len(self.extracted['cells']),3)
        result=calculate(self.extracted,self.edits,self.rules)
        self.assertEqual([(c['id'],c['new']) for c in result['changes']],[('c1','120.00'),('c3','90.00')])

    def test_reject_wrong_formula_and_cycle(self):
        with self.assertRaises(ValueError):calculate(self.extracted,self.edits,[{'target':'c3','terms':[{'source':'c1','sign':1}]}])
        with self.assertRaises(ValueError):calculate(self.extracted,self.edits,[{'target':'c1','terms':[{'source':'c3','sign':1}]},{'target':'c3','terms':[{'source':'c1','sign':1}]}])

    def test_export_requires_explicit_image_consent(self):
        with self.assertRaises(ValueError):render_changes(self.data,self.extracted,self.edits,self.rules)
        output,_=render_changes(self.data,self.extracted,self.edits,self.rules,True)
        with pymupdf.open(stream=self.data,filetype='pdf') as a,pymupdf.open(stream=output,filetype='pdf') as b:
            self.assertEqual(len(a),len(b))
            self.assertEqual(a[0].rect,b[0].rect)
            self.assertEqual(a[1].get_pixmap().samples,b[1].get_pixmap().samples)
            self.assertTrue(b[0].get_images())

    def test_rotated_page_dimensions_preserved(self):
        with pymupdf.open(stream=self.data,filetype='pdf') as doc:
            doc[0].set_rotation(90);data=doc.tobytes()
        extracted=extract(data,'en');output,_=render_changes(data,extracted,self.edits,self.rules,True)
        with pymupdf.open(stream=data,filetype='pdf') as a,pymupdf.open(stream=output,filetype='pdf') as b:
            self.assertEqual(a[0].rect,b[0].rect)
            self.assertEqual(a[0].rotation,b[0].rotation)

    def test_analysis_cannot_be_modified(self):
        signed=signed_extract(self.data,'en');validate_analysis(self.data,signed)
        signed['analysis']['statement']['cells'][0]['value']='999'
        with self.assertRaises(ValueError):validate_analysis(self.data,signed)


if __name__=='__main__':unittest.main()
