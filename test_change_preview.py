import base64
from pathlib import Path
import unittest
import pymupdf
from change_preview import previews
from finance_workflow import analyze, apply
from general_finance import validate_analysis


class PreviewTests(unittest.TestCase):
    def test_later_page_and_longer_replacement_bounds(self):
        from exact_finance import apply_exact
        from general_finance import extract, calculate
        with pymupdf.open() as doc:
            for i in range(2):
                p=doc.new_page();p.insert_text((50,70),'Revenue',fontsize=10);p.insert_text((300,70),'100.00',fontsize=10)
            data=doc.tobytes()
        extracted=extract(data,'en')
        changes=calculate(extracted,[{'id':'c2','value':'100,000.00'}],[])['changes']
        output=apply_exact(data,changes,'en');preview=previews(data,output,changes)
        self.assertEqual(preview['pages'],[2])
        with pymupdf.open(stream=base64.b64decode(preview['after']),filetype='pdf') as doc:
            self.assertFalse(list(doc[0].annots() or []))
            page=doc[1]
            marks=list(page.annots());self.assertEqual(len(marks),1)
            word=next(w for w in page.get_text('words') if w[4]=='100,000.00')
            self.assertTrue(marks[0].rect.contains(pymupdf.Rect(word[:4])))

    def test_all_bwa_changes_marked_without_marking_download(self):
        data=(Path(__file__).parent.parent/'BWA-ganzjaehrig-2025.pdf').read_bytes()
        extracted=validate_analysis(data,analyze(data))
        edits=[{'id':'revenue_0','value':'62.315,78'}]
        output,result=apply(data,extracted,edits,extracted['candidate_rules'])
        preview=previews(data,output,result['changes'])
        self.assertEqual(preview['pages'],[1])
        for version in ['before','after']:
            with pymupdf.open(stream=base64.b64decode(preview[version]),filetype='pdf') as doc:
                page=doc[0]
                marks=list(page.annots());self.assertEqual(len(marks),len(result['changes']))
                self.assertTrue(all('->' in m.info['content'] for m in marks))
        with pymupdf.open(stream=output,filetype='pdf') as doc:
            self.assertFalse(list(doc[0].annots() or []))
        with pymupdf.open(stream=data,filetype='pdf') as doc:
            self.assertFalse(list(doc[0].annots() or []))


if __name__=='__main__':unittest.main()
