import unittest
from unittest.mock import patch
import pymupdf
from finance_workflow import apply
from change_preview import previews
import upload_cache
import analysis_jobs
from concurrent.futures import Future


class ScanWorkflowTests(unittest.TestCase):
    def test_background_job_pending_complete_and_failure(self):
        future=Future()
        with patch('analysis_jobs._pool.submit',return_value=future):
            job=analysis_jobs.start(lambda:None)['job']
        self.assertEqual(analysis_jobs.poll(job)['state'],'processing')
        future.set_result({'amounts':640})
        self.assertEqual(analysis_jobs.poll(job)['result'],{'amounts':640})
        failure=Future();failure.set_exception(ValueError('OCR failed'))
        with patch('analysis_jobs._pool.submit',return_value=failure):
            job=analysis_jobs.start(lambda:None)['job']
        with self.assertRaisesRegex(ValueError,'OCR failed'):
            analysis_jobs.poll(job)

    def test_upload_reference_roundtrip_and_expiry(self):
        token=upload_cache.store(b'PDF bytes')
        self.assertEqual(upload_cache.resolve(token),b'PDF bytes')
        with patch('upload_cache.time.monotonic',return_value=10**12):
            with self.assertRaisesRegex(ValueError,'expired'):
                upload_cache.resolve(token)
        with self.assertRaisesRegex(ValueError,'expired'):
            upload_cache.resolve('unknown')

    def test_scan_requires_consent_and_preserves_untouched_page(self):
        with pymupdf.open() as native:
            page=native.new_page(width=300,height=200)
            page.insert_text((40,60),'100,00',fontsize=14)
            box=next(w[:4] for w in page.get_text('words') if w[4]=='100,00')
            image=page.get_pixmap(matrix=pymupdf.Matrix(2,2)).tobytes('png')
        with pymupdf.open() as source:
            page=source.new_page(width=300,height=200)
            page.insert_image(page.rect,stream=image)
            source.new_page(width=300,height=200).insert_text((30,40),'Unchanged page')
            data=source.tobytes()
        extracted={'export_mode':'image','locale':'de','cells':[{'id':'c1','page':1,'text':'100,00','value':'100.00','suffix':'','context':'Example amount','mode':'ocr','rotation':0,'box':list(box)}]}
        edits=[{'id':'c1','value':'120,00'}]
        with self.assertRaisesRegex(ValueError,'Enable image-based'):
            apply(data,extracted,edits,[])
        output,result=apply(data,extracted,edits,[],allow_raster=True)
        self.assertTrue(previews(data,output,result['changes'])['after'])
        with pymupdf.open(stream=data,filetype='pdf') as before,pymupdf.open(stream=output,filetype='pdf') as after:
            self.assertEqual(len(after),2)
            self.assertEqual(before[1].get_pixmap().samples,after[1].get_pixmap().samples)
            self.assertEqual(after[1].get_text(),before[1].get_text())


if __name__=='__main__':
    unittest.main()
