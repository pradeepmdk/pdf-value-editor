"""Edit WinAnsi TJ glyphs using the existing font and text positioning.

Every removed glyph retains its original advance. Inserted text is right aligned
and its advance cancelled, preserving subsequent text, including split amounts.
"""
import re
import pymupdf
from pdf_editor import decode_literal

TOKENS = re.compile(rb'\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|/[^\s/\[\]()<>]+|-?\d*\.?\d+|[A-Za-z*\x27\"]+|\S')


def _bytes(token):
    return decode_literal(token[1:-1]) if token.startswith(b'(') else bytes.fromhex(token[1:-1].decode())


def _number(value):
    return f'{value:.8f}'.encode()


def _hex(value):
    return b'<' + value.hex().encode() + b'>'


def _shows(page):
    tokens = list(TOKENS.finditer(page.read_contents()))
    fonts = {f[4]: f for f in page.get_fonts()}
    font = None; size = 0; tc = 0; scale = 100; stack = []; shows = []; offset = 0
    for i, t in enumerate(tokens):
        op = t.group()
        if op == b'q': stack.append((font,size,tc,scale))
        elif op == b'Q' and stack: font,size,tc,scale=stack.pop()
        elif op == b'Tf': font=fonts.get(tokens[i-2].group().decode().lstrip('/'));size=float(tokens[i-1].group())
        elif op == b'Tc': tc=float(tokens[i-1].group())
        elif op == b'Tz': scale=float(tokens[i-1].group())
        elif op in (b'Tj',b'TJ'):
            if op == b'Tj': start=i-1;parts=[tokens[start]]
            else:
                start=i-1
                while start>=0 and tokens[start].group()!=b'[':start-=1
                if start<0:raise ValueError('Unmatched native text array.')
                parts=tokens[start+1:i-1]
            raw=b''.join(_bytes(p.group()) for p in parts if p.group().startswith((b'(',b'<')))
            shows.append({'start':tokens[start].start(),'end':t.end(),'parts':parts,'raw':raw,
                          'offset':offset,'font':font,'size':size,'tc':tc,'scale':scale})
            offset+=len(raw)
    return shows


def _glyphs(page):
    return [(trace,c) for trace in page.get_texttrace() for c in trace['chars']]


def _widths(doc, font):
    if not font or font[5] != 'WinAnsiEncoding':
        raise ValueError('Native glyph editing requires a verified WinAnsi font.')
    kind,raw=doc.xref_get_key(font[0],'Widths')
    if kind=='xref':raw=doc.xref_object(int(raw.split()[0]))
    if kind not in ('array','xref'):raise ValueError('The native font has no explicit character widths.')
    widths=[float(n) for n in re.findall(r'-?\d+(?:\.\d+)?',raw)]
    first=int(doc.xref_get_key(font[0],'FirstChar')[1])
    return {first+i:w for i,w in enumerate(widths)}


def apply_native(data,changes):
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        for page in doc:
            selected=[c for c in changes if c['page']==page.number+1]
            if not selected:continue
            if list(page.widgets() or []):raise ValueError('Native editing of interactive forms is unsupported.')
            glyphs=_glyphs(page);shows=_shows(page)
            if b''.join(s['raw'] for s in shows).decode('cp1252')!=''.join(chr(c[0]) for _,c in glyphs):
                raise ValueError('Native text operators do not match rendered glyphs.')
            removed=set();insertions={};width_cache={}
            for change in selected:
                box=pymupdf.Rect(change['box'])*page.derotation_matrix
                ids=[i for i,(_,c) in enumerate(glyphs) if box.x0-.02<=c[2][0]<box.x1-.02 and box.y0<=c[2][1]<=box.y1]
                if not ids or ''.join(chr(glyphs[i][1][0]) for i in ids)!=change['text'] or ids!=list(range(ids[0],ids[-1]+1)):
                    raise ValueError('The selected amount cannot be matched to its exact native glyphs.')
                show=next(s for s in shows if s['offset']<=ids[0]<s['offset']+len(s['raw']))
                if show['scale']!=100 or show['size']<=0:raise ValueError('Unsupported native text scale.')
                font=show['font'];widths=width_cache.setdefault(font[0],_widths(doc,font))
                new=change['new'].encode('cp1252')
                if any(b not in widths for b in new):raise ValueError('The original font cannot encode the replacement.')
                new_width=sum(widths[b]*show['size']/1000 for b in new)+show['tc']*(len(new)-1)
                left=box.x1-new_width
                # A replacement can grow into whitespace, but never into another field.
                obstacles=[pymupdf.Rect(w[:4]) for w in page.get_text('words') if w[2]<=box.x0+.02 and min(w[3],box.y1)>max(w[1],box.y0)]
                if left<max((r.x1+1 for r in obstacles),default=0):raise ValueError('Replacement overlaps another field at the original font size.')
                delta=left-glyphs[ids[0]][1][2][0]
                advance=new_width+show['tc']
                insertions[ids[0]]=(_number(-delta*1000/show['size'])+b' '+_hex(new)+b' '+_number((delta+advance)*1000/show['size']))
                if removed.intersection(ids):raise ValueError('Overlapping native amount selections.')
                removed.update(ids)
            patches=[]
            for show in shows:
                if not removed.intersection(range(show['offset'],show['offset']+len(show['raw']))):continue
                widths=width_cache.setdefault(show['font'][0],_widths(doc,show['font']))
                position=show['offset'];parts=[]
                for part in show['parts']:
                    raw=part.group()
                    if not raw.startswith((b'(',b'<')):parts.append(raw);continue
                    pending=bytearray()
                    for byte in _bytes(raw):
                        if position in removed:
                            if pending:parts.append(_hex(bytes(pending)));pending.clear()
                            if position in insertions:parts.append(insertions[position])
                            parts.append(_number(-(widths[byte]+show['tc']*1000/show['size'])))
                        else:pending.append(byte)
                        position+=1
                    if pending:parts.append(_hex(bytes(pending)))
                patches.append((show['start'],show['end'],b'['+b' '.join(parts)+b'] TJ'))
            stream=page.read_contents()
            for start,end,replacement in reversed(patches):stream=stream[:start]+replacement+stream[end:]
            refs=page.get_contents();doc.update_stream(refs[0],stream)
            for ref in refs[1:]:doc.update_stream(ref,b'')
        output=doc.tobytes(garbage=3,deflate=True)
    verify_native(data,output,changes)
    return output


def verify_native(data,output,changes):
    with pymupdf.open(stream=data,filetype='pdf') as before,pymupdf.open(stream=output,filetype='pdf') as after:
        if len(before)!=len(after):raise ValueError('Saved page count changed.')
        for a,b in zip(before,after):
            if a.rect!=b.rect or a.rotation!=b.rotation:raise ValueError('Saved page dimensions changed.')
            selected=[c for c in changes if c['page']==a.number+1]
            if not selected:
                if a.read_contents()!=b.read_contents():raise ValueError('An untouched page changed.')
                continue
            old=_glyphs(a);new=_glyphs(b);old_removed=set();new_removed=set()
            for change in selected:
                box=pymupdf.Rect(change['box'])*a.derotation_matrix
                original=[i for i,(_,c) in enumerate(old) if box.x0-.02<=c[2][0]<box.x1-.02 and box.y0<=c[2][1]<=box.y1]
                matches=[w for w in b.get_text('words') if w[4]==change['new'] and abs(w[2]-box.x1)<.03 and abs(w[1]-box.y0)<.03]
                if len(matches)!=1:raise ValueError('Saved replacement failed amount/position verification.')
                region=pymupdf.Rect(matches[0][:4])
                replaced=[i for i,(_,c) in enumerate(new) if region.x0-.02<=c[2][0]<region.x1-.02 and region.y0<=c[2][1]<=region.y1]
                if ''.join(chr(new[i][1][0]) for i in replaced)!=change['new']:raise ValueError('Saved glyph verification failed.')
                if any(new[i][0]['font']!=old[original[0]][0]['font'] or abs(new[i][0]['size']-old[original[0]][0]['size'])>.001 for i in replaced):raise ValueError('Saved replacement font or size changed.')
                old_removed.update(original);new_removed.update(replaced)
            untouched_old=[(t['font'],t['size'],c[0],c[2]) for i,(t,c) in enumerate(old) if i not in old_removed]
            untouched_new=[(t['font'],t['size'],c[0],c[2]) for i,(t,c) in enumerate(new) if i not in new_removed]
            if len(untouched_old)!=len(untouched_new):raise ValueError('Unrelated glyph count changed.')
            for x,y in zip(untouched_old,untouched_new):
                if x[:3]!=y[:3] or any(abs(v-w)>.03 for v,w in zip(x[3],y[3])):raise ValueError('Unrelated native text changed.')
