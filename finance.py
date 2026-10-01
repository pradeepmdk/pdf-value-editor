"""Verified DATEV BWA 01 annual-layout calculation rules; no model arithmetic."""
from decimal import Decimal, InvalidOperation
import re

import pymupdf
from pdf_editor import TOKEN, BASE14, decode_literal

NUMBER = re.compile(r'^-?\d{1,3}(?:\.\d{3})*,\d{2}$')
PREFIXES = [
    ('revenue','umsatzerl'),('inventory','bestandsver'),('own_work','aktivierte eigen'),
    ('performance','gesamtleistung'),('materials','material-/'),('gross','rohertrag'),
    ('other_operating','so. betr.'),('operating_gross','betrieblicher rohertrag'),
    ('staff','personalkosten'),('rent','raumkosten'),('business_tax','betriebliche steuern'),
    ('insurance','versicherungen/'),('special','besondere kosten'),('vehicles','fahrzeugkosten'),
    ('travel','werbe-/'),('distribution','kosten warenabgabe'),('depreciation','abschreibungen'),
    ('repairs','reparatur/'),('other_costs','sonstige kosten'),('total_costs','gesamtkosten'),
    ('operating_result','betriebsergebnis'),('interest_expense','zinsaufwand'),
    ('other_neutral_expense','sonstiger neutraler aufwand'),('neutral_expense','neutraler aufwand'),
    ('interest_income','zinsertr'),('other_neutral_income','sonstiger neutraler ertrag'),
    ('imputed','verrechnete kalk.'),('neutral_income','neutraler ertrag'),
    ('unassigned','kontenklasse unbesetzt'),('pretax','ergebnis vor steuern'),
    ('income_tax','steuern einkommen'),('final','vorl')]
COSTS=['staff','rent','business_tax','insurance','special','vehicles','travel','distribution','depreciation','repairs','other_costs']
RULES={
    'performance':[('revenue',1),('inventory',1),('own_work',1)],
    'gross':[('performance',1),('materials',-1)],
    'operating_gross':[('gross',1),('other_operating',1)],
    'total_costs':[(key,1) for key in COSTS],
    'operating_result':[('operating_gross',1),('total_costs',-1)],
    'neutral_expense':[('interest_expense',1),('other_neutral_expense',1)],
    'neutral_income':[('interest_income',1),('other_neutral_income',1),('imputed',1)],
    'pretax':[('operating_result',1),('neutral_expense',-1),('neutral_income',1)],
    'final':[('pretax',1),('income_tax',-1)]}


def amount(text):
    if not NUMBER.fullmatch(text):
        raise ValueError('Use German EUR format, for example 62.315,78 (two decimal places).')
    return Decimal(text.replace('.','').replace(',','.'))


def fmt(value):
    return f'{value:,.2f}'.replace(',','X').replace('.',',').replace('X','.')


def analyze(data):
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        if len(doc)!=1 or doc.is_encrypted:
            raise ValueError('Automatic recalculation currently supports the one-page annual DATEV BWA 01 layout only.')
        page=doc[0]
        text=page.get_text()
        if 'DATEV-BWA' not in text or 'BWA Form 01' not in text:
            raise ValueError('Unsupported statement format. SuSa and scans need separately verified extraction and rules.')
        spans=[s for b in page.get_text('dict')['blocks'] for line in b.get('lines',[]) for s in line['spans']]
        numeric=[s['text'].strip() for s in spans if NUMBER.fullmatch(s['text'].strip())]
        stream_numbers=[]
        tokens=list(TOKEN.finditer(page.read_contents()))
        for i,t in enumerate(tokens):
            if t.group()==b'Tj' and i and tokens[i-1].group().startswith(b'('):
                value=decode_literal(tokens[i-1].group()[1:-1]).decode('cp1252').strip()
                if NUMBER.fullmatch(value):stream_numbers.append(value)
        if stream_numbers!=numeric:
            raise ValueError('PDF text positions do not match editable numeric operators; recalculation is unavailable.')
        groups={};index=0;headers=[]
        for span in spans:
            value=span['text'].strip(); rect=pymupdf.Rect(span['bbox'])*page.rotation_matrix
            if re.fullmatch(r'[A-Za-z]{3}/\d{4}',value):headers.append((rect.x0,value))
            item={'text':value,'rect':list(rect)}
            if NUMBER.fullmatch(value):item['index']=index;index+=1
            groups.setdefault(round(rect.y0,1),[]).append(item)
        columns=[v for _,v in sorted(headers)]+['Annual total']
        if len(columns)!=13:
            raise ValueError('Expected twelve monthly columns and one annual total.')
        rows=[];seen=set()
        for items in groups.values():
            cells=sorted([v for v in items if 'index' in v],key=lambda v:v['rect'][0])
            if not cells:continue
            if len(cells)!=13:raise ValueError('Ambiguous table row: expected thirteen amounts.')
            labels=[v for v in items if 'index' not in v and v['text'] and v['rect'][0]<cells[0]['rect'][0]]
            if len(labels)!=1:raise ValueError('Ambiguous row label.')
            label=labels[0]['text']; normalized=label.lower()
            key=next((key for key,prefix in PREFIXES if normalized.startswith(prefix)),None)
            if not key or key in seen:raise ValueError('Unknown or duplicate BWA row: '+label)
            seen.add(key)
            rows.append({'id':key,'label':label,'editable':key not in RULES and key!='unassigned','values':[c['text'] for c in cells],'cells':cells})
        if seen!={key for key,_ in PREFIXES}:raise ValueError('Missing BWA rows; rules cannot be applied safely.')
        values={r['id']:[amount(v) for v in r['values']] for r in rows}
        if any(values['unassigned']):raise ValueError('Nonzero unassigned accounts require an accountant-approved rule.')
        discrepancies=[]
        for row in rows:
            key=row['id']
            expected=sum(values[key][:12],Decimal(0))
            if expected!=values[key][12]:discrepancies.append({'row':row['label'],'column':'Annual total','printed':row['values'][12],'expected':fmt(expected)})
            if key in RULES:
                for col in range(13):
                    expected=sum((values[source][col]*sign for source,sign in RULES[key]),Decimal(0))
                    if expected!=values[key][col]:discrepancies.append({'row':row['label'],'column':columns[col],'printed':row['values'][col],'expected':fmt(expected)})
        return {'format':'DATEV BWA 01 annual','columns':columns,'rows':rows,'discrepancies':discrepancies,'verified':not discrepancies,'rule_source':'https://www.datev.de/dnlexom/v2/content/files/st2110633099_de.pdf'}


def plan(data, edits):
    statement=analyze(data)
    if not statement['verified']:
        raise ValueError('Source statement has existing discrepancies. Review and resolve them before automatic recalculation.')
    by_id={r['id']:r for r in statement['rows']}
    values={key:[amount(v) for v in row['values']] for key,row in by_id.items()}
    for edit in edits:
        key=edit['row'];col=int(edit['column'])
        if key not in by_id or not by_id[key]['editable'] or not 0<=col<12:
            raise ValueError('Edit a monthly input amount; calculated rows and annual totals are derived.')
        values[key][col]=amount(edit['value'].strip())
    for key,terms in RULES.items():
        values[key][:12]=[sum((values[source][col]*sign for source,sign in terms),Decimal(0)) for col in range(12)]
    for key in values:values[key][12]=sum(values[key][:12],Decimal(0))
    changes=[]
    for row in statement['rows']:
        key=row['id']
        for col in range(13):
            value=fmt(values[key][col]);old=row['values'][col]
            if value!=old:
                changes.append({'row':row['label'],'row_id':key,'column':statement['columns'][col],'column_index':col,'old':old,'new':value,'index':row['cells'][col]['index'],'rect':row['cells'][col]['rect'],'reason':'Annual sum' if col==12 else 'Dependent calculation' if key in RULES else 'Input edit'})
    if not changes:raise ValueError('No amounts changed.')
    return {'statement':statement,'changes':changes}


def apply(data, edits):
    calculated=plan(data,edits);changes={c['index']:c for c in calculated['changes']}
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        page=doc[0];stream=page.read_contents();tokens=list(TOKEN.finditer(stream));font=None;size=0;index=0;patches=[]
        fonts={f[4]:f[3] for f in page.get_fonts()}
        for i,token in enumerate(tokens):
            if token.group()==b'Tf':font=fonts.get(tokens[i-2].group().decode().lstrip('/'));size=float(tokens[i-1].group())
            if token.group()!=b'Tj' or not i or not tokens[i-1].group().startswith(b'('):continue
            literal=tokens[i-1];raw=decode_literal(literal.group()[1:-1]);value=raw.decode('cp1252').strip()
            if not NUMBER.fullmatch(value):continue
            change=changes.get(index);index+=1
            if not change:continue
            if font not in BASE14 or size<=0:raise ValueError('Unsupported amount font.')
            if value!=change['old']:raise ValueError('Amount mapping changed.')
            new=change['new'];old_width=pymupdf.get_text_length(value,fontname=BASE14[font],fontsize=size);new_width=pymupdf.get_text_length(new,fontname=BASE14[font],fontsize=size)
            if new_width>48:raise ValueError('New amount exceeds the available column width.')
            delta=old_width-new_width
            command=b'('+raw.replace(value.encode(),new.encode(),1)+b')Tj'
            if abs(delta)>1e-6:
                # This annual format positions each subsequent value with Td/Tm.
                next_ops=[t.group() for t in tokens[i+1:] if t.group() in (b'Tj',b'TJ',b'Td',b'TD',b'Tm',b'BT',b'ET')]
                if next_ops and next_ops[0] in (b'Tj',b'TJ'):raise ValueError('Chained text operators cannot be aligned safely.')
                command=f'{delta:.6f} 0 Td '.encode()+command+f' {-delta:.6f} 0 Td'.encode()
            patches.append((literal.start(),token.end(),command))
        if len(patches)!=len(changes):raise ValueError('Not all recalculated cells could be located.')
        for start,end,command in reversed(patches):stream=stream[:start]+command+stream[end:]
        refs=page.get_contents();doc.update_stream(refs[0],stream)
        for xref in refs[1:]:doc.update_stream(xref,b'')
        output=doc.tobytes(garbage=3,deflate=True)
    verified=analyze(output)
    if not verified['verified']:raise ValueError('Recalculated PDF failed verification.')
    return output,calculated['changes']
