"""Preview-only change outlines. The downloadable PDF remains unmarked."""
import base64
import pymupdf

COLORS = {'Input edit': (0.9, 0.35, 0.05), 'dependent': (0.05, 0.45, 0.8)}


def _marked(data, changes, modified):
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        for change in changes:
            page = doc[change['page']-1]
            old = pymupdf.Rect(change['box'])
            rect = old
            if modified:
                # Replacement can be longer: locate its actual saved bounds rather
                # than reusing the original width or highlighting an equal value elsewhere.
                candidates = [pymupdf.Rect(w[:4]) * page.rotation_matrix for w in page.get_text('words') if w[4] == change['new']]
                candidates = [r for r in candidates if abs(r.y0-old.y0) < 1 and abs(r.x1-old.x1) < 1]
                if len(candidates) != 1:
                    raise ValueError('The modified amount could not be located uniquely for its highlighted preview.')
                rect = candidates[0]
            rect = pymupdf.Rect(rect.x0-1.5, rect.y0-1.5, rect.x1+1.5, rect.y1+1.5) * page.derotation_matrix
            mark = page.add_rect_annot(rect)
            mark.set_colors(stroke=COLORS.get(change['reason'], COLORS['dependent']))
            mark.set_border(width=1.3)
            mark.set_info(title='Changed input' if change['reason']=='Input edit' else 'Recalculated amount',
                          content=f"{change['text']} -> {change['new']}")
            mark.update()
        return doc.tobytes(garbage=3, deflate=True)


def previews(original, modified, changes):
    return {'before': base64.b64encode(_marked(original, changes, False)).decode(),
            'after': base64.b64encode(_marked(modified, changes, True)).decode(),
            'pages': sorted({c['page'] for c in changes})}
