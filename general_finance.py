"""General PDF extraction and explicitly reviewed additive calculation rules."""
from decimal import Decimal
import base64
import io
import re
import hashlib
import hmac

import numpy as np
import pymupdf
from PIL import Image,ImageDraw,ImageFont
from pathlib import Path


def parse_amount(text,locale):
    text=text.strip();suffix=text[-1:] if text[-1:] in ('S','H') else ''
    numeric=text[:-1].strip() if suffix else text
    pattern=r'-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2}' if locale=='de' else r'-?\d{1,3}(?:,\d{3})*\.\d{2}|-?\d+\.\d{2}'
    if locale not in ('de','en') or not re.fullmatch(pattern,numeric):raise ValueError('Use an amount with two decimals in the chosen number format.')
    value=Decimal(numeric.replace('.','').replace(',','.')) if locale=='de' else Decimal(numeric.replace(',',''))
    # S/H are labels here; their debit/credit meaning must be encoded in reviewed rules.
    return value,suffix


def format_amount(value,locale,suffix=''):
    result=f'{value:,.2f}'
    if locale=='de':result=result.replace(',','X').replace('.',',').replace('X','.')
    return result+suffix


def _ocr(image):
    import scan_editor
    with scan_editor._lock:
        if scan_editor._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            scan_editor._engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
        result,_=scan_editor._engine(np.array(image))
    return result or []


def extract(data,locale='de',rotation=0):
    if locale not in ('de','en') or rotation not in (0,90,180,270):raise ValueError('Invalid number format or scan rotation.')
    cells=[];notes=[]
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        if doc.is_encrypted:raise ValueError('Unlock password-protected PDFs before uploading.')
        for page in doc:
            words=page.get_text('words')
            groups={}
            for word in words:groups.setdefault((word[5],word[6]),[]).append(word)
            if words:
                for word in words:
                    try:value,suffix=parse_amount(word[4],locale)
                    except ValueError:continue
                    rect=pymupdf.Rect(word[:4])*page.rotation_matrix
                    line=' '.join(w[4] for w in groups[(word[5],word[6])])
                    cells.append({'id':f'c{len(cells)+1}','page':page.number+1,'text':word[4],'value':str(value),'suffix':suffix,'context':line[:240],'box':list(rect),'mode':'text','rotation':0})
            else:
                scale=min(2,2200/max(page.rect.width,page.rect.height))
                pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False,annots=False)
                image=Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB').rotate(-rotation,expand=True)
                if image.width*image.height>25_000_000:raise ValueError('Page exceeds OCR size limit.')
                ocr_results=_ocr(image)
                for box,text,confidence in ocr_results:
                    try:value,suffix=parse_amount(text.strip(),locale)
                    except ValueError:continue
                    if confidence<0.85:continue
                    xs=[p[0] for p in box];ys=[p[1] for p in box]
                    center_y=sum(ys)/len(ys)
                    row_context=sorted([(min(p[0] for p in other_box),other_text) for other_box,other_text,other_score in ocr_results if other_score>=0.75 and abs(sum(p[1] for p in other_box)/len(other_box)-center_y)<=max(12,(max(ys)-min(ys))*.8)])
                    context=' | '.join(t for _,t in row_context)[:500]
                    cells.append({'id':f'c{len(cells)+1}','page':page.number+1,'text':text.strip(),'value':str(value),'suffix':suffix,'context':context or f'OCR region ({round(confidence*100)}% confidence)','box':[min(xs)/scale,min(ys)/scale,max(xs)/scale,max(ys)/scale],'mode':'ocr','rotation':rotation})
                notes.append(f'Page {page.number+1}: amounts extracted with OCR; verify every selected value and region.')
        if not cells:raise ValueError('No amounts with two decimals found. Check number format and scan rotation.')
        return {'pages':len(doc),'cells':cells,'locale':locale,'notes':notes,'automatic_rules':False}


def calculate(extracted,edits,rules):
    cells={c['id']:c for c in extracted['cells']};values={key:Decimal(c['value']) for key,c in cells.items()}
    by_target={}
    for rule in rules:
        target=rule['target'];terms=rule['terms']
        if target not in cells or target in by_target or not terms:raise ValueError('Rules need a unique existing target and at least one source.')
        seen=set()
        for term in terms:
            if term['source'] not in cells or term['source']==target or term['source'] in seen or term['sign'] not in (-1,1):raise ValueError('Invalid, duplicate, or self-referencing source.')
            seen.add(term['source'])
        by_target[target]=rule
    order=[];visiting=set();visited=set()
    def visit(target):
        if target in visiting:raise ValueError('Calculation rules contain a cycle.')
        if target in visited:return
        visiting.add(target)
        for term in by_target[target]['terms']:
            if term['source'] in by_target:visit(term['source'])
        visiting.remove(target);visited.add(target);order.append(target)
    for target in by_target:visit(target)
    for target in order:
        expected=sum((values[t['source']]*t['sign'] for t in by_target[target]['terms']),Decimal(0))
        if expected!=values[target]:raise ValueError(f'Rule for {target} does not match the original statement: printed {values[target]}, calculated {expected}. Check signs and source amounts.')
    for edit in edits:
        key=edit['id']
        if key not in cells or key in by_target:raise ValueError('Edit a source amount, not a calculated target.')
        values[key]=parse_amount(edit['value'],extracted['locale'])[0]
    for target in order:values[target]=sum((values[t['source']]*t['sign'] for t in by_target[target]['terms']),Decimal(0))
    changes=[]
    for key,cell in cells.items():
        if values[key]!=Decimal(cell['value']):changes.append({**cell,'new':format_amount(values[key],extracted['locale'],cell['suffix']),'reason':'Reviewed formula' if key in by_target else 'Input edit'})
    if not changes:raise ValueError('No amounts changed.')
    return {'changes':changes,'rules_checked':len(rules),'note':'Only supplied, baseline-verified relationships were recalculated. Undeclared dependencies remain unchanged.'}


def signed_extract(data,locale='de',rotation=0):
    from scan_editor import _signature
    analysis={'kind':'general_finance','digest':hashlib.sha256(data).hexdigest(),'statement':extract(data,locale,rotation)}
    return {'analysis':analysis,'signature':_signature(analysis)}


def validate_analysis(data,signed):
    from scan_editor import _signature
    analysis=signed['analysis']
    if not hmac.compare_digest(_signature(analysis),signed['signature']) or analysis.get('kind')!='general_finance' or analysis.get('digest')!=hashlib.sha256(data).hexdigest():
        raise ValueError('Analysis is invalid or expired. Analyze the PDF again.')
    return analysis['statement']


def preview_cell(data,extracted,cell_id):
    cell=next((c for c in extracted['cells'] if c['id']==cell_id),None)
    if not cell:raise ValueError('Unknown amount.')
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        page=doc[cell['page']-1];scale=min(2,2200/max(page.rect.width,page.rect.height))
        pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False)
        image=Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB').rotate(-cell['rotation'],expand=True)
        ImageDraw.Draw(image).rectangle([v*scale for v in cell['box']],outline='red',width=4)
        image.thumbnail((1600,1600));out=io.BytesIO();image.save(out,format='PNG')
        return {'image':base64.b64encode(out.getvalue()).decode(),'page':cell['page']}


def render_changes(data,extracted,edits,rules,allow_raster=False):
    if not allow_raster:raise ValueError('Confirm image-based export for changed pages before creating this general-format PDF.')
    result=calculate(extracted,edits,rules)
    font_path=next((str(p) for p in [Path('C:/Windows/Fonts/arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('/System/Library/Fonts/Supplemental/Arial.ttf')] if p.is_file()),None)
    if not font_path:raise ValueError('Install Arial or DejaVu Sans for rendering.')
    grouped={}
    for c in result['changes']:grouped.setdefault(c['page'],[]).append(c)
    with pymupdf.open(stream=data,filetype='pdf') as source,pymupdf.open() as output:
        for page in source:
            changes=grouped.get(page.number+1)
            if not changes:output.insert_pdf(source,from_page=page.number,to_page=page.number);continue
            if list(page.widgets() or []):raise ValueError('Image export of editable PDF form pages is unsupported.')
            rotations={c['rotation'] for c in changes}
            if len(rotations)!=1:raise ValueError('Mixed scan orientations on one page are unsupported.')
            rotation=rotations.pop();scale=min(3,3000/max(page.rect.width,page.rect.height))
            pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False,annots=True)
            image=Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB').rotate(-rotation,expand=True)
            for cell in changes:
                box=[int(round(v*scale)) for v in cell['box']];x0,y0,x1,y1=box
                if cell['mode']=='ocr':
                    # OCR coordinates were generated at a lower resolution, in the same rotated frame.
                    pass
                x0=max(0,x0);y0=max(0,y0);x1=min(image.width,x1);y1=min(image.height,y1)
                if x1<=x0 or y1<=y0:raise ValueError('Invalid amount region.')
                region=np.array(image.crop((x0,y0,x1,y1)));background=tuple(int(v) for v in np.percentile(region.reshape(-1,3),85,axis=0));foreground=tuple(int(v) for v in np.percentile(region.reshape(-1,3),10,axis=0))
                width,height=x1-x0,y1-y0
                for size in range(height*2,0,-1):
                    font=ImageFont.truetype(font_path,size);bounds=font.getbbox(cell['new'])
                    if bounds[2]-bounds[0]<=width and bounds[3]-bounds[1]<=height:break
                if size<8:raise ValueError('Replacement cannot fit legibly into the selected amount region.')
                patch=Image.new('RGB',(width,height),background);ImageDraw.Draw(patch).text((width-(bounds[2]-bounds[0])-bounds[0],(height-(bounds[3]-bounds[1]))//2-bounds[1]),cell['new'],font=font,fill=foreground);image.paste(patch,(x0,y0))
            image=image.rotate(rotation,expand=True).rotate(page.rotation,expand=True)
            newpage=output.new_page(width=page.cropbox.width,height=page.cropbox.height)
            buffer=io.BytesIO();image.save(buffer,format='PNG');newpage.insert_image(newpage.rect,stream=buffer.getvalue());newpage.set_rotation(page.rotation)
        pdf=output.tobytes(garbage=3,deflate=True)
    return pdf,result
