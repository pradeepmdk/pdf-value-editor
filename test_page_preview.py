import base64
import unittest
import pymupdf
from general_finance import preview_page


class AllPagePreviewTests(unittest.TestCase):
    def test_page_without_amounts_is_rendered(self):
        with pymupdf.open() as doc:
            doc.new_page(width=300,height=200)
            doc.new_page(width=200,height=300)
            data=doc.tobytes()
        statement={'pages':2,'cells':[]}
        result=preview_page(data,statement,2)
        self.assertEqual(result['page'],2);self.assertEqual((result['width'],result['height']),(200,300))
        self.assertTrue(base64.b64decode(result['image']).startswith(b'\x89PNG'))
        with self.assertRaises(ValueError):preview_page(data,statement,3)


if __name__=='__main__':unittest.main()
