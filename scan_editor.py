"""OCR-assisted editing of a single-image scanned page."""
import base64
import hashlib
import hmac
import io
import json
import math
import re
import secrets
import threading
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

_secret = secrets.token_bytes(32)
_lock = threading.Lock()
_engine = None


def _image(doc, page_number, rotation):
    if rotation not in (0, 90, 180, 270) or not 1 <= page_number <= len(doc):
        raise ValueError('Invalid page or OCR rotation.')
    page = doc[page_number - 1]
    images = page.get_images(full=True)
    if page.get_text().strip() or len(images) != 1 or images[0][1]:
        raise ValueError('OCR editing supports pages with one scanned image and no text or image mask.')
    xref = images[0][0]
    if len(page.get_image_rects(xref)) != 1:
        raise ValueError('Repeated page images are unsupported.')
    if any(xref in [item[0] for item in other.get_images()] for other in doc if other.number != page.number):
        raise ValueError('This image is shared by multiple pages; editing is unsupported.')
    image = Image.open(io.BytesIO(doc.extract_image(xref)['image'])).convert('RGB')
    if image.width * image.height > 25_000_000:
        raise ValueError('Scan exceeds the 25 megapixel limit.')
    return page, xref, image.rotate(-rotation, expand=True)


def _signature(candidate):
    return hmac.new(_secret, json.dumps(candidate, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def _preview(image):
    image = image.copy()
    image.thumbnail((1600, 1600))
    output = io.BytesIO(); image.save(output, format='PNG')
    return base64.b64encode(output.getvalue()).decode()


def locate_scan(data, old, page_number=1, rotation=0):
    global _engine
    old = old.strip()
    if not old or any(c in old for c in '\r\n\t'):
        raise ValueError('Enter the exact text or value to find.')
    numeric_only = bool(re.fullmatch(r'-?\d+(?:[.,]\d+)*', old))
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        _, _, image = _image(doc, page_number, rotation)
        page_count = len(doc)
    # Serialise model execution so concurrent requests do not overload the CPU.
    with _lock:
        if _engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError:
                raise ValueError('Install the OCR dependencies from requirements.txt first.')
            _engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2)
        results, _ = _engine(np.array(image))
    matches = []
    annotated = image.copy(); draw = ImageDraw.Draw(annotated)
    for box, text, score in results or []:
        text = text.strip()
        # Keep accounting S/H markers; never use fuzzy number matching.
        pattern = re.escape(old) + (r'\s*[SH]?' if numeric_only else '')
        if not re.fullmatch(pattern, text) or score < 0.85:
            continue
        xs = [point[0] for point in box]; ys = [point[1] for point in box]
        rect = [max(0, math.floor(min(xs))), max(0, math.floor(min(ys))), min(image.width, math.ceil(max(xs))), min(image.height, math.ceil(max(ys)))]
        if rect[2]-rect[0] <= rect[3]-rect[1]:
            continue  # Require upright horizontal text; user can rotate the OCR image.
        candidate = {'digest': hashlib.sha256(data).hexdigest(), 'old': old, 'page': page_number, 'rotation': rotation, 'box': rect, 'text': text, 'score': round(float(score), 4)}
        matches.append({'candidate': candidate, 'signature': _signature(candidate)})
        draw.rectangle(rect, outline='red', width=4)
        draw.text((rect[0], max(0, rect[1]-22)), str(len(matches)), fill='red')
    if not matches:
        raise ValueError('No confident exact OCR match. Check the value, page, or image rotation; OCR may misread scans.')
    return {'matches': matches, 'image': _preview(annotated), 'pages': page_count, 'page': page_number}


def preview_scan(data, page_number=1, rotation=0):
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        _, _, image = _image(doc, page_number, rotation)
        return {'image': _preview(image), 'pages': len(doc), 'page': page_number}


def edit_scan(data, new, signed_candidate):
    candidate = signed_candidate['candidate']
    if not hmac.compare_digest(_signature(candidate), signed_candidate['signature']):
        raise ValueError('Invalid OCR selection. Find the value again.')
    if candidate['digest'] != hashlib.sha256(data).hexdigest():
        raise ValueError('PDF changed. Find the value again.')
    old = candidate['old']
    new = new.strip()
    if not new or new == old or any(c in new for c in '\r\n\t'):
        raise ValueError('Enter different, non-empty single-line replacement text.')
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        page, xref, image = _image(doc, candidate['page'], candidate['rotation'])
        x0, y0, x1, y1 = candidate['box']
        replacement = new
        if re.fullmatch(r'-?\d+(?:[.,]\d+)*', old) and re.fullmatch(r'-?\d+(?:[.,]\d+)*', new):
            replacement += candidate['text'][len(old):]
        fonts = [Path('C:/Windows/Fonts/arial.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('/System/Library/Fonts/Supplemental/Arial.ttf')]
        font_path = next((str(p) for p in fonts if p.is_file()), None)
        if not font_path:
            raise ValueError('No suitable font found. Install Arial or DejaVu Sans.')
        width, height = x1-x0, y1-y0
        font = ImageFont.truetype(font_path, max(1, height))
        for size in range(max(1, height*2), 0, -1):
            font = ImageFont.truetype(font_path, size)
            bounds = font.getbbox(replacement)
            if bounds[2]-bounds[0] <= width and bounds[3]-bounds[1] <= height:
                break
        if size < 8:
            raise ValueError('Replacement is too long to remain legible in the selected region.')
        # Use local scan background; only selected pixels are replaced.
        region = np.array(image.crop((x0, y0, x1, y1)))
        background = tuple(int(v) for v in np.percentile(region.reshape(-1, 3), 85, axis=0))
        foreground = tuple(int(v) for v in np.percentile(region.reshape(-1, 3), 10, axis=0))
        patch = Image.new('RGB', (width, height), background)
        ImageDraw.Draw(patch).text((width-(bounds[2]-bounds[0])-bounds[0], (height-(bounds[3]-bounds[1]))//2-bounds[1]), replacement, font=font, fill=foreground)
        image.paste(patch, (x0, y0))
        changed_preview = _preview(image)
        restored = image.rotate(candidate['rotation'], expand=True)
        buffer = io.BytesIO(); restored.save(buffer, format='PNG')
        page.replace_image(xref, stream=buffer.getvalue())
        output = doc.tobytes(garbage=3, deflate=True)
        return {'pdf': base64.b64encode(output).decode(), 'image': changed_preview, 'pages': len(doc), 'page': candidate['page'], 'count': 1, 'changed_pages': [candidate['page']], 'scan': True}
