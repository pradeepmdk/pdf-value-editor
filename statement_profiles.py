"""Explicit, source-validated layouts. Models never define these formulas."""
from decimal import Decimal, ROUND_HALF_UP
import re
import unicodedata
import pymupdf
from general_finance import extract, parse_amount, format_amount


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c) and c.isalnum())


def sum_rule(target, terms, reason='Printed subtotal', constant=None):
    rule={'target':target['id'],'terms':[{'source':c['id'],'sign':s} for c,s in terms], 'reason':reason}
    if constant is not None:rule['constant']=str(constant)
    return rule


def ratio_rule(target, numerator, denominator, absolute=False):
    return {'target':target['id'],'terms':[{'source':numerator['id'],'sign':1},{'source':denominator['id'],'sign':1}],
            'operation':'percentage','absolute_denominator':absolute,'reason':'Printed percentage (rounded to two decimals)'}


def evaluate(rule,values):
    if rule.get('operation')=='percentage':
        numerator,denominator=(values[t['source']] for t in rule['terms'])
        if rule.get('absolute_denominator'):denominator=abs(denominator)
        if not denominator:raise ValueError('A percentage denominator becomes zero; the printed numeric field cannot express an undefined ratio.')
        return (numerator*100/denominator).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    return sum((values[t['source']]*t['sign'] for t in rule['terms']),Decimal(rule.get('constant','0')))


def _order(rules):
    by_target={r['target']:r for r in rules}
    if len(by_target)!=len(rules):raise ValueError('Duplicate profile formula target.')
    result=[];active=set();done=set()
    def visit(key):
        if key in active:raise ValueError('Profile formula cycle.')
        if key in done:return
        active.add(key)
        for t in by_target[key]['terms']:
            if t['source'] in by_target:visit(t['source'])
        active.remove(key);done.add(key);result.append(by_target[key])
    for key in by_target:visit(key)
    return result


def validate(statement):
    values={c['id']:Decimal(c['value']) for c in statement['cells']}
    errors=[]
    for rule in _order(statement['profile_rules']):
        expected=evaluate(rule,values);printed=values[rule['target']]
        # Ratios are printed from rounded currency; a one-cent ratio difference
        # is documented. Additive currency relationships must match exactly.
        tolerance=Decimal('.01') if rule.get('operation')=='percentage' else Decimal(0)
        if abs(expected-printed)>tolerance:errors.append(f"{rule['target']}: printed {printed}, calculated {expected}")
    statement['discrepancies']=errors
    statement['verified']=not errors
    return statement


def calculate_profile(statement,edits):
    if not statement.get('verified'):raise ValueError('Source statement has unexplained discrepancies. '+ '; '.join(statement['discrepancies'][:5]))
    cells={c['id']:c for c in statement['cells']};original={key:Decimal(c['value']) for key,c in cells.items()};values=dict(original)
    if not isinstance(edits,list) or not 1<=len(edits)<=30 or len({e['id'] for e in edits})!=len(edits):raise ValueError('Provide one to thirty distinct input changes.')
    affected=set();explicit={e['id'] for e in edits}
    for edit in edits:
        c=cells.get(edit['id'])
        if not c or c.get('editable') is not True:raise ValueError('Select an independent input, not a percentage, subtotal or repeated report value.')
        value,suffix=parse_amount(edit['value'],statement['locale'])
        if suffix!=c['suffix']:raise ValueError('Preserve the printed S/H direction.')
        if suffix and value<0:raise ValueError('S/H balances must be non-negative magnitudes.')
        values[c['id']]=value
        if value!=original[c['id']]:affected.add(c['id'])
    # The monthly column is included in year-to-date. Retain the earlier months;
    # an explicit annual replacement takes precedence over propagation.
    for monthly,annual in statement.get('period_pairs',[]):
        if monthly in affected and annual not in explicit:
            values[annual]+=values[monthly]-original[monthly];affected.add(annual)
    for rule in _order(statement['profile_rules']):
        if any(t['source'] in affected for t in rule['terms']):
            value=evaluate(rule,values)
            if value!=values[rule['target']]:values[rule['target']]=value;affected.add(rule['target'])
    for debit,credit in statement.get('balance_checks',[]):
        if values[debit]!=values[credit]:raise ValueError('SuSa debit and credit totals would no longer balance. Add the corresponding debit/credit movement to the same batch; no counterpart booking is invented.')
    if any(values[key] for key in statement.get('zero_balance_checks',[])):
        raise ValueError('SuSa signed opening or closing grand totals would no longer balance. Add the corresponding balance correction to the same batch.')
    changes=[]
    for key,c in cells.items():
        if values[key]==original[key]:continue
        if c['suffix'] and values[key]<0:raise ValueError('Calculated balance crosses the original S/H direction. Review the account movements; no PDF was created.')
        changes.append({**c,'new':format_amount(values[key],statement['locale'],c['suffix']),
                        'reason':'Input edit' if key in explicit else 'Verified statement formula'})
    if not changes:raise ValueError('No amounts changed.')
    return {'changes':changes,'rules_checked':len(statement['profile_rules']), 'note':statement['profile_note']}


def recognize(data,locale='de',rotation=0):
    if locale!='de':return None
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        text=''.join(p.get_text() for p in doc)
    if 'BWA-Form: Einnahmen-Ausgaben-BWA' in text:
        return cash_basis(data)
    return None


def recognize_scan(statement):
    """ADDISON's six-column account report, after upright OCR."""
    items=statement.get('ocr_pages',{})
    text=' '.join(v['text'] for page in items.values() for v in page)
    keys=normalized(text)
    if all(k in keys for k in ('addison','monatsumsatz','jahresumsatz','anfangsbestand','saldo')):
        return addison_susa(statement)
    return None


def addison_susa(statement):
    rules=[];rows=[]
    for c in statement['cells']:c['editable']=False
    # The six amount columns are evenly spaced. Infer their right edges from
    # the actual page, not amount order (OCR can emit columns out of order).
    for page in range(1,statement['pages']+1):
        amounts=[c for c in statement['cells'] if c['page']==page]
        if not amounts:continue
        clusters=[]
        for x in sorted(c['box'][2] for c in amounts):
            cluster=next((g for g in clusters if abs(sum(g)/len(g)-x)<8),None)
            if cluster is None:cluster=[];clusters.append(cluster)
            cluster.append(x)
        if len(clusters)!=6:raise ValueError('SuSa OCR could not identify all six amount columns. Check scan orientation and quality.')
        edges=[sum(g)/len(g) for g in clusters]
        groups=[]
        for c in sorted(amounts,key=lambda c:sum(c['box'][1::2])/2):
            center=(c['box'][1]+c['box'][3])/2
            group=next((g for g in groups if abs((g[0]['box'][1]+g[0]['box'][3])/2-center)<4.5),None)
            if group is None:group=[];groups.append(group)
            group.append(c)
        for group in groups:
            label=max((c['label'] for c in group),key=len)
            # Crop-derived multiline labels are useful context, but must never
            # absorb another numeric row into this row's account identity.
            match=re.match(r'\s*(\d{3,4})(?!\d)',label)
            identity=match.group(1) if match else normalized(label)
            if not identity:raise ValueError('SuSa OCR row label is missing.')
            columns={}
            for c in group:
                col=min(range(6),key=lambda i:abs(c['box'][2]-edges[i]))
                if col in columns:raise ValueError('Ambiguous SuSa OCR row. Re-scan or choose the correct rotation.')
                columns[col]=c;c['row']=identity;c['column_index']=col
                c['column']=['Opening balance','Monthly debit','Monthly credit','Year-to-date debit','Year-to-date credit','Closing balance'][col]
                c['context']=label+' / '+c['column'];c['label']=label
            if len(columns)!=6:raise ValueError('SuSa OCR missed an amount in '+label+'. Re-scan the source; missing cells cannot be assumed to be zero.')
            if columns[0]['suffix'] not in ('S','H') or columns[5]['suffix'] not in ('S','H') or any(columns[i]['suffix'] for i in (1,2,3,4)):
                raise ValueError('SuSa debit/credit directions could not be read unambiguously in '+label)
            rows.append({'key':identity,'label':label,'account':bool(match),'cells':columns})
    if not rows or rows[-1]['key']!='gesamtsumme':raise ValueError('The SuSa grand total is missing from OCR.')
    account_rows=[];class_rows=[];segment=[];class_accounts=[];pairs=[]
    def direction(c):return -1 if c['suffix']=='H' else 1
    def total_rule(target,sources,col):
        return sum_rule(target,[(r['cells'][col],direction(r['cells'][col])*direction(target) if col in (0,5) else 1) for r in sources],'Account subtotal in the printed S/H direction')
    for r in rows:
        cols=r['cells']
        if r['account']:
            account_rows.append(r);class_accounts.append(r);segment.append(r)
            sign=direction(cols[5])
            rules.append(sum_rule(cols[5],[(cols[0],direction(cols[0])*sign),(cols[3],sign),(cols[4],-sign)],'Opening signed balance plus year-to-date debit minus year-to-date credit'))
            for i in range(5):cols[i]['editable']=cols[i].get('confidence',0)>=.85
            pairs.extend([[cols[1]['id'],cols[3]['id']],[cols[2]['id'],cols[4]['id']]])
        else:
            if r['key']=='gesamtsumme':sources=class_rows
            elif r['key'].startswith('summeklasse'):
                sources=class_accounts;class_rows.append(r);class_accounts=[];segment=[]
            else:sources=segment;segment=[]
            if not sources:raise ValueError('Unknown or empty SuSa subtotal: '+r['label'])
            for col in range(6):rules.append(total_rule(cols[col],sources,col))
    statement.update(profile='addison_susa',report_type='SuSa',export_mode='image',profile_rules=rules,period_pairs=pairs,
        balance_checks=[[rows[-1]['cells'][1]['id'],rows[-1]['cells'][2]['id']],[rows[-1]['cells'][3]['id'],rows[-1]['cells'][4]['id']]],
        zero_balance_checks=[rows[-1]['cells'][0]['id'],rows[-1]['cells'][5]['id']],
        profile_note='ADDISON SuSa: signed opening balances, monthly and year-to-date debit/credit, closing balances, account subtotals, class totals and grand totals verified. Monthly edits propagate the same delta to year-to-date. Debit/credit totals must remain balanced; provide counterpart movements explicitly. Changed scanned pages use image export with approximate fonts; original orientation and untouched pages are preserved.')
    statement['notes'].append(statement['profile_note'])
    return validate(statement)


def _rows(statement,page):
    groups=[]
    for c in sorted((c for c in statement['cells'] if c['page']==page),key=lambda c:(c['box'][1],c['box'][0])):
        group=next((g for g in groups if abs(g[0]['box'][1]-c['box'][1])<2),None)
        if group is None:group=[];groups.append(group)
        group.append(c)
    return groups


def cash_basis(data):
    statement=extract(data,'de');rules=[];tables={}
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        # Six calculation pages are followed by a variable number of ledger
        # snapshots. Ledger pagination depends on the accounts in the period.
        if len(doc)<6 or any(p.rect.width<800 or p.rotation for p in list(doc)[:6]):raise ValueError('Unsupported cash-basis BWA page layout.')
        for i,heading in enumerate(('Kurzfristige Erfolgsrechnung','Kurzfristige Erfolgsrechnung','Vorjahresvergleich','Vorjahresvergleich','3-Jahresvergleich','3-Jahresvergleich')):
            if heading not in doc[i].get_text():raise ValueError('Cash-basis report pages are missing or reordered.')
    anchors={1:[281.7,334.7,387.5,440.6,589.4,642.4,695.2,748.0],2:[281.7,334.7,387.5,440.6,589.4,642.4,695.2,748.0],
             3:[271.4,357.1,442.5,493.4,579.1,664.7,750.2,801.1],4:[271.4,357.1,442.5,493.4,579.1,664.7,750.2,801.1],
             5:[264.2,342.9,421.4,499.9,547.9,626.6,674.6,753.1,801.1],6:[264.2,342.9,421.4,499.9,547.9,626.6,674.6,753.1,801.1]}
    for c in statement['cells']:c['editable']=False
    for page in range(1,7):
        table={}
        for group in _rows(statement,page):
            key=normalized(group[0]['label'])
            if key in table:raise ValueError('Ambiguous duplicate cash-basis row.')
            row={}
            for c in group:
                column=min(range(len(anchors[page])),key=lambda j:abs(c['box'][2]-anchors[page][j]))
                if abs(c['box'][2]-anchors[page][column])>1 or column in row:raise ValueError('Cash-basis amount is not aligned with its expected column.')
                row[column]=c;c['row']=key;c['column_index']=column
                c['context']=c['label']+' / '+('Month' if column==0 else 'Year to date' if (page<=2 and column==4) or (page>=5 and column==3) or (page in (3,4) and column==4) else 'Comparison / percentage')
                c['column']=c['context'].split(' / ')[-1]
            table[key]=row
        tables[page]=table
    first=tables[1];liquidity=tables[2]
    def row(table,name):
        key=normalized(name)
        if key not in table:raise ValueError('Missing cash-basis row: '+name)
        return table[key]
    costs=['Material-/Wareneinkauf','Fremdleistungen','Personalkosten','Raumkosten','Steuern/Versicherungen/Beiträge','Fahrzeugkosten','Werbe-/Reisekosten','Kosten Warenabgabe','Instandhaltung/Werkzeuge','Abschreibungen','Verschiedene Kosten']
    definitions=[('= Summe der Erlöse',[('betrieblicher Tätigkeit',1),('Sonstige Erlöse',1)]),
        ('Betriebseinnahmen',[('= Summe der Erlöse',1),('Umsatzsteuer',1),('Umsatzsteuer-Erstattung',1),('Erhaltene Anzahlungen',1),('- Zugang Forderungen',-1)]),
        ('= Summe der Kosten',[(k,1) for k in costs]),
        ('Betriebsausgaben',[('= Summe der Kosten',1),('Geleistete Anzahlungen',1),('Buchwert Anlagenabgänge',1),('Sonstige Aufwendungen',1),('Vorsteuer',1),('Umsatzsteuer-Zahlung',1),('- Verrechnete kalkulatorische Kosten',-1),('- Zugang Verbindlichkeiten',-1)]),
        ('Einnahmen-Ausgaben-BWA',[('Betriebseinnahmen',1),('Betriebsausgaben',-1)])]
    for col in (0,4):
        for target,terms in definitions:rules.append(sum_rule(row(first,target)[col],[(row(first,k)[col],s) for k,s in terms]))
        rules.append(sum_rule(row(liquidity,'Vorläufiges Ergebnis')[col],[(row(first,'Einnahmen-Ausgaben-BWA')[col],1)],'Same period result in liquidity report'))
        rules.append(sum_rule(row(liquidity,'(nicht kalkulatorisch)')[col],[(row(first,'Abschreibungen')[col],1)],'Non-imputed depreciation'))
        rules.append(sum_rule(row(liquidity,'Liquiditätsbeitrag Betrieb')[col],[(row(liquidity,k)[col],s) for k,s in [('Vorläufiges Ergebnis',1),('(nicht kalkulatorisch)',1),('+ Aufnahme Darlehen',1),('- Tilgung Darlehen',-1),('- Anlagenzugänge',-1),('+ Anlagenabgänge',1),('+/- Sonstige Posten',1)]]))
        rules.append(sum_rule(row(liquidity,'Liquiditätsbeitrag Privat')[col],[(row(liquidity,k)[col],s) for k,s in [('Privateinlagen',1),('+ Grundstücksertrag',1),('- Grundstücksaufwand',-1),('- Privatentnahmen',-1),('- Unentgeltliche Wertabgaben',-1),('- Privatsteuern',-1),('- Sonderausgaben/Spenden',-1),('- Außergewöhnliche Belastungen',-1)]]))
        rules.append(sum_rule(row(liquidity,'über-/-unterdeckung')[col],[(row(liquidity,'Liquiditätsbeitrag Betrieb')[col],1),(row(liquidity,'Liquiditätsbeitrag Privat')[col],1)]))
    for key,cells in first.items():
        for col,c in cells.items():
            if col in (1,2,3,5,6,7):
                amount_col=0 if col<4 else 4
                denominator={1:'= Summe der Erlöse',2:'= Summe der Kosten',3:'Betriebseinnahmen',5:'= Summe der Erlöse',6:'= Summe der Kosten',7:'Betriebseinnahmen'}[col]
                rules.append(ratio_rule(c,cells[amount_col],row(first,denominator)[amount_col]))
    # Repeated current values, absolute variance and comparison percentages.
    for page in range(3,7):
        master=first if page%2 else liquidity
        if set(tables[page])!=set(master):raise ValueError('Comparison rows do not match their source report.')
        for key,cells in tables[page].items():
            for current,source_col in ((0,0),(4 if page<5 else 3,4)):
                rules.append(sum_rule(cells[current],[(master[key][source_col],1)],'Repeated current period'))
            if page<5:
                for current,previous,difference,percent in ((0,1,2,3),(4,5,6,7)):
                    rules.append(sum_rule(cells[difference],[(cells[current],1),(cells[previous],-1)],'Current minus previous year'))
                    if percent in cells:rules.append(ratio_rule(cells[percent],cells[difference],cells[previous],True))
            elif page==5:
                for amount_col,percent_col,revenue_col in ((3,4,3),(5,6,5),(7,8,7)):
                    if percent_col in cells:rules.append(ratio_rule(cells[percent_col],cells[amount_col],row(tables[5],'= Summe der Erlöse')[revenue_col]))
    targets={r['target'] for r in rules};pairs=[]
    for table in (first,liquidity):
        for cells in table.values():
            for col in (0,4):cells[col]['editable']=cells[col]['id'] not in targets
            if cells[0]['editable'] and cells[4]['editable']:pairs.append([cells[0]['id'],cells[4]['id']])
    statement.update(profile='datev_cash_basis',report_type='BWA',export_mode='native',profile_rules=rules,period_pairs=pairs,
        profile_note='Cash-basis BWA totals, percentages, liquidity and comparison pages recalculated with Decimal. Monthly input changes also update year-to-date by the same delta. VAT and other taxes remain independent inputs. The attached SuSa ledger pages are source snapshots and remain unchanged; this is a report scenario, not a bookkeeping correction.')
    statement['notes'].append(statement['profile_note'])
    return validate(statement)
