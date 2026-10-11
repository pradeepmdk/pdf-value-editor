"""Exercise upload, analysis, preview, recalculation and export on localhost."""
import base64
import json
from pathlib import Path
import time
import urllib.request
import pymupdf

ROOT=Path(__file__).resolve().parent.parent
URL='http://127.0.0.1:8000'


def post(path,payload,binary=False):
    body=payload if binary else json.dumps(payload).encode()
    request=urllib.request.Request(URL+path,data=body,headers={'Content-Type':'application/octet-stream' if binary else 'application/json'})
    with urllib.request.urlopen(request,timeout=120) as response:
        assert response.status==200
        return json.loads(response.read())


with urllib.request.urlopen(URL+'/finance',timeout=10) as response:
    page=response.read().decode()
    assert response.status==200
    assert 'Recognized BWA and SuSa layouts use verified format rules' in page
    assert 'rules=proposal.suggestions.map(r=>({...r,' in page
data=(ROOT/'10-10-docs/10257_BWA_2024-12_261009_205509.pdf').read_bytes()
prepared=post('/api/finance/prepare',data,binary=True)
token=prepared['upload_token']
job=post('/api/finance/workflow-analyze-start',{'upload_token':token,'locale':'de','rotation':0})
deadline=time.monotonic()+120
while True:
    result=post('/api/finance/analysis-job',{'job':job['job']})
    if result['state']=='complete':break
    if time.monotonic()>deadline:raise TimeoutError('Analysis job timed out.')
    time.sleep(.2)
signed=result['result']
assert signed['analysis']['statement']['profile']=='datev_cash_basis'
assert signed['inspection']['model']=='verified-format-rules'
payload={'upload_token':token,'analysis':signed,'edits':[{'id':'c1','value':'3.837,82'}]}
assert post('/api/general/preview',{**payload,'id':'c1'})['image']
proposal=post('/api/general/dependencies',payload)
assert not proposal['unresolved']
payload['rules']=proposal['suggestions']
planned=post('/api/finance/workflow-plan',payload)
saved=post('/api/finance/workflow-apply',payload)
assert saved['changes']==planned['changes']
assert saved['highlighted']['after']
with pymupdf.open(stream=base64.b64decode(saved['pdf']),filetype='pdf') as doc:
    assert len(doc)==10
    assert '3.837,82' in doc[0].get_text()
    assert '-10.613,65' in doc[0].get_text()
    assert '3.837,82' in doc[2].get_text()
print('PASS: live upload, analysis job, recognized format, field preview, dependencies, plan, export and highlighted preview')
print('App: '+URL+'/finance')
