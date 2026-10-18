"""Live bilingual OpenRouter summaries, with exact source-backed amounts."""
import json
from pathlib import Path
import time
import urllib.request

URL='http://127.0.0.1:8000'
ROOT=Path(__file__).resolve().parent.parent


def post(path,payload,binary=False):
    request=urllib.request.Request(URL+path,data=payload if binary else json.dumps(payload).encode(),headers={'Content-Type':'application/octet-stream' if binary else 'application/json'})
    with urllib.request.urlopen(request,timeout=30) as response:return json.loads(response.read())


def complete(job):
    deadline=time.monotonic()+300
    while True:
        result=post('/api/finance/analysis-job',{'job':job['job']})
        if result['state']=='complete':return result['result']
        if time.monotonic()>deadline:raise TimeoutError('AI summary timed out.')
        time.sleep(1)


with urllib.request.urlopen(URL+'/finance',timeout=10) as response:
    page=response.read().decode();assert 'Analysis language / Analysesprache' in page;assert 'finance-summary.js' not in page
prepared=post('/api/finance/prepare',(ROOT/'10-10-docs/10257_BWA_2024-12_261009_205509.pdf').read_bytes(),True)
token=prepared['upload_token']
signed=complete(post('/api/finance/workflow-analyze-start',{'upload_token':token,'locale':'de','rotation':0}))
for lang in ('en','de'):
    print('Requesting live '+lang+' document explanation.',flush=True)
    result=complete(post('/api/finance/summary-start',{'upload_token':token,'analysis':signed,'language':lang}))
    assert result['language']==lang and result['model']=='openai/gpt-4.1'
    assert len(result['summary']['cost_labels'])==11
    assert result['summary']['overview'] and result['summary']['title']
    metrics={v['key']:v['amount'] for v in result['facts']['periods'][0]['metrics']}
    assert metrics['income']=='41.623,64' and metrics['result']=='-34.873,94'
    assert result['facts']['periods'][0]['kind']=='ytd'
    print('PASS: '+lang+' AI explanation and translated costs; original amounts/periods unchanged.',flush=True)
print('PASS: bilingual upload summary API and served language selector.',flush=True)
