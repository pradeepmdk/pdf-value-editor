"""Change selected scan pixels at the source image's original resolution."""
import io
from pathlib import Path
import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont


def apply_scan(data,changes):
    font_path=next((p for p in (Path('C:/Windows/Fonts/arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')) if p.is_file()),None)
    if font_path is None:raise ValueError('Arial or DejaVu Sans is required for scanned amount replacement.')
    expected={}
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        for page in doc:
            selected=[c for c in changes if c['page']==page.number+1]
            if not selected:continue
            if any(c.get('confidence',0)<.85 for c in selected):raise ValueError('A changed SuSa field has insufficient OCR confidence. Re-scan and verify it before export.')
            images=page.get_images()
            if len(images)!=1 or list(page.widgets() or []):raise ValueError('This scan uses an unsupported image or form layout.')
            xref=images[0][0];placements=page.get_image_rects(xref,transform=True)
            if len(placements)!=1:raise ValueError('The scan image has ambiguous placement.')
            rect,matrix=placements[0]
            if any(abs(v-w)>.05 for v,w in zip(rect,page.cropbox)) or abs(matrix.b)>.001 or abs(matrix.c)>.001 or matrix.a<=0 or matrix.d<=0:
                raise ValueError('The scan image must cover the original page without skew.')
            rotations={c['rotation'] for c in selected}
            if len(rotations)!=1:raise ValueError('Mixed OCR orientations on one page.')
            rotation=rotations.pop();angle=(page.rotation+rotation)%360
            source=Image.open(io.BytesIO(doc.extract_image(xref)['image'])).convert('RGB')
            image=source.rotate(-angle,expand=True)
            width,height=(page.rect.height,page.rect.width) if rotation in (90,270) else (page.rect.width,page.rect.height)
            sx=image.width/width;sy=image.height/height
            original=np.array(image);mask=np.zeros(original.shape[:2],dtype=bool)
            for c in selected:
                x0,y0,x1,y1=[round(v*s) for v,s in zip(c['box'],(sx,sy,sx,sy))]
                if not 0<=x0<x1<=image.width or not 0<=y0<y1<=image.height:raise ValueError('Invalid scan amount bounds.')
                if mask[y0:y1,x0:x1].any():raise ValueError('Overlapping scan amount selections.')
                mask[y0:y1,x0:x1]=True;region=original[y0:y1,x0:x1]
                background=tuple(int(v) for v in np.percentile(region.reshape(-1,3),85,axis=0))
                foreground=tuple(int(v) for v in np.percentile(region.reshape(-1,3),10,axis=0))
                w,h=x1-x0,y1-y0
                for size in range(h*2,0,-1):
                    font=ImageFont.truetype(str(font_path),size);bounds=font.getbbox(c['new'])
                    if bounds[2]-bounds[0]<=w and bounds[3]-bounds[1]<=h:break
                if size<8:raise ValueError('Replacement cannot fit legibly in the scanned amount region.')
                patch=Image.new('RGB',(w,h),background)
                ImageDraw.Draw(patch).text((w-(bounds[2]-bounds[0])-bounds[0],(h-(bounds[3]-bounds[1]))//2-bounds[1]),c['new'],font=font,fill=foreground)
                image.paste(patch,(x0,y0))
            result=np.array(image)
            if not np.array_equal(original[~mask],result[~mask]):raise ValueError('Pixels outside selected scan amounts changed.')
            image=image.rotate(angle,expand=True)
            buffer=io.BytesIO();image.save(buffer,format='PNG');page.replace_image(xref,stream=buffer.getvalue())
            expected[page.number]=np.array(image)
        output=doc.tobytes(garbage=3,deflate=True)
    with pymupdf.open(stream=output,filetype='pdf') as saved,pymupdf.open(stream=data,filetype='pdf') as original:
        for a,b in zip(original,saved):
            if a.rect!=b.rect or a.rotation!=b.rotation:raise ValueError('Saved scan dimensions or orientation changed.')
            if a.number in expected:
                pixels=np.array(Image.open(io.BytesIO(saved.extract_image(b.get_images()[0][0])['image'])).convert('RGB'))
                if not np.array_equal(pixels,expected[a.number]):raise ValueError('Saved scan pixels failed replacement verification.')
            elif a.get_pixmap().samples!=b.get_pixmap().samples:raise ValueError('An untouched scan page changed.')
    return output
