"""AI-researched realistic scenario: after the user's own change, GPT looks up
real economic figures for the document's year (web search) and proposes a
percentage change for every other account in the edited period columns.
Python turns the percentages into amounts with Decimal and recalculates every
total with the verified format rules."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import pymupdf

from general_finance import parse_amount, format_amount
from scan_editor import _signature
from openrouter_dependencies import ENDPOINT, cell_state
from ai_models import selected_model, model_payload
from finance_workflow import plan, apply

MAX_CHANGE = Decimal(100)   # safeguard against absurd proposals, in percent
MAX_EDITS = 200
NOTE = ('AI SCENARIO: the other accounts were proposed by AI from web-researched figures for the document period. '
        'Figures and sources come from the AI and must be checked. Python calculated every amount and recalculated all totals '
        'with the verified report formulas. Planning scenario, not actual bookkeeping.')

PROMPTS = Path(__file__).resolve().parent / 'prompts'


def load_prompt(name, language):
    """Prompts live in prompts/*.txt so they can be read and edited directly;
    the file is read on every call, so edits apply without a restart."""
    text = (PROMPTS / name).read_text(encoding='utf-8')
    return text.strip().replace('{language}', 'German' if language == 'de' else 'English')


def _record(log, step, file, web, system, user):
    """Keep the exact prompts sent to the AI so the UI can show them."""
    if log is not None:
        log.append({'step': step, 'file': file, 'model': selected_model(), 'web_search': web, 'system': system, 'user': user})


def supported(statement):
    return statement.get('profile') in ('buhl_bwa', 'datev_cash_basis') or statement.get('export_mode') == 'direct'


def _key():
    key = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPEN_ROUTER_KEY')
    if not key:raise ValueError('Configure the OpenRouter key and restart to use the AI scenario.')
    return key


def _error_reason(exc):
    """OpenRouter's own explanation of a failed request, shortened for the UI."""
    try:
        error = json.loads(exc.read(20000))['error']
        details = [e.get('raw') or e.get('message', '') for e in (error.get('metadata') or {}).get('previous_errors') or []]
        raw = (error.get('metadata') or {}).get('raw')
        return ' '.join(str(v) for v in [error.get('message', ''), raw, *details] if v)[:400]
    except Exception:
        return ''


def _call(payload, timeout=90, attempts=3):
    """Each call normally answers in 3-15 seconds; a stuck or overloaded
    request is retried instead of failing the whole scenario."""
    body = json.dumps(model_payload(payload)).encode()
    for attempt in range(attempts):
        request = urllib.request.Request(ENDPOINT, data=body,
            headers={'Authorization': 'Bearer ' + _key(), 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:raw = response.read(2*1024*1024+1)
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (408, 429, 500, 502, 503, 504) and attempt < attempts-1:
                time.sleep(2*(attempt+1));continue
            reason = _error_reason(exc)
            if 'rate-limited' in reason or exc.code == 429:
                raise ValueError(f'{payload["model"]} is temporarily rate-limited by its provider. Choose another AI model or retry in a few minutes. No PDF was changed.') from None
            raise ValueError(f'OpenRouter AI scenario failed (HTTP {exc.code}). Check credits and model access. No PDF was changed.'
                             + (f' Reason: {reason}' if reason else '')) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt < attempts-1:continue
            raise ValueError('OpenRouter AI scenario timed out or could not connect. No PDF was changed.') from None
    if len(raw) > 2*1024*1024:raise ValueError('Oversized AI response.')
    answer = json.loads(raw)['choices'][0]
    if answer.get('finish_reason') != 'stop':raise ValueError('Incomplete AI response.')
    return answer['message']


def _percent(value):
    if not isinstance(value, str) or len(value) > 12:raise ValueError('AI percentages must be short decimal strings.')
    try:result = Decimal(value.strip().replace(',', '.').rstrip('%'))
    except InvalidOperation:raise ValueError('AI returned an invalid percentage.') from None
    if not result.is_finite() or abs(result) > MAX_CHANGE:raise ValueError('AI proposed a change outside the ±100 % safeguard.')
    return result


def _sources(message):
    """Only pages the web search actually returned; tracking parameters removed."""
    result = []
    for a in message.get('annotations') or []:
        citation = a.get('url_citation') if isinstance(a, dict) else None
        url = citation.get('url') if isinstance(citation, dict) else None
        if not isinstance(url, str) or len(url) > 500 or not re.fullmatch(r'https://[^\s<>"]+', url):continue
        url = re.sub(r'([?&])utm_source=openai(&|$)', lambda m: m.group(1) if m.group(2) else '', url).rstrip('?&')
        if url not in [v['url'] for v in result]:result.append({'url': url, 'title': str(citation.get('title') or url)[:160]})
    return result[:20]


def document_context(data):
    """Header text tells the AI the company, period and year."""
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        return ' '.join(doc[0].get_text().split())[:1500]


def targets(statement, edits):
    """Editable accounts in the edited period columns, minus the user's own
    inputs and year-to-date partners that follow their month automatically."""
    cells = {c['id']: c for c in statement['cells']}
    explicit = {e['id'] for e in edits}
    columns = {cells[i].get('column_index') for i in explicit}
    month_of = {a: m for m, a in statement.get('period_pairs', [])}
    result = []
    for c in statement['cells']:
        if c.get('editable') is not True or c['id'] in explicit or c.get('column_index') not in columns:continue
        month = month_of.get(c['id'])
        if month and cells[month].get('column_index') in columns:continue  # follows its month
        result.append(c)
    return result


def research(context, statement, language, log=None):
    """Web search for real figures of the document's year and region. A
    second, structured step may cite only pages the search returned."""
    labels = sorted({c.get('label') or c['context'] for c in statement['cells'] if c.get('editable') is True})[:80]
    prompt = load_prompt('scenario_research.txt', language)
    user = 'Document header: ' + context + '\nAccount labels: ' + '; '.join(labels)
    _record(log, '1. Web research', 'prompts/scenario_research.txt', True, prompt, user)
    found = _call({'model': selected_model(), 'temperature': 0, 'max_tokens': 3000, 'plugins': [{'id': 'web', 'max_results': 8}],
        'messages': [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': user}]})
    if log:log[-1]['response'] = str(found.get('content', ''))[:20000]
    sources = _sources(found)
    if not sources:raise ValueError('The web search returned no sources. Try again later; no PDF was changed.')
    item = {'type': 'object', 'properties': {
        'id': {'type': 'string'}, 'name': {'type': 'string'}, 'change_percent': {'type': 'string'},
        'period': {'type': 'string'}, 'source': {'type': 'integer', 'enum': list(range(1, len(sources)+1))}},
        'required': ['id', 'name', 'change_percent', 'period', 'source'], 'additionalProperties': False}
    schema = {'type': 'object', 'properties': {
        'document_year': {'type': 'string'}, 'region': {'type': 'string'}, 'industry': {'type': 'string'},
        'indicators': {'type': 'array', 'items': item}},
        'required': ['document_year', 'region', 'industry', 'indicators'], 'additionalProperties': False}
    extract = load_prompt('scenario_extract.txt', language)
    listing = '\n'.join(f"[{i}] {v['title']} {v['url']}" for i, v in enumerate(sources, 1))
    request = ('Document header: ' + context[:600] + '\n\nResearch text:\n'
               + str(found.get('content', ''))[:12000] + '\n\nSources:\n' + listing)
    _record(log, '2. Extract figures with sources', 'prompts/scenario_extract.txt', False, extract, request)
    message = _call({'model': selected_model(), 'temperature': 0, 'max_tokens': 3000,
        'messages': [{'role': 'system', 'content': extract}, {'role': 'user', 'content': request}],
        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'researched_indicators', 'strict': True, 'schema': schema}},
        'provider': {'require_parameters': True}})
    try:
        generated = json.loads(message['content'])
        indicators = []
        for v in generated['indicators'][:12]:
            if type(v['source']) is not int or not 1 <= v['source'] <= len(sources):continue
            try:change = _percent(v['change_percent'])
            except ValueError:continue
            # Models sometimes reuse an id (two "fuel" figures) or add capitals;
            # normalize and number repeats instead of dropping every figure.
            base = re.sub(r'[^a-z0-9_]+', '_', str(v['id']).lower()).strip('_')[:36] or 'figure'
            key, n = base, 1
            while key in {i['id'] for i in indicators}:n += 1;key = f'{base}_{n}'
            source = sources[v['source']-1]
            indicators.append({'id': key, 'name': v['name'][:160], 'change_percent': str(change), 'period': v['period'][:80],
                               'source_title': source['title'], 'source_url': source['url']})
        if not indicators:raise ValueError('No usable researched figures with sources.')
        return {'document_year': generated['document_year'][:40], 'region': generated['region'][:80],
                'industry': generated['industry'][:160], 'indicators': indicators}
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError, IndexError) as exc:
        raise ValueError('AI research response failed validation: ' + str(exc)) from None


def propose(statement, edits, cells, found, language, log=None):
    """The AI decides what drives each account; it does no arithmetic."""
    by_id = {c['id']: c for c in statement['cells']}
    ids = [c['id'] for c in cells]
    user_ids = [e['id'] for e in edits]
    indicator_ids = [v['id'] for v in found['indicators']]
    item = {'type': 'object', 'properties': {
        'revenue': {'type': 'boolean'}, 'driver': {'type': 'string', 'enum': ['sales', 'indicator', 'none']},
        'indicators': {'type': 'array', 'items': {'type': 'string', 'enum': indicator_ids}},
        'reason': {'type': 'string'}}, 'required': ['revenue', 'driver', 'indicators', 'reason'], 'additionalProperties': False}
    flag = {'type': 'object', 'properties': {'revenue': {'type': 'boolean'}}, 'required': ['revenue'], 'additionalProperties': False}
    schema = {'type': 'object', 'properties': {
        'user_changes': {'type': 'object', 'properties': {i: flag for i in user_ids}, 'required': user_ids, 'additionalProperties': False},
        'accounts': {'type': 'object', 'properties': {i: item for i in ids}, 'required': ids, 'additionalProperties': False},
        'summary': {'type': 'string'}}, 'required': ['user_changes', 'accounts', 'summary'], 'additionalProperties': False}
    state = {'locale': statement['locale'], 'report_type': statement.get('report_type'),
        'document_year': found['document_year'], 'region': found['region'], 'industry': found['industry'],
        'researched_indicators': found['indicators'],
        'user_changes': [{'id': e['id'], 'label': by_id[e['id']].get('label') or by_id[e['id']]['context'],
                          'column': by_id[e['id']].get('column', ''), 'original': by_id[e['id']]['text'], 'replacement': e['value']} for e in edits],
        'accounts': [{'id': c['id'], 'label': c.get('label') or c['context'], 'column': c.get('column', ''), 'amount': c['text']} for c in cells]}
    prompt = load_prompt('scenario_drivers.txt', language)
    payload = {'model': selected_model(), 'temperature': 0, 'max_tokens': 12000,
        'messages': [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': json.dumps(state, ensure_ascii=False)}],
        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'realistic_scenario', 'strict': True, 'schema': schema}},
        'provider': {'require_parameters': True}}
    _record(log, '3. Driver per account', 'prompts/scenario_drivers.txt', False, prompt, payload['messages'][1]['content'])
    if len(json.dumps(payload)) > 350000:raise ValueError('The AI scenario exceeds the AI context budget. No rows were silently omitted.')
    try:
        generated = json.loads(_call(payload)['content'])
        accounts, flags = generated['accounts'], generated['user_changes']
        if set(accounts) != set(ids) or set(flags) != set(user_ids):raise ValueError('Unknown or missing account.')
        result = {}
        for i in ids:
            v = accounts[i]
            chosen = [k for k in dict.fromkeys(v['indicators']) if k in indicator_ids]
            if v['driver'] not in ('sales', 'indicator', 'none') or (v['driver'] == 'indicator' and not chosen):
                raise ValueError('An indicator-driven account must name a researched indicator.')
            if not isinstance(v['reason'], str) or not v['reason'].strip():raise ValueError('Missing reason.')
            result[i] = {'revenue': v['revenue'] is True, 'driver': v['driver'],
                         'indicators': chosen if v['driver'] == 'indicator' else [], 'reason': v['reason'].strip()[:400]}
        return result, {i: flags[i]['revenue'] is True for i in user_ids}, str(generated['summary'])[:2000]
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise ValueError('AI scenario response failed validation: ' + str(exc)) from None


def sales_changes(statement, edits, proposals, user_revenue):
    """Exact total-revenue change per period column caused by the user's edits, in percent."""
    cells = {c['id']: c for c in statement['cells']}
    result = {}
    for column in {cells[e['id']].get('column_index') for e in edits}:
        old = new = Decimal(0)
        for e in edits:
            c = cells[e['id']]
            if c.get('column_index') == column and user_revenue[e['id']]:
                old += Decimal(c['value']);new += parse_amount(e['value'], statement['locale'])[0]
        for key, p in proposals.items():
            if p['revenue'] and cells[key].get('column_index') == column:
                old += Decimal(cells[key]['value']);new += Decimal(cells[key]['value'])
        change = (new / old - 1) * 100 if old else Decimal(0)
        result[column] = max(Decimal(-100), min(Decimal(300), change))
    return result


def preview(data, statement, edits, language='en'):
    if language not in ('en', 'de'):raise ValueError('Choose English or German.')
    if not supported(statement):raise ValueError('The AI scenario needs a recognized BWA layout (DATEV, Buhl or cash-basis BWA). SuSa movements need balanced counterpart bookings and are not supported.')
    if statement.get('profile') and not statement.get('verified'):raise ValueError('Source discrepancies must be resolved before the AI scenario.')
    if not isinstance(edits, list) or not 1 <= len(edits) <= 30 or any(not isinstance(e, dict) for e in edits):raise ValueError('Enter at least one changed amount first.')
    cells = {c['id']: c for c in statement['cells']}
    if len({e.get('id') for e in edits}) != len(edits):raise ValueError('Each requested input must be distinct.')
    for e in edits:
        c = cells.get(e.get('id'))
        if not c or c.get('editable') is not True:raise ValueError('Choose an independent input, not a total or percentage.')
        value, suffix = parse_amount(e.get('value', ''), statement['locale'])
        if suffix != c['suffix']:raise ValueError('Preserve the original S/H direction.')
    accounts = targets(statement, edits)
    if not accounts:raise ValueError('No other accounts in this period column can be adjusted.')
    prompts = []
    found = research(document_context(data), statement, language, prompts)
    proposals, user_revenue, summary = propose(statement, edits, accounts, found, language, prompts)
    sales = sales_changes(statement, edits, proposals, user_revenue)
    indicators = {v['id']: v for v in found['indicators']}
    merged = {e['id']: e['value'] for e in edits}
    rows = []
    for c in accounts:
        p = proposals[c['id']]
        change = Decimal(0)
        if p['driver'] == 'sales':change = sales[c.get('column_index')]
        if p['driver'] == 'indicator':
            change = sum((Decimal(indicators[k]['change_percent']) for k in p['indicators']), Decimal(0)) / len(p['indicators'])
        change = change.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        baseline = Decimal(c['value'])
        new = (baseline * (1 + change / 100)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        if c['suffix'] and new < 0:new = Decimal(0)
        if new != baseline:merged[c['id']] = format_amount(new, statement['locale'], c['suffix'])
        rows.append({'id': c['id'], 'context': c['context'], 'before': c['text'], 'after': format_amount(new, statement['locale'], c['suffix']),
                     'change_percent': str(change), 'driver': p['driver'], 'indicators': [indicators[k]['name'] for k in p['indicators']],
                     'reason': p['reason']})
    expanded = [{'id': k, 'value': v} for k, v in merged.items() if parse_amount(v, statement['locale'])[0] != Decimal(cells[k]['value'])]
    if not expanded:raise ValueError('No amounts changed.')
    if len(expanded) > MAX_EDITS:raise ValueError('The AI scenario exceeds the bounded input limit.')
    rules = statement.get('profile_rules', statement.get('candidate_rules', []))
    calculated = plan(data, statement, expanded, rules, MAX_EDITS)
    proposal = {'kind': 'ai_realistic_scenario', 'source_signature': _signature(statement), 'edits': expanded,
                'model': selected_model(), 'research': found}
    columns = {cells[e['id']].get('column_index'): cells[e['id']].get('column', '') for e in edits}
    return {**calculated, 'accounts': rows, 'research': found, 'summary': summary, 'note': NOTE, 'model': selected_model(), 'prompts': prompts,
            'sales_change': [{'column': columns[k], 'change_percent': str(v.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))} for k, v in sales.items()],
            'scenario': {'proposal': proposal, 'signature': _signature(proposal)}}


def export(data, statement, scenario, reviewed=False, allow_raster=False):
    if reviewed is not True:raise ValueError('Review the AI figures, sources and proposed amounts before creating the PDF.')
    if not isinstance(scenario, dict) or not isinstance(scenario.get('proposal'), dict) or not isinstance(scenario.get('signature'), str):
        raise ValueError('Invalid AI scenario preview.')
    proposal = scenario['proposal']
    if (not hmac.compare_digest(_signature(proposal), scenario['signature']) or proposal.get('source_signature') != _signature(statement)
            or proposal.get('kind') != 'ai_realistic_scenario'):
        raise ValueError('AI scenario preview is invalid or belongs to another analysis. Preview the scenario again.')
    rules = statement.get('profile_rules', statement.get('candidate_rules', []))
    output, result = apply(data, statement, proposal['edits'], rules, allow_raster, MAX_EDITS)
    return output, {**result, 'note': NOTE, 'simulation': True}
