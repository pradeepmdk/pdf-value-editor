from pathlib import Path
import unittest
from unittest.mock import patch
import json
import io
import os

import numpy as np
import pymupdf
from finance import analyze,plan,apply,RULES
from local_review import review


class FinanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=(Path(__file__).resolve().parent.parent/'BWA-ganzjaehrig-2025.pdf').read_bytes()

    def test_original_statement_is_consistent(self):
        result=analyze(self.data)
        self.assertTrue(result['verified'])
        self.assertEqual(len(result['rows']),32)

    def test_revenue_dependencies_and_visual_preservation(self):
        edits=[{'row':'revenue','column':0,'value':'62.315,78'}]
        result=plan(self.data,edits)
        self.assertEqual(len(result['changes']),14)
        changed={(r['row_id'],r['column_index']):r['new'] for r in result['changes']}
        self.assertEqual(changed[('final',0)],'3.687,76')
        self.assertEqual(changed[('final',12)],'5.150,72')
        output,changes=apply(self.data,edits)
        self.assertTrue(analyze(output)['verified'])
        with pymupdf.open(stream=self.data,filetype='pdf') as a,pymupdf.open(stream=output,filetype='pdf') as b:
            self.assertEqual(a[0].rect,b[0].rect)
            self.assertEqual(a[0].get_fonts(),b[0].get_fonts())
            pa=a[0].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False);pb=b[0].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
            diff=np.any(np.frombuffer(pa.samples,dtype=np.uint8).reshape(pa.height,pa.width,3)!=np.frombuffer(pb.samples,dtype=np.uint8).reshape(pb.height,pb.width,3),axis=2)
            allowed=np.zeros(diff.shape,dtype=bool)
            updated=analyze(output);by_id={r['id']:r for r in updated['rows']}
            for change in changes:
                for rect in (change['rect'],by_id[change['row_id']]['cells'][change['column_index']]['rect']):
                    x0,y0,x1,y1=rect;allowed[max(0,int(y0*2)-3):int(y1*2)+4,max(0,int(x0*2)-3):int(x1*2)+4]=True
            self.assertFalse(np.any(diff & ~allowed),'Pixels changed outside recalculated cells')

    def test_multiple_edits_and_cent_precision(self):
        output,_=apply(self.data,[{'row':'staff','column':0,'value':'27.119,91'},{'row':'revenue','column':1,'value':'67.102,00'}])
        rows={r['id']:r for r in analyze(output)['rows']}
        self.assertEqual(rows['final']['values'][0],'-6.312,25')
        self.assertEqual(rows['final']['values'][1],'11.382,92')
        self.assertEqual(rows['final']['values'][12],'-4.849,27')

    def test_derived_cell_edits_are_rejected(self):
        with self.assertRaises(ValueError):plan(self.data,[{'row':'final','column':0,'value':'10,00'}])
        with self.assertRaises(ValueError):plan(self.data,[{'row':'revenue','column':12,'value':'10,00'}])

    def test_inconsistent_source_is_blocked(self):
        from pdf_editor import edit_pdf
        inconsistent,_,_=edit_pdf(self.data,'52.315,78','62.315,78',1)
        self.assertFalse(analyze(inconsistent)['verified'])
        with self.assertRaises(ValueError):plan(inconsistent,[{'row':'staff','column':0,'value':'1,00'}])

    def test_scan_is_not_treated_as_verified_bwa(self):
        data=(Path(__file__).resolve().parent.parent/'SuSa-AB-Service-GmbH-042026.pdf').read_bytes()
        with self.assertRaises(ValueError):analyze(data)

    def test_local_model_response_is_advisory(self):
        rows=analyze(self.data)['rows']
        response={'message':{'content':json.dumps({'document_type':'BWA','row_roles':[{'id':r['id'],'role':'unknown'} for r in rows]})}}
        with patch.dict(os.environ,{'PDF_EDITOR_OLLAMA_MODEL':'test-local'}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
            result=review(self.data)
        self.assertTrue(result['advisory_only'])
        self.assertEqual(result['model'],'test-local')


if __name__=='__main__':unittest.main()
