"""Local PDF value editor. Run: python pdf_editor.py"""
import base64
import argparse
import html
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pymupdf
from openrouter_dependencies import load_environment

load_environment()

MAX_REQUEST = 30 * 1024 * 1024
TOKEN = re.compile(rb'\((?:\\.|[^\\)])*\)|/[^\s/\[\]()<>]+|-?\d*\.?\d+|[A-Za-z*\x27\"]+|\S')
BASE14 = {"Helvetica": "helv", "Helvetica-Bold": "hebo", "Helvetica-Oblique": "heit", "Helvetica-BoldOblique": "hebi", "Times-Roman": "tiro", "Times-Bold": "tibo", "Courier": "cour", "Courier-Bold": "cobo"}


def decode_literal(raw):
    result = bytearray()
    i = 0
    escapes = {110: 10, 114: 13, 116: 9, 98: 8, 102: 12}
    while i < len(raw):
        if raw[i] != 92:
            result.append(raw[i]); i += 1; continue
        i += 1
        if i >= len(raw):
            break
        match = re.match(rb'[0-7]{1,3}', raw[i:])
        if match:
            result.append(int(match.group(), 8) & 255); i += len(match.group())
        elif raw[i] in (10, 13):
            if raw[i:i+2] == b'\r\n': i += 1
            i += 1
        else:
            result.append(escapes.get(raw[i], raw[i])); i += 1
    return bytes(result)


def edit_pdf(data, old, new, occurrence=0):
    """Replace exact literal text, fitting replacement into the original width.

    Deliberately rejects encoded/custom fonts, split text, and scanned PDFs.
    occurrence=0 means all; positive values select one match in document order.
    """
    if not old.strip() or not new.strip() or any(c in old + new for c in '\r\n\t'):
        raise ValueError('Enter non-empty, single-line text or numbers.')
    try:
        old_bytes, new_bytes = old.encode('cp1252'), new.encode('cp1252')
    except UnicodeEncodeError:
        raise ValueError('This direct editor supports Western European characters; this font cannot encode the requested text.')
    if old == new:
        raise ValueError('The new value must differ from the old value.')
    if occurrence < 0:
        raise ValueError('Occurrence must be zero (all) or a positive number.')
    doc = pymupdf.open(stream=data, filetype='pdf')
    try:
        if doc.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported.')
        matches = []
        for page in doc:
            font_map = {f[4]: f[3] for f in page.get_fonts()}
            stream = page.read_contents()
            tokens = list(TOKEN.finditer(stream))
            font_name = None
            font_resource = None
            size = 0
            char_spacing = word_spacing = 0.0
            scale = 100.0
            stack = []
            patches = []
            for i, token in enumerate(tokens):
                value = token.group()
                if value == b'q':
                    stack.append((font_name, font_resource, size, char_spacing, word_spacing, scale))
                elif value == b'Q' and stack:
                    font_name, font_resource, size, char_spacing, word_spacing, scale = stack.pop()
                elif value == b'Tf' and i >= 2:
                    font_resource = tokens[i-2].group()
                    font_name = font_map.get(font_resource.decode('ascii').lstrip('/'))
                    size = float(tokens[i-1].group())
                elif value in (b'Tc', b'Tw', b'Tz') and i:
                    number = float(tokens[i-1].group())
                    if value == b'Tc': char_spacing = number
                    if value == b'Tw': word_spacing = number
                    if value == b'Tz': scale = number
                elif value == b'Tj' and i and tokens[i-1].group().startswith(b'('):
                    literal = tokens[i-1]
                    raw = decode_literal(literal.group()[1:-1])
                    if raw.strip() != old_bytes:
                        continue
                    matches.append(page.number + 1)
                    if occurrence and len(matches) != occurrence:
                        continue
                    if font_name not in BASE14 or size <= 0:
                        raise ValueError('This value uses an unsupported font encoding. Direct editing is unavailable for this PDF.')
                    replacement = raw.replace(old_bytes, new_bytes, 1)
                    before = raw.decode('cp1252'); after = replacement.decode('cp1252')
                    delta = (pymupdf.get_text_length(before, fontname=BASE14[font_name], fontsize=size)
                             - pymupdf.get_text_length(after, fontname=BASE14[font_name], fontsize=size)
                             + char_spacing * (len(before) - len(after))
                             + word_spacing * (before.count(' ') - after.count(' '))) * scale / 100
                    escaped = replacement.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')
                    replacement_command = b'(' + escaped + b')Tj'
                    if delta < -0.00001:
                        if char_spacing or word_spacing:
                            raise ValueError('Longer text with custom character spacing cannot fit safely.')
                        before_width = pymupdf.get_text_length(before, fontname=BASE14[font_name], fontsize=size)
                        after_width = pymupdf.get_text_length(after, fontname=BASE14[font_name], fontsize=size)
                        fitted_size = size * before_width / after_width
                        if fitted_size < 3:
                            raise ValueError('Replacement is too long to remain legible in the original space.')
                        replacement_command = font_resource + f' {fitted_size:.6f} Tf '.encode() + replacement_command + b' ' + font_resource + f' {size:.6f} Tf'.encode()
                    # Preserve existing text positioning. Shorter text starts at the
                    # original position; longer text is reduced to fit the same width.
                    patches.append((literal.start(), token.end(), replacement_command))
            if patches:
                for start, end, replacement in reversed(patches):
                    stream = stream[:start] + replacement + stream[end:]
                refs = page.get_contents()
                doc.update_stream(refs[0], stream)
                for xref in refs[1:]:
                    doc.update_stream(xref, b'')
        if not matches:
            raise ValueError('No editable exact match found. Scans, split text, and encoded fonts are not supported.')
        if occurrence > len(matches):
            raise ValueError(f'Only {len(matches)} occurrence(s) found.')
        output = doc.tobytes(garbage=3, deflate=True)
        count = 1 if occurrence else len(matches)
        return output, count, sorted(set(matches))
    finally:
        doc.close()


def preview(data, page_number=1):
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        if doc.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported.')
        if not 1 <= page_number <= len(doc):
            raise ValueError('Invalid page number.')
        page = doc[page_number - 1]
        scale = min(1.5, 1600 / max(page.rect.width, page.rect.height))
        png = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')
        return base64.b64encode(png).decode(), len(doc)


def select_text(data, page_number, region):
    if len(region) != 4 or not all(isinstance(v, (float, int)) and 0 <= v <= 1 for v in region) or region[0] >= region[2] or region[1] >= region[3]:
        raise ValueError('Invalid selected region.')
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        if not 1 <= page_number <= len(doc):
            raise ValueError('Invalid page number.')
        selected_page = doc[page_number-1]
        width, height = selected_page.rect.width, selected_page.rect.height
        selected_rect = pymupdf.Rect(region[0]*width,region[1]*height,region[2]*width,region[3]*height)
        candidates = []
        counts = {}
        for page in doc:
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        text = span['text'].strip()
                        if not text:
                            continue
                        counts[text] = counts.get(text,0)+1
                        if page.number != page_number-1:
                            continue
                        rect = pymupdf.Rect(span['bbox']) * page.rotation_matrix
                        intersection = rect & selected_rect
                        if rect.get_area() > 0 and intersection.get_area()/rect.get_area() >= 0.5:
                            candidates.append({'text': text, 'occurrence': counts[text]})
        if not candidates:
            raise ValueError('No complete text found in the selected area. Draw around the whole value, or use the OCR editor for a scan.')
        return {'matches': candidates, 'page': page_number}


class Handler(BaseHTTPRequestHandler):
    allowed_origins = {'http://127.0.0.1:8000', 'http://localhost:8000'}
    def reply(self, status, payload, kind='application/json'):
        body = json.dumps(payload).encode() if kind == 'application/json' else payload
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/api/finance/linked-demo':
            from linked_finance import demo
            return self.reply(200, demo())
        if self.path == '/api/finance/decision-status':
            from openrouter_dependencies import status
            configuration=status()
            return self.reply(200,{'enabled':configuration['enabled'],'model':configuration['model'],'advisory_only':True})
        if self.path == '/api/finance/ai-status':
            from ai_rules import status
            return self.reply(200,status())
        if self.path == '/general':
            self.send_response(302)
            self.send_header('Location','/finance')
            self.end_headers()
            return
        if self.path == '/finance':
            page = Path(__file__).with_name('finance.html').read_text(encoding='utf-8')
            panel = Path(__file__).with_name('linked-finance.html').read_text(encoding='utf-8')
            page = page.replace('</main>', panel + '</main>')
            # Serve one current document so stale or blocked companion scripts
            # cannot leave the obsolete analysis-only handler active.
            for name in ('linked-finance.js', 'amount-format.js', 'finance-edits.js', 'finance-preview.js'):
                script = Path(__file__).with_name(name).read_text(encoding='utf-8')
                page = page.replace('<script src="/' + name + '"></script>', '<script>\n' + script + '\n</script>')
            return self.reply(200, page.encode(), 'text/html; charset=utf-8')
        if self.path in ('/linked-finance.js', '/finance-edits.js', '/finance-preview.js', '/amount-format.js'):
            name = self.path.lstrip('/')
            kind = 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/html; charset=utf-8'
            return self.reply(200, Path(__file__).with_name(name).read_bytes(), kind)
        if self.path == '/selection.js':
            return self.reply(200, Path(__file__).with_name('selection.js').read_bytes(), 'text/javascript; charset=utf-8')
        if self.path == '/scan':
            return self.reply(200, Path(__file__).with_name('scan.html').read_bytes(), 'text/html; charset=utf-8')
        if self.path == '/':
            self.reply(200, Path(__file__).with_name('editor.html').read_bytes(), 'text/html; charset=utf-8')
        else:
            self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if self.headers.get('Origin') is not None and self.headers.get('Origin') not in self.allowed_origins:
            return self.reply(403, {'error': 'Origin not allowed'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_REQUEST:
                return self.reply(413, {'error': 'Upload a PDF smaller than 20 MB.'})
            if self.path == '/api/finance/prepare' and self.headers.get('Content-Type','').split(';')[0] == 'application/octet-stream':
                from upload import prepare
                from upload_cache import store
                if length > 20 * 1024 * 1024:
                    return self.reply(413, {'error':'Upload a PDF smaller than 20 MB.'})
                result=prepare(self.rfile.read(length))
                result['upload_token']=store(result['pdf'])
                result['pdf']=base64.b64encode(result['pdf']).decode()
                return self.reply(200,result)
            request = json.loads(self.rfile.read(length))
            if self.path == '/api/finance/analysis-job':
                from analysis_jobs import poll
                return self.reply(200,poll(request.get('job')))
            if self.path in ('/api/finance/linked-analyze', '/api/finance/linked-plan', '/api/finance/linked-apply'):
                from linked_finance import analyze, plan, apply
                if self.path.endswith('-analyze'):
                    return self.reply(200, analyze(request['documents'], request.get('locale', 'de'), int(request.get('rotation', 0))))
                args = (request['documents'], request['analysis'], request['edits'], request['rules'], request.get('reviewed') is True)
                if self.path.endswith('-plan'):
                    return self.reply(200, plan(*args))
                return self.reply(200, apply(*args, coverage=request.get('coverage') is True))
            if request.get('upload_token'):
                from upload_cache import resolve
                data=resolve(request['upload_token'])
            else:
                data = base64.b64decode(request['pdf'], validate=True)
            page_number = int(request.get('page', 1))
            if self.path == '/api/finance/workflow-analyze-start':
                from analysis_jobs import start,analyze_document
                locale=request.get('locale','de');rotation=int(request.get('rotation',0))
                return self.reply(200,start(lambda:analyze_document(data,locale,rotation)))
            if self.path == '/api/finance/prepare':
                from upload import prepare
                result=prepare(data)
                result['pdf']=base64.b64encode(result['pdf']).decode()
                return self.reply(200,result)
            if self.path == '/api/finance/workflow-analyze':
                from finance_workflow import analyze
                from openrouter_dependencies import inspect_document
                from scan_editor import _signature
                result = analyze(data,request.get('locale','de'),int(request.get('rotation',0)))
                statement = result['analysis']['statement']
                inspection = inspect_document(statement)
                statement['report_type'] = inspection['report_type']
                independent = set(inspection['independent_ids'])
                for cell in statement['cells']:
                    cell['editable'] = cell.get('editable') is not False and cell['id'] in independent
                statement['notes'].insert(0, inspection['report_type'] + ': ' + inspection['summary'])
                statement['notes'].extend('AI uncertainty: ' + item for item in inspection['uncertainties'])
                result['signature'] = _signature(result['analysis'])
                result['inspection'] = inspection
                return self.reply(200,result)
            if self.path in ('/api/finance/workflow-plan','/api/finance/workflow-apply'):
                from general_finance import validate_analysis
                from finance_workflow import plan,apply
                extracted=validate_analysis(data,request['analysis'])
                if request.get('proportional_simulation') is True:
                    from proportional_finance import scenario
                    if self.path.endswith('-plan'):
                        return self.reply(200,scenario(data,extracted,request['edits']))
                    output,result=scenario(data,extracted,request['edits'],export=True)
                    from change_preview import previews
                    return self.reply(200,{'pdf':base64.b64encode(output).decode(), 'highlighted':previews(data,output,result['changes']), **result})
                if self.path.endswith('-plan'):
                    return self.reply(200,plan(data,extracted,request['edits'],request['rules']))
                output,result=apply(data,extracted,request['edits'],request['rules'],request.get('allow_raster') is True)
                from change_preview import previews
                return self.reply(200,{'pdf':base64.b64encode(output).decode(), 'highlighted':previews(data,output,result['changes']), **result})
            if self.path == '/api/general/analyze':
                from general_finance import signed_extract
                return self.reply(200,signed_extract(data,request.get('locale','de'),int(request.get('rotation',0))))
            if self.path in ('/api/general/plan','/api/general/apply','/api/general/preview','/api/general/suggest','/api/general/dependencies'):
                from general_finance import validate_analysis,calculate,render_changes,preview_cell
                extracted=validate_analysis(data,request['analysis'])
                if self.path.endswith('/dependencies'):
                    from openrouter_dependencies import decide
                    return self.reply(200,decide(extracted,request['edits']))
                if self.path.endswith('/suggest'):
                    from ai_rules import suggest
                    return self.reply(200,suggest(extracted))
                if self.path.endswith('/preview'):
                    return self.reply(200,preview_cell(data,extracted,request['id']))
                if self.path.endswith('/plan'):
                    return self.reply(200,calculate(extracted,request['edits'],request['rules']))
                output,result=render_changes(data,extracted,request['edits'],request['rules'],request.get('allow_raster') is True)
                return self.reply(200,{'pdf':base64.b64encode(output).decode(),**result})
            if self.path == '/api/finance/analyze':
                from finance import analyze
                return self.reply(200, analyze(data))
            if self.path == '/api/finance/plan':
                from finance import plan
                return self.reply(200, plan(data, request['edits']))
            if self.path == '/api/finance/apply':
                from finance import apply
                output, changes = apply(data, request['edits'])
                png, pages = preview(output)
                return self.reply(200, {'pdf':base64.b64encode(output).decode(),'image':png,'pages':pages,'changes':changes})
            if self.path == '/api/finance/local-review':
                from local_review import review
                return self.reply(200, review(data))
            if self.path == '/api/text/select':
                return self.reply(200, select_text(data, page_number, request['region']))
            if self.path == '/api/ocr/preview':
                from scan_editor import preview_scan
                return self.reply(200, preview_scan(data, page_number, int(request.get('rotation', 0))))
            if self.path == '/api/ocr/find':
                from scan_editor import locate_document
                return self.reply(200, locate_document(data, request['old'].strip(), int(request.get('rotation', 0))))
            if self.path == '/api/ocr/selection':
                from scan_editor import preview_selection
                return self.reply(200, preview_selection(data, request['selection']))
            if self.path == '/api/ocr/region':
                from scan_editor import locate_region
                return self.reply(200, locate_region(data, page_number, int(request.get('rotation', 0)), request['region']))
            if self.path == '/api/ocr/edit':
                from scan_editor import edit_scan
                return self.reply(200, edit_scan(data, request['new'].strip(), request['selection']))
            if self.path == '/api/preview':
                png, pages = preview(data, page_number)
                return self.reply(200, {'image': png, 'pages': pages})
            if self.path == '/api/edit':
                output, count, pages_changed = edit_pdf(data, request['old'].strip(), request['new'].strip(), int(request.get('occurrence', 0)))
                png, pages = preview(output, pages_changed[0])
                return self.reply(200, {'pdf': base64.b64encode(output).decode(), 'image': png, 'pages': pages, 'page': pages_changed[0], 'count': count, 'changed_pages': pages_changed})
            self.reply(404, {'error': 'Not found'})
        except (ValueError, KeyError, TypeError, pymupdf.FileDataError) as exc:
            self.reply(400, {'error': str(exc)})
        except Exception:
            self.reply(500, {'error': 'Unable to process this PDF.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PDF editor web server')
    parser.add_argument('--host', default='127.0.0.1', help='Listen address; use 0.0.0.0 for LAN access')
    parser.add_argument('--port', type=int, default=8000, help='Internal listening port')
    parser.add_argument('--allowed-origin', action='append', default=[], help='Exact browser origin, such as https://pdf.example.com (repeatable)')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    Handler.allowed_origins = {f'http://127.0.0.1:{args.port}', f'http://localhost:{args.port}'} | {value.rstrip('/') for value in args.allowed_origin}
    print(f'PDF editor listening on {args.host}:{args.port} (Ctrl+C to stop)', flush=True)
    if args.host == '0.0.0.0':
        print('Open using this computer\'s LAN IP or the configured domain, not 0.0.0.0.', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
