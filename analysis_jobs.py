"""Short polling requests for long OCR/AI intake, with bounded in-memory jobs."""
from concurrent.futures import ThreadPoolExecutor
import secrets
import threading
import time

_pool = ThreadPoolExecutor(max_workers=2)
_jobs = {}
_lock = threading.Lock()

def start(work):
    with _lock:
        now=time.monotonic()
        for key,(created,future) in list(_jobs.items()):
            if future.done() and now-created>1800:
                del _jobs[key]
        if sum(not f.done() for _,f in _jobs.values()) >= 4:
            raise ValueError('Document analysis is busy. Please retry shortly.')
        while len(_jobs)>=8:
            completed=next((k for k,(_,f) in _jobs.items() if f.done()),None)
            if completed is None:break
            del _jobs[completed]
        token=secrets.token_urlsafe(32)
        _jobs[token]=(now,_pool.submit(work))
        return {'job':token,'state':'processing'}

def poll(token):
    with _lock:
        entry=_jobs.get(token) if isinstance(token,str) else None
    if not entry:
        raise ValueError('Analysis job expired. Select the document again.')
    future=entry[1]
    if not future.done():return {'state':'processing'}
    try:
        return {'state':'complete','result':future.result()}
    except Exception as exc:
        raise ValueError(str(exc)) from None

def analyze_document(data,locale,rotation):
    from finance_workflow import analyze
    from openrouter_dependencies import inspect_document
    from scan_editor import _signature
    result=analyze(data,locale,rotation)
    statement=result['analysis']['statement']
    inspection=inspect_document(statement)
    statement['report_type']=inspection['report_type']
    independent=set(inspection['independent_ids'])
    for cell in statement['cells']:
        cell['editable']=cell.get('editable') is not False and cell['id'] in independent
    statement['notes'].insert(0,inspection['report_type']+': '+inspection['summary'])
    statement['notes'].extend('AI uncertainty: '+item for item in inspection['uncertainties'])
    result['signature']=_signature(result['analysis'])
    result['inspection']=inspection
    return result
