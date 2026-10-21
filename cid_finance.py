"""Patch amounts drawn with embedded Identity-H (two-byte CID) fonts.

The original font, size and text matrix are kept. A replacement is preceded by
a TJ adjustment equal to the width difference, so it stays right aligned and
every later glyph on the line keeps its original position.
"""
import re
import pymupdf
from exact_finance import EXACT_TOKEN

HEX = re.compile(r'<([0-9A-Fa-f]+)>')


def _hex(text):
    return [int(v, 16) for v in HEX.findall(text)]


def _font(doc, xref):
    """Return (code -> unicode, unicode -> code, code -> width, default width)."""
    if doc.xref_get_key(xref, 'Encoding')[1] != '/Identity-H':
        raise ValueError('Exact CID export requires an Identity-H font.')
    kind, ref = doc.xref_get_key(xref, 'ToUnicode')
    if kind != 'xref':
        raise ValueError('The CID font has no ToUnicode map.')
    cmap = doc.xref_stream(int(ref.split()[0])).decode('latin1')
    decode = {}
    for block in re.findall(r'beginbfchar(.*?)endbfchar', cmap, re.S):
        for src, dst in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block):
            decode[int(src, 16)] = chr(int(dst, 16))
    for block in re.findall(r'beginbfrange(.*?)endbfrange', cmap, re.S):
        for start, end, dst in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]+>|\[[^\]]*\])', block):
            start, end = int(start, 16), int(end, 16)
            targets = _hex(dst) if dst.startswith('[') else [int(dst[1:-1], 16) + i for i in range(end - start + 1)]
            for i, target in enumerate(targets):
                decode[start + i] = chr(target)
    descendant = int(doc.xref_get_key(xref, 'DescendantFonts')[1].strip('[] ').split()[0])
    kind, default = doc.xref_get_key(descendant, 'DW')
    default = float(default) if kind == 'int' or kind == 'float' else 1000.0
    kind, raw = doc.xref_get_key(descendant, 'W')
    if kind == 'xref':
        raw = doc.xref_object(int(raw.split()[0]))
    widths = {}
    items = re.findall(r'\[[^\]]*\]|-?\d+(?:\.\d+)?', raw.strip()[1:-1] if raw.strip().startswith('[') else raw)
    i = 0
    while i < len(items):
        first = int(items[i])
        if items[i + 1].startswith('['):
            for k, w in enumerate(re.findall(r'-?\d+(?:\.\d+)?', items[i + 1])):
                widths[first + k] = float(w)
            i += 2
        else:
            for code in range(first, int(items[i + 1]) + 1):
                widths[code] = float(items[i + 2])
            i += 3
    encode = {}
    for code, char in decode.items():
        encode.setdefault(char, code)
    return decode, encode, widths, default


def _number(value):
    return f' {value:.4f} '.encode()


def _pieces(doc, page, metrics):
    """Text runs in user space. A run joins kerned fragments of one operator
    and continues into the next operator when it starts exactly where the
    previous one ended (e.g. after a character-spacing change)."""
    stream = page.read_contents()
    tokens = list(EXACT_TOKEN.finditer(stream))
    tm = [1, 0, 0, 1, 0, 0]; tlm = list(tm); font = None; size = 0.0; tc = 0.0; tz = 100.0; tl = 0.0
    stack = []; runs = []; run = None

    def show(elements, close):
        nonlocal tm, run
        tx = 0.0; piece = None
        for token in elements:
            value = token.group()
            if not value.startswith(b'<'):
                if value.startswith(b'('):
                    raise ValueError('Literal strings in a CID font cannot be patched safely.')
                tx -= float(value) / 1000 * size * tz / 100
                if abs(float(value)) > 150: run = piece = None
                continue
            raw = bytes.fromhex(value[1:-1].decode())
            codes = [int.from_bytes(raw[k:k + 2], 'big') for k in range(0, len(raw), 2)]
            decode, _, widths, default = metrics(font)
            text = ''.join(decode.get(code, '�') for code in codes)
            begin = tx
            tx += sum((widths.get(code, default) / 1000 * size + tc) * tz / 100 for code in codes)
            if tm[1] or tm[2] or ' ' in text or not text:
                run = piece = None
                continue
            x0, x1 = tm[0] * begin + tm[4], tm[0] * tx + tm[4]
            if piece is None:
                piece = {'first': token, 'close': close, 'font': font, 'size': size, 'tc': tc, 'tz': tz, 'scale': tm[0], 'start': x0}
                if run and run['baseline'] == tm[5] and abs(run['end'] - x0) < .2:
                    run['pieces'].append(piece)
                else:
                    run = {'baseline': tm[5], 'pieces': [piece], 'text': ''}; runs.append(run)
            piece.update(last=token, end=x1)
            run['text'] += text; run['end'] = x1
        tm = [tm[0], tm[1], tm[2], tm[3], tm[0] * tx + tm[4], tm[1] * tx + tm[5]]

    for i, token in enumerate(tokens):
        op = token.group()
        if op == b'q': stack.append((font, size, tc, tz, tl))
        elif op == b'Q' and stack: font, size, tc, tz, tl = stack.pop()
        elif op in (b'BT', b'ET'): tm = [1, 0, 0, 1, 0, 0]; tlm = list(tm); run = None
        elif op == b'Tf': font = tokens[i - 2].group().decode().lstrip('/'); size = float(tokens[i - 1].group())
        elif op == b'Tc': tc = float(tokens[i - 1].group())
        elif op == b'Tz': tz = float(tokens[i - 1].group())
        elif op == b'TL': tl = float(tokens[i - 1].group())
        elif op == b'Tm': tm = [float(t.group()) for t in tokens[i - 6:i]]; tlm = list(tm)
        elif op in (b'Td', b'TD', b'T*'):
            x, y = (0.0, -tl) if op == b'T*' else (float(tokens[i - 2].group()), float(tokens[i - 1].group()))
            if op == b'TD': tl = -y
            tlm = [tlm[0], tlm[1], tlm[2], tlm[3], x * tlm[0] + y * tlm[2] + tlm[4], x * tlm[1] + y * tlm[3] + tlm[5]]
            tm = list(tlm)
        elif op == b'Tj': show(tokens[i - 1:i], token)
        elif op == b'TJ':
            start = i - 1
            while start >= 0 and tokens[start].group() != b'[': start -= 1
            show(tokens[start + 1:i - 1], None)
        elif op in (b"'", b'"'):
            raise ValueError('Unsupported text operator in amount stream.')
    return stream, runs


def apply_cid(data, changes):
    pending = {c['id']: c for c in changes}
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        if doc.is_encrypted:
            raise ValueError('Unlock the original PDF first.')
        for page in doc:
            wanted = [c for c in pending.values() if c['page'] == page.number + 1]
            if not wanted:
                continue
            if page.rotation or page.rect.x0 or page.rect.y0:
                raise ValueError('Exact CID export supports unrotated pages only.')
            fonts = {f[4]: f[0] for f in page.get_fonts()}; cache = {}

            def metrics(name):
                if name not in fonts:
                    raise ValueError('Unknown font resource in content stream.')
                if name not in cache:
                    cache[name] = _font(doc, fonts[name])
                return cache[name]

            stream, runs = _pieces(doc, page, metrics)
            height = page.rect.height; patches = []
            for c in wanted:
                matches = [r for r in runs if r['text'] == c['text'] and abs(r['end'] - c['box'][2]) < .6
                           and c['box'][1] - 1 <= height - r['baseline'] <= c['box'][3] + 2]
                if len(matches) != 1:
                    raise ValueError('An amount could not be matched to native CID text; exact export blocked.')
                pieces = matches[0]['pieces']; first = pieces[0]
                _, encode, widths, _ = metrics(first['font'])
                codes = []
                for char in c['new']:
                    if char not in encode or encode[char] not in widths:
                        raise ValueError(f'The embedded font subset has no glyph for "{char}"; exact export blocked.')
                    codes.append(encode[char])
                unit = first['size'] * first['tz'] / 100 * first['scale'] / 1000  # user space per TJ unit
                width = sum((widths[k] / 1000 * first['size'] + first['tc']) * first['tz'] / 100 for k in codes) * first['scale']
                end = matches[0]['end']
                # Shift right so the new amount ends at the original right edge,
                # then move back so the rest of the operator keeps its position.
                body = (_number(-(end - first['start'] - width) / unit)
                        + b'<' + b''.join(k.to_bytes(2, 'big') for k in codes).hex().upper().encode() + b'>'
                        + _number((end - first['end']) / unit))
                replacements = [(first, body)]
                for piece in pieces[1:]:
                    scale = piece['size'] * piece['tz'] / 100 * piece['scale'] / 1000
                    replacements.append((piece, _number(-(piece['end'] - piece['start']) / scale)))
                for piece, body in replacements:
                    if piece['close'] is not None:
                        patches.append((piece['first'].start(), piece['close'].end(), b'[' + body + b']TJ'))
                    else:
                        patches.append((piece['first'].start(), piece['last'].end(), body))
                del pending[c['id']]
            for start, end, command in sorted(patches, reverse=True):
                stream = stream[:start] + command + stream[end:]
            refs = page.get_contents(); doc.update_stream(refs[0], stream)
            for ref in refs[1:]: doc.update_stream(ref, b'')
        if pending:
            raise ValueError('Some amounts could not be matched to native PDF text.')
        output = doc.tobytes(garbage=3, deflate=True)
    with pymupdf.open(stream=output, filetype='pdf') as saved:
        for c in changes:
            words = saved[c['page'] - 1].get_text('words')
            if not any(w[4] == c['new'] and abs(w[2] - c['box'][2]) < .05 for w in words):
                raise ValueError('Saved PDF failed amount position verification.')
    return output
