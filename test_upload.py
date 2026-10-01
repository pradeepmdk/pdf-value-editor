import io
from pathlib import Path
import unittest
import pymupdf
from PIL import Image,ImageDraw,ImageFont
from upload import prepare
from general_finance import extract,calculate


class UploadTests(unittest.TestCase):
    def test_original_pdf_passes_through(self):
        data=(Path(__file__).resolve().parent.parent/'BWA-ganzjaehrig-2025.pdf').read_bytes()
        result=prepare(data)
        self.assertEqual(result['pdf'],data)
        self.assertTrue(result['automatic_bwa'])

    def test_image_to_ocr_to_calculation(self):
        image=Image.new('RGB',(1400,1000),'white');draw=ImageDraw.Draw(image)
        font_path=next(str(p) for p in [Path('C:/Windows/Fonts/arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.is_file())
        font=ImageFont.truetype(font_path,52)
        for y,label,value in [(180,'Revenue','100,00'),(400,'Costs','30,00'),(620,'Profit','70,00')]:
            draw.text((100,y),label,font=font,fill='black');draw.text((900,y),value,font=font,fill='black')
        out=io.BytesIO();image.save(out,format='PNG')
        result=prepare(out.getvalue());self.assertFalse(result['automatic_bwa'])
        extracted=extract(result['pdf'],'de')
        by_text={c['text']:c['id'] for c in extracted['cells']}
        self.assertTrue({'100,00','30,00','70,00'}<=by_text.keys())
        rule={'target':by_text['70,00'],'terms':[{'source':by_text['100,00'],'sign':1},{'source':by_text['30,00'],'sign':-1}]}
        calculation=calculate(extracted,[{'id':by_text['100,00'],'value':'120,00'}],[rule])
        self.assertIn('90,00',[c['new'] for c in calculation['changes']])

    def test_invalid_upload_is_rejected(self):
        with self.assertRaises(ValueError):prepare(b'not a PDF or image')


if __name__=='__main__':unittest.main()
