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


def _is_amount(text,locale):
    try:parse_amount(text,locale);return True
    except ValueError:return False


def _label_and_column(items,box,locale):
    """Row label = non-amount text left of the amount on the same row; column = nearest non-amount text above it."""
    x0,y0,x1,y1=box;center=(y0+y1)/2
    words=[(b,t) for b,t in items if t.strip() and not _is_amount(t,locale)]
    row=sorted((b[0],t) for b,t in words if b[2]<=x0+2 and b[1]-2<=center<=b[3]+2)
    above=[(b,t) for b,t in words if b[3]<=y0+2 and min(b[2],x1)>max(b[0],x0)]
    column=''
    if above:
        nearest=max(b[3] for b,_ in above)
        column=' '.join(t for b,t in sorted(above,key=lambda e:e[0][0]) if abs(b[3]-nearest)<=4)
    return ' '.join(t for _,t in row)[:200],column[:120]


def extract(data,locale='de',rotation=0):
    if locale not in ('de','en') or rotation not in (0,90,180,270):raise ValueError('Invalid number format or scan rotation.')
    cells=[];notes=[];ocr_pages={}
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        if doc.is_encrypted:raise ValueError('Unlock password-protected PDFs before uploading.')
        for page in doc:
            words=page.get_text('words')
            groups={}
            for word in words:groups.setdefault((word[5],word[6]),[]).append(word)
            if words:
                items=[(list(pymupdf.Rect(w[:4])*page.rotation_matrix),w[4]) for w in words]
                for word in words:
                    try:value,suffix=parse_amount(word[4],locale)
                    except ValueError:continue
                    rect=pymupdf.Rect(word[:4])*page.rotation_matrix
                    line=' '.join(w[4] for w in groups[(word[5],word[6])])
                    label,column=_label_and_column(items,list(rect),locale)
                    cells.append({'id':f'c{len(cells)+1}','page':page.number+1,'text':word[4],'value':str(value),'suffix':suffix,'context':line[:240],'label':label,'column':column,'box':list(rect),'mode':'text','rotation':0})
            else:
                scale=min(2,2200/max(page.rect.width,page.rect.height))
                pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False,annots=False)
                page_rotation=rotation
                if rotation==0 and page.rotation in (90,270) and page.cropbox.width>page.cropbox.height and page.rect.width<page.rect.height:
                    page_rotation=(360-page.rotation)%360
                    notes.append(f'Page {page.number+1}: sideways scan automatically rotated for OCR and editing.')
                image=Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB').rotate(-page_rotation,expand=True)
                if image.width*image.height>25_000_000:raise ValueError('Page exceeds OCR size limit.')
                ocr_results=_ocr(image)
                # Sideways accounting scans often contain upright PDF page metadata.
                # Detect vertical amount polygons before deriving rows and headers.
                vertical=[b for b,t,s in ocr_results if s>=.85 and _is_amount(t.strip(),locale)]
                if page_rotation==0 and len(vertical)>=10 and sum((max(p[1] for p in b)-min(p[1] for p in b))>1.25*(max(p[0] for p in b)-min(p[0] for p in b)) for b in vertical)>len(vertical)*.7:
                    page_rotation=90;image=image.rotate(-90,expand=True);ocr_results=_ocr(image)
                    notes.append(f'Page {page.number+1}: sideways scan automatically rotated clockwise for OCR and editing.')
                cleaned=[]
                for box,text,confidence in ocr_results:
                    candidate=text.strip()
                    if locale=='de' and not _is_amount(candidate,locale) and re.fullmatch(r"[\dO.,'\-]+[SH]?",candidate) and any(c in candidate for c in ",.'"):
                        # Re-read a suspicious numeric token at higher resolution.
                        # Never guess a missing amount from the account formula.
                        crop_box=(max(0,int(min(p[0] for p in box))-8),max(0,int(min(p[1] for p in box))-8),min(image.width,int(max(p[0] for p in box))+8),min(image.height,int(max(p[1] for p in box))+8))
                        crop=image.crop(crop_box);crop=crop.resize((crop.width*3,crop.height*3))
                        retry=[(t.strip(),float(s)) for _,t,s in _ocr(crop) if s>=.85 and _is_amount(t.strip(),locale)]
                        if len(retry)==1:candidate,confidence=retry[0]
                    if locale=='de' and re.fullmatch(r'[\dO.,-]+[SH]?',candidate):
                        corrected=candidate.replace('O','0')
                        if re.fullmatch(r'-?\d+\.\d{2}[SH]?',corrected):corrected=corrected.replace('.',',')
                        if _is_amount(corrected,locale):candidate=corrected
                    cleaned.append((box,candidate,confidence))
                ocr_results=cleaned
                ocr_pages[str(page.number+1)]=[{'box':[min(p[0] for p in b)/scale,min(p[1] for p in b)/scale,max(p[0] for p in b)/scale,max(p[1] for p in b)/scale], 'text':t,'confidence':float(s)} for b,t,s in ocr_results if s>=.75]
                for box,text,confidence in ocr_results:
                    try:value,suffix=parse_amount(text.strip(),locale)
                    except ValueError:continue
                    if confidence<0.75:continue
                    xs=[p[0] for p in box];ys=[p[1] for p in box]
                    center_y=sum(ys)/len(ys)
                    row_context=sorted([(min(p[0] for p in other_box),other_text) for other_box,other_text,other_score in ocr_results if other_score>=0.75 and abs(sum(p[1] for p in other_box)/len(other_box)-center_y)<=max(12,(max(ys)-min(ys))*.8)])
                    context=' | '.join(t for _,t in row_context)[:500]
                    ocr_items=[([min(p[0] for p in b),min(p[1] for p in b),max(p[0] for p in b),max(p[1] for p in b)],t) for b,t,s in ocr_results if s>=0.75]
                    label,column=_label_and_column(ocr_items,[min(xs),min(ys),max(xs),max(ys)],locale)
                    cells.append({'id':f'c{len(cells)+1}','page':page.number+1,'text':text.strip(),'value':str(value),'suffix':suffix,'context':context or f'OCR region ({round(confidence*100)}% confidence)','label':label,'column':column,'box':[min(xs)/scale,min(ys)/scale,max(xs)/scale,max(ys)/scale],'mode':'ocr','rotation':page_rotation,'confidence':float(confidence),'editable':bool(confidence>=.85)})
                notes.append(f'Page {page.number+1}: amounts extracted with OCR; verify every selected value and region.')
        if not cells:raise ValueError('No amounts with two decimals found. Check number format and scan rotation.')
        return {'pages':len(doc),'cells':cells,'locale':locale,'notes':notes,'automatic_rules':False,'ocr_pages':ocr_pages}


def calculate(extracted,edits,rules):
    cells={c['id']:c for c in extracted['cells']};values={key:Decimal(c['value']) for key,c in cells.items()}
    by_target={}
    for rule in rules:
        target=rule['target'];terms=rule['terms']
        if target not in cells:raise ValueError(f'Rule target {target} is not an extracted field.')
        if target in by_target:raise ValueError(f'More than one rule was given for {target}.')
        if not terms:raise ValueError(f'Rule for {target} has no sources.')
        seen=set()
        for term in terms:
            source=term['source']
            if source not in cells:raise ValueError(f'Rule for {target} uses unknown source {source}.')
            if source==target:raise ValueError(f'Rule for {target} references itself as a source.')
            if source in seen:raise ValueError(f'Rule for {target} lists source {source} more than once.')
            if term['sign'] not in (-1,1):raise ValueError(f'Rule for {target} uses an invalid sign for {source}.')
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
        if cells[key].get('editable') is False:raise ValueError('This field is derived or has insufficient OCR confidence for editing.')
        value,suffix=parse_amount(edit['value'],extracted['locale'])
        if suffix!=cells[key]['suffix']:raise ValueError('Preserve the original S/H direction; changing debit/credit direction needs separate accounting rules.')
        if suffix and value<0:raise ValueError('S/H amounts must be non-negative magnitudes. Do not combine a minus sign with a debit/credit suffix.')
        values[key]=value
    for target in order:values[target]=sum((values[t['source']]*t['sign'] for t in by_target[target]['terms']),Decimal(0))
    changes=[]
    for key,cell in cells.items():
        if cell['suffix'] and values[key]<0:
            raise ValueError(f'Calculated balance {key} crosses its original S/H direction. Automatic direction reversal is unsupported; no PDF was created. Review the underlying debit/credit movements.')
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
        width,height=page.rect.width,page.rect.height
        if cell['rotation'] in (90,270):width,height=height,width
        return {'image':base64.b64encode(out.getvalue()).decode(),'page':cell['page'],
                'width':width,'height':height,'rotation':cell['rotation']}


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
                if cell.get('confidence',1)<.85:raise ValueError('A changed field has insufficient OCR confidence. Review or re-scan the source before export.')
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
