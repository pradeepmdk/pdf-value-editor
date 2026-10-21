"""Live OpenRouter planning request, followed by verified and highlighted export."""
import base64
import json
import sys
from pathlib import Path
import time
import urllib.request
import urllib.error
import pymupdf

ROOT=Path(__file__).resolve().parent.parent
URL='http://127.0.0.1:8000'


def post(path,payload,binary=False):
    if not binary and len(sys.argv)>2:payload={**payload,'ai_model':sys.argv[2]}
    body=payload if binary else json.dumps(payload).encode()
    req=urllib.request.Request(URL+path,data=body,headers={'Content-Type':'application/octet-stream' if binary else 'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as result:return json.loads(result.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode()) from None


def complete(job):
    deadline=time.monotonic()+300
    while True:
        r=post('/api/finance/analysis-job',{'job':job['job']})
        if r['state']=='complete':return r['result']
        if time.monotonic()>deadline:raise TimeoutError('Planning job timed out.')
        time.sleep(1)


with urllib.request.urlopen(URL+'/finance',timeout=10) as response:
    page=response.read().decode()
    assert 'Set a profit / loss target' not in page
    assert 'Realistic expense planning' in page
data=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'10-10-docs/10257_BWA_2024-12_261009_205509.pdf').read_bytes()
prepared=post('/api/finance/prepare',data,True)
token=prepared['upload_token']
signed=complete(post('/api/finance/workflow-analyze-start',{'upload_token':token,'locale':'de','rotation':0}))
batch={'upload_token':token,'analysis':signed,'edits':[{'id':'c1','value':'12.837,82'}]}
print('Local extraction complete; requesting OpenRouter cost assumptions.',flush=True)
preview=complete(post('/api/finance/forecast-start',batch))
assert preview['model']==(sys.argv[2] if len(sys.argv)>2 else 'openai/gpt-4.1')
assert preview['limits']
for v in preview['limits']:
    if v['category']=='fixed':assert v['after']==v['before']
print(f"Live model response validated: {len(preview['limits'])} bounded expense inputs; exporting reviewed simulation.",flush=True)
saved=post('/api/finance/forecast-apply',{'upload_token':token,'analysis':signed,'forecast':preview['forecast'],'reviewed':True})
with pymupdf.open(stream=base64.b64decode(saved['pdf']),filetype='pdf') as doc:
    assert 'PLANNING SIMULATION' not in doc[0].get_text()
with pymupdf.open(stream=base64.b64decode(saved['highlighted']['after']),filetype='pdf') as doc:
    assert sum(len(list(p.annots() or [])) for p in doc)==len(saved['changes'])
print('PASS: live OpenRouter classification, bounded Decimal forecast, reviewed signed export and every changed amount highlighted.',flush=True)
