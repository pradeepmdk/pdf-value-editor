import unittest
from pathlib import Path

import numpy as np
import pymupdf

from pdf_editor import edit_pdf, select_text


class PDFEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).resolve().parent.parent / 'BWA-ganzjaehrig-2025.pdf').read_bytes()

    def test_all_matches_and_unchanged_layout(self):
        result, count, pages = edit_pdf(self.source, '52.315,78', '62.315,78')
        self.assertEqual((count, pages), (3, [1]))
        with pymupdf.open(stream=self.source, filetype='pdf') as before, pymupdf.open(stream=result, filetype='pdf') as after:
            self.assertEqual(after[0].get_text(), before[0].get_text().replace('52.315,78', '62.315,78'))
            self.assertEqual(before[0].rect, after[0].rect)
            self.assertEqual(before[0].get_fonts(), after[0].get_fonts())
            zoom = 2
            a = before[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            b = after[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            diff = np.any(np.frombuffer(a.samples, dtype=np.uint8).reshape(a.height, a.width, 3) != np.frombuffer(b.samples, dtype=np.uint8).reshape(b.height, b.width, 3), axis=2)
            allowed = np.zeros(diff.shape, dtype=bool)
            for rect in before[0].search_for('52.315,78'):
                rect = rect * before[0].rotation_matrix
                allowed[max(0, int(rect.y0 * zoom)-2):int(rect.y1 * zoom)+3, max(0, int(rect.x0 * zoom)-2):int(rect.x1 * zoom)+3] = True
            self.assertTrue(diff.any())
            self.assertFalse(np.any(diff & ~allowed), 'Pixels changed outside the target numbers')

    def test_single_occurrence(self):
        result, count, _ = edit_pdf(self.source, '52.315,78', '62.315,78', occurrence=2)
        with pymupdf.open(stream=result, filetype='pdf') as doc:
            self.assertEqual(count, 1)
            self.assertEqual(doc[0].get_text().count('52.315,78'), 2)
            self.assertEqual(doc[0].get_text().count('62.315,78'), 1)

    def test_reject_unsafe_or_missing_values(self):
        for old, new, occurrence in [('52.315,78', '', 0), ('999.999,99', '888.888,88', 0), ('52.315,78', '62.315,78', 9)]:
            with self.assertRaises(ValueError):
                edit_pdf(self.source, old, new, occurrence)

    def test_mixed_text_and_pdf_string_escaping(self):
        result, count, _ = edit_pdf(self.source, '52.315,78', 'Test (A)', 1)
        with pymupdf.open(stream=result, filetype='pdf') as doc:
            self.assertEqual(count, 1)
            self.assertIn('Test (A)', doc[0].get_text())

    def test_longer_text_fits(self):
        result, count, _ = edit_pdf(self.source, '52.315,78', 'Invoice 123', 1)
        with pymupdf.open(stream=result, filetype='pdf') as doc:
            self.assertIn('Invoice 123', doc[0].get_text())

    def test_rotated_area_selects_second_occurrence(self):
        with pymupdf.open(stream=self.source, filetype='pdf') as doc:
            page = doc[0]
            rect = page.search_for('52.315,78')[1] * page.rotation_matrix
            region = [rect.x0/page.rect.width,rect.y0/page.rect.height,rect.x1/page.rect.width,rect.y1/page.rect.height]
        selected = select_text(self.source, 1, region)
        self.assertEqual(selected['matches'], [{'text':'52.315,78','occurrence':2}])


if __name__ == '__main__':
    unittest.main()
