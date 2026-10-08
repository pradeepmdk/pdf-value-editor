"""Patch supported native financial amounts without substituting fonts or sizes."""
import re
import pymupdf
from general_finance import parse_amount
from pdf_editor import TOKEN, BASE14, decode_literal
EXACT_TOKEN = re.compile(rb'\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|/[^\s/\[\]()<>]+|-?\d*\.?\d+|[A-Za-z*\x27\"]+|\S')


def _operand(tokens, i):
    if tokens[i].group() == b'Tj':
        first = i-1
    elif tokens[i].group() == b'TJ' and i >= 3 and tokens[i-3].group() == b'[' and tokens[i-1].group() == b']':
        first = i-2
    else: return None
    value = tokens[first].group()
    if value.startswith(b'('): raw = decode_literal(value[1:-1])
    elif value.startswith(b'<'): raw = bytes.fromhex(value[1:-1].decode())
    else: return None
    return raw, tokens[first-1].start() if tokens[i].group() == b'TJ' else tokens[first].start()


def apply_exact(data, changes, locale):
    if any(c['mode'] != 'text' for c in changes):
        raise ValueError('Exact font export is unavailable for scanned amounts. Supply a native PDF exported from the accounting software; OCR cannot recover the original editable font.')
    with pymupdf.open(stream=data, filetype='pdf') as check:
        text = ''.join(p.get_text() for p in check)
    if 'DATEV-BWA' in text and 'BWA Form 01' in text:
        from finance import analyze, apply
        source = analyze(data); mapped = []; wanted = {}
        for c in changes:
            match = [(row, column) for row in source['rows'] for column, cell in enumerate(row['cells'])
                     if c['page'] == 1 and tuple(round(v, 3) for v in cell['rect']) == tuple(round(v, 3) for v in c['box']) and cell['text'] == c['text']]
            if len(match) != 1: raise ValueError('BWA amount location cannot be matched safely.')
            row, column = match[0]; wanted[(row['id'], column)] = c['new']
            if row['editable'] and column < 12: mapped.append({'row': row['id'], 'column': column, 'value': c['new']})
        output, verified_changes = apply(data, mapped)
        if wanted != {(c['row_id'], c['column_index']): c['new'] for c in verified_changes}:
            raise ValueError('Changes do not cover the complete verified BWA graph.')
        return output
    pending = {(c['page'], tuple(round(v, 3) for v in c['box'])): c for c in changes}
    if len(pending) != len(changes):
        raise ValueError('Ambiguous amount locations.')
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        if doc.is_encrypted:
            raise ValueError('Unlock the original PDF first.')
        for page in doc:
            if not any(key[0] == page.number + 1 for key in pending): continue
            if list(page.widgets() or []):
                raise ValueError('Exact export of interactive financial forms is unavailable.')
            spans = [s for b in page.get_text('dict')['blocks'] for line in b.get('lines', []) for s in line['spans']]
            amounts = []
            for span in spans:
                try: parse_amount(span['text'].strip(), locale)
                except ValueError: continue
                amounts.append(span)
            stream = page.read_contents(); tokens = list(EXACT_TOKEN.finditer(stream))
            operators = []
            for i, token in enumerate(tokens):
                operand = _operand(tokens, i)
                if operand:
                    text = operand[0].decode('cp1252').strip()
                    try: parse_amount(text, locale)
                    except ValueError: continue
                    operators.append((i, text))
            if [text for _, text in operators] != [s['text'].strip() for s in amounts]:
                raise ValueError('This PDF uses split or encoded amount text. Exact export cannot preserve its font safely; use the source software export.')
            fonts = {f[4]: f[3] for f in page.get_fonts()}
            font = None; size = 0; spacing = {}; matrix_ok = True; stack = []; patches = []
            spans_by_operator = {i: span for (i, _), span in zip(operators, amounts)}
            for i, token in enumerate(tokens):
                op = token.group()
                if op == b'q': stack.append((font, size, dict(spacing), matrix_ok))
                elif op == b'Q' and stack: font, size, spacing, matrix_ok = stack.pop()
                elif op == b'Tf': font = fonts.get(tokens[i-2].group().decode().lstrip('/')); size = float(tokens[i-1].group())
                elif op in (b'Tc', b'Tw', b'Tz', b'Ts'): spacing[op] = float(tokens[i-1].group())
                elif op in (b'Tm', b'cm'):
                    matrix = [float(t.group()) for t in tokens[i-6:i]]
                    identity = matrix[:4] == [1, 0, 0, 1]
                    matrix_ok = identity if op == b'Tm' else matrix_ok and identity
                if i not in spans_by_operator: continue
                span = spans_by_operator[i]; rect = pymupdf.Rect(span['bbox']) * page.rotation_matrix
                key = (page.number + 1, tuple(round(v, 3) for v in rect))
                change = pending.get(key)
                if change is None: continue
                if span['text'].strip() != change['text']:
                    raise ValueError('Amount location no longer matches the original PDF.')
                if font not in BASE14 or size <= 0 or not matrix_ok or any(spacing.get(k, v) != v for k, v in ((b'Tc', 0), (b'Tw', 0), (b'Tz', 100), (b'Ts', 0))):
                    raise ValueError('This amount has an unsupported font or text transform. Exact export is blocked rather than changing its appearance.')
                old = change['text']; new = change['new']; box = pymupdf.Rect(span['bbox'])
                width = pymupdf.get_text_length(new, fontname=BASE14[font], fontsize=size)
                previous = [pymupdf.Rect(s['bbox']) for s in spans if s is not span and s['bbox'][2] <= box.x0 + .01 and min(s['bbox'][3], box.y1) > max(s['bbox'][1], box.y0)]
                left_limit = max((r.x1 + 1 for r in previous), default=0)
                if box.x1 - width < left_limit:
                    raise ValueError('The replacement cannot fit at the original font size without overlapping another field. Exact export is blocked.')
                next_op = next((t.group() for t in tokens[i+1:] if t.group() in (b'Tj', b'TJ', b'Td', b'TD', b'Tm', b'BT', b'ET')), None)
                if next_op in (b'Tj', b'TJ'):
                    raise ValueError('Chained text positioning cannot be preserved safely.')
                delta = pymupdf.get_text_length(old, fontname=BASE14[font], fontsize=size) - width
                raw, start = _operand(tokens, i)
                replacement = raw.replace(old.encode('cp1252'), new.encode('cp1252'), 1)
                replacement = replacement.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')
                command = f'{delta:.6f} 0 Td '.encode() + b'(' + replacement + b')Tj' + f' {-delta:.6f} 0 Td'.encode()
                patches.append((start, token.end(), command)); del pending[key]
            for start, end, command in reversed(patches): stream = stream[:start] + command + stream[end:]
            refs = page.get_contents(); doc.update_stream(refs[0], stream)
            for ref in refs[1:]: doc.update_stream(ref, b'')
        if pending:
            raise ValueError('Some selected amounts cannot be matched to native PDF text with exact formatting.')
        output = doc.tobytes(garbage=3, deflate=True)
    # Verify actual saved amounts, fonts, sizes, and right edges after rendering extraction.
    with pymupdf.open(stream=output, filetype='pdf') as saved, pymupdf.open(stream=data, filetype='pdf') as original:
        for c in changes:
            page = saved[c['page']-1]; old_page = original[c['page']-1]
            def spans(p): return [s for b in p.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']]
            old = next((s for s in spans(old_page) if tuple(round(v, 3) for v in pymupdf.Rect(s['bbox']) * old_page.rotation_matrix) == tuple(round(v, 3) for v in c['box'])), None)
            matches = [s for s in spans(page) if s['text'].strip() == c['new'] and abs(s['bbox'][2]-old['bbox'][2]) < .02 and abs(s['bbox'][1]-old['bbox'][1]) < .02] if old else []
            if not any(s['font'] == old['font'] and abs(s['size']-old['size']) < .001 for s in matches):
                raise ValueError('Saved PDF failed exact amount/font/size verification.')
    return output
