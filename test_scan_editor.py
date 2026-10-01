import base64
import io
import unittest
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

from scan_editor import edit_scan, locate_scan


class ScanEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = (Path(__file__).resolve().parent.parent / 'SuSa-AB-Service-GmbH-042026.pdf').read_bytes()
        cls.found = locate_scan(cls.data, '373,00S', 1, 0)

    def test_ocr_edit_preserves_outside_pixels_and_other_pages(self):
        selection = self.found['matches'][0]
        output = edit_scan(self.data, '473,00S', selection)
        with pymupdf.open(stream=self.data, filetype='pdf') as before, pymupdf.open(stream=base64.b64decode(output['pdf']), filetype='pdf') as after:
            self.assertEqual(len(before), len(after))
            arrays = []
            for doc in (before, after):
                xref = doc[0].get_images()[0][0]
                arrays.append(np.array(Image.open(io.BytesIO(doc.extract_image(xref)['image'])).convert('RGB')))
            diff = np.any(arrays[0] != arrays[1], axis=2)
            self.assertTrue(diff.any())
            x0, y0, x1, y1 = selection['candidate']['box']
            diff[y0:y1, x0:x1] = False
            self.assertFalse(diff.any())
            for i in range(len(before)):
                self.assertEqual(before[i].rect, after[i].rect)
                self.assertEqual(before[i].rotation, after[i].rotation)
                if i:
                    self.assertEqual(before[i].get_pixmap().samples, after[i].get_pixmap().samples)

    def test_reject_modified_selection(self):
        selection = {'candidate': dict(self.found['matches'][0]['candidate']), 'signature': self.found['matches'][0]['signature']}
        selection['candidate']['old'] = '999,00'
        with self.assertRaises(ValueError):
            edit_scan(self.data, '499,00', selection)

    def test_accept_mixed_replacement(self):
        result = edit_scan(self.data, 'Test 1H', self.found['matches'][0])
        self.assertEqual(result['count'], 1)

    def test_find_alphabetic_text(self):
        found = locate_scan(self.data, 'AB Service GmbH', 1, 0)
        self.assertTrue(found['matches'])


if __name__ == '__main__':
    unittest.main()
