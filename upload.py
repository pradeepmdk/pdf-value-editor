"""Normalize PDF or common image uploads into an in-memory PDF."""
import io
import pymupdf
from PIL import Image,ImageSequence,UnidentifiedImageError


def prepare(data):
    if data.lstrip().startswith(b'%PDF-'):
        pdf=data;kind='PDF'
    else:
        try:
            source=Image.open(io.BytesIO(data))
            with pymupdf.open() as doc:
                for frame in ImageSequence.Iterator(source):
                    if frame.width*frame.height>25_000_000:raise ValueError('Image exceeds the 25 megapixel limit.')
                    frame=frame.convert('RGB');png=io.BytesIO();frame.save(png,format='PNG')
                    page=doc.new_page(width=frame.width*72/150,height=frame.height*72/150)
                    page.insert_image(page.rect,stream=png.getvalue())
                pdf=doc.tobytes(deflate=True)
            kind='Image'
        except (UnidentifiedImageError,OSError):
            raise ValueError('Upload a valid PDF, PNG, JPEG, TIFF, BMP, or WebP image.')
    with pymupdf.open(stream=pdf,filetype='pdf') as doc:
        if doc.is_encrypted:raise ValueError('Unlock password-protected files before uploading.')
        text='\n'.join(page.get_text() for page in doc)
        automatic=len(doc)==1 and 'DATEV-BWA' in text and 'BWA Form 01' in text
        return {'pdf':pdf,'kind':kind,'pages':len(doc),'automatic_bwa':automatic}
