"""Read-only reconciliation for the supported native DATEV SKR04 attachment."""
from decimal import Decimal
import re
import pymupdf


def ledger_checks(data, tables, normalize):
    accounts = {}
    attached = False
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        for page in list(doc)[6:]:
            if 'Summen und Salden (pro Monat)' not in page.get_text():
                continue
            attached = True
            if page.rotation or page.rect.width < 800:
                raise ValueError('Unsupported attached SuSa layout; reconciliation cannot be verified.')
            words = page.get_text('words')
            for word in words:
                if not (70 < word[0] < 75 and re.fullmatch(r'\d{3,4}', word[4])):
                    continue
                key = word[4]
                if key in accounts:
                    raise ValueError('Duplicate attached SuSa account; accounting versions may be mixed.')
                row = [w for w in words if abs(w[1]-word[1]) < 1]
                values = [Decimal(0)] * 4
                seen = set()
                for w in row:
                    if not re.fullmatch(r'-?[\d.]+,\d{2}', w[4]):
                        continue
                    edges = [459.9, 546.1, 632.5, 723.2]
                    col = min(range(4), key=lambda i: abs(w[2]-edges[i]))
                    if abs(w[2]-edges[col]) > 1:
                        continue
                    if col in seen:
                        raise ValueError('Ambiguous attached SuSa amount column.')
                    seen.add(col)
                    values[col] = Decimal(w[4].replace('.', '').replace(',', '.'))
                accounts[key] = values
    if not attached:
        return None
    if '4400' not in accounts or '3806' not in accounts:
        raise ValueError('Attached SuSa revenue/VAT accounts could not be verified.')
    # These mappings apply to this supported SKR04 report, not arbitrary charts.
    mappings = [
        ('betrieblicher Tätigkeit', ['4400'], -1),
        ('Umsatzsteuer', ['3806'], -1),
        ('Material-/Wareneinkauf', ['5400'], 1),
        ('Personalkosten', ['6020','6035','6036','6110','6120','6130','6199'], 1),
        ('Raumkosten', ['6310','6318','6325','6330','6335'], 1),
        ('Steuern/Versicherungen/Beiträge', ['6400','6430'], 1),
        ('Fahrzeugkosten', ['6530','6560'], 1),
        ('Werbe-/Reisekosten', ['6600','6643'], 1),
        ('Instandhaltung/Werkzeuge', ['6470'], 1),
        ('Abschreibungen', ['6220','6243'], 1),
        ('Verschiedene Kosten', ['6805','6815','6830','6850','6855'], 1),
        ('Vorsteuer', ['1401','1406'], 1),
    ]
    checks = []
    for label, numbers, direction in mappings:
        cells = tables[1][normalize(label)]
        for col, offset in ((0, 0), (4, 2)):
            expected = sum((direction*(accounts[n][offset]-accounts[n][offset+1])
                            for n in numbers if n in accounts), Decimal(0))
            checks.append({'id': cells[col]['id'], 'expected': str(expected),
                           'label': label + ' / ' + ('month' if col == 0 else 'year to date'),
                           'accounts': numbers})
    if not {'1600', '1800'}.issubset(accounts):
        raise ValueError('Attached cash/bank accounts could not be verified.')
    for col, offset in ((0, 0), (4, 2)):
        numbers = ['1370', '1460', '1461', '1600', '1800']
        expected = sum((accounts[n][offset]-accounts[n][offset+1]
                        for n in numbers if n in accounts), Decimal(0))
        checks.append({'id': tables[2][normalize('über-/-unterdeckung')][col]['id'],
                       'expected': str(expected), 'label': 'Liquidity / ' + ('month' if col == 0 else 'year to date'),
                       'accounts': numbers})
    return checks


def discrepancies(checks, values):
    return [f"Attached SuSa: {c['label']}: BWA {values[c['id']]}, accounts {c['expected']}"
            for c in checks if values[c['id']] != Decimal(c['expected'])]
