/* Upload-time AI explanations; source-backed monetary facts stay independent. */
(()=>{
const language=document.createElement('select'),languageLabel=document.createElement('label');language.id='analysisLanguage';languageLabel.htmlFor=language.id;languageLabel.textContent='Analysis language / Analysesprache';language.append(new Option('English','en'),new Option('German','de'));language.value='en';
// The app-wide language switch (i18n.js) drives the analysis language.
language.value=window.appLanguage?.()==='de'?'de':'en';languageLabel.hidden=true;language.hidden=true;
document.querySelector('main > h1').after(languageLabel,language);
language.style.cssText='max-width:260px;margin-bottom:16px';
const panel=document.createElement('div'),title=document.createElement('h2'),progress=document.createElement('p'),body=document.createElement('div'),retry=document.createElement('button');
panel.id='documentOverview';progress.className='hint';progress.setAttribute('role','status');retry.type='button';retry.hidden=true;panel.append(title,progress,body,retry);$('originalWrap').before(panel);panel.hidden=true;
let generation=0,source=null,pending=false,inputRows=null;const cache=new Map();
const words={en:{heading:'Document overview',loading:'OpenRouter is analyzing the extracted document...',ready:'AI explanation from OpenRouter GPT-4.1. Amounts below are source-backed.',retry:'Retry AI summary',period:'Period',month:'Month',ytd:'Year to date',annual:'Full year',income:'Income',sales:'Sales revenue',receipts:'Operating receipts',expenses:'Expenses',net_costs:'Net operating costs',operating_costs:'Operating costs',goods:'Goods and materials',result:'Result',costs:'Expense breakdown',metric:'Item',amount:'Amount',computed:'Calculated from source fields',printed:'Printed in PDF',verification:'Source verification',verified:'Verified',unverified:'Not verified',source:'Source fields',info:'Upload extracts your PDF locally, then OpenRouter explains the extracted information in the selected language. Recognized formats use verified local calculations. Only extracted data is sent, not the PDF file. AI requests use OpenRouter credits.',susa:'SuSa income, expenses and result are calculated from account movements, not printed BWA profit figures.'},
de:{heading:'Dokumentübersicht',loading:'OpenRouter analysiert die ausgelesenen Dokumentdaten...',ready:'KI-Erläuterung von OpenRouter GPT-4.1. Die folgenden Beträge stammen aus den Quelldaten.',retry:'KI-Zusammenfassung erneut laden',period:'Zeitraum',month:'Monat',ytd:'Jahr bis zum Berichtsmonat',annual:'Gesamtjahr',income:'Erträge',sales:'Umsatzerlöse',receipts:'Betriebseinnahmen',expenses:'Aufwendungen',net_costs:'Nettobetriebskosten',operating_costs:'Betriebskosten',goods:'Waren und Material',result:'Ergebnis',costs:'Kostenübersicht',metric:'Position',amount:'Betrag',computed:'Aus Quelldaten berechnet',printed:'Im PDF ausgewiesen',verification:'Quellenprüfung',verified:'Geprüft',unverified:'Nicht geprüft',source:'Quellfelder',info:'Beim Hochladen wird Ihr PDF lokal ausgelesen. Anschließend erläutert OpenRouter die Daten in der gewählten Sprache. Erkannte Formate werden mit geprüften lokalen Regeln berechnet. Nur ausgelesene Daten werden gesendet, nicht die PDF-Datei. KI-Anfragen verbrauchen OpenRouter-Guthaben.',susa:'SuSa-Erträge, Aufwendungen und Ergebnis werden aus Kontobewegungen berechnet; es handelt sich nicht um ausgewiesene BWA-Ergebnisse.'}};
function t(){return words[language.value]||words.en}
// Period names come from the AI reading of the document headers (e.g. "Juli 2025"); kinds are fallbacks.
function periodName(result,period){const named=result.summary.periods?.find(v=>v.id===period.id);return named?.label||t()[period.kind]+(period.kind==='month'&&!['Month','Monat'].includes(period.period)?' · '+period.period:'')}
function summaryInputs(result){
 const rows=new Map(),translations=new Map(result.summary.cost_labels.map(v=>[v.key,v.label])),w=t();
 for(const period of result.facts.periods){
  const name=periodName(result,period);
  for(const record of [...period.metrics,...period.costs]){
   if(!record.ids?.length||record.ids.length>2)continue;
   const label=translations.get(record.key)||w[record.key]||record.label||record.key;
   for(const id of record.ids){const c=cell(id);if(c?.editable!==true&&!(id==='revenue_12'&&statement()?.export_mode==='direct'))continue;
    rows.set(id,`${c.text} | ${label} | ${name}${record.ids.length>1?' | '+c.column:''}`);
   }
  }
 }
 inputRows=rows;filterInputs();
}
function filterInputs(){
 if(!inputRows)return;const input=$('input'),selected=input.value;
 const rows=[...inputRows].filter(([id])=>id!=='revenue_12'||document.getElementById('expensePlanning')?.checked);
 const current=Array.from(input.options);if(current.length===rows.length&&current.every((o,i)=>o.value===rows[i][0]&&o.textContent===rows[i][1]))return;
 input.replaceChildren(...rows.map(([id,label])=>new Option(label,id)));
 input.value=rows.some(([id])=>id===selected)?selected:rows[0]?.[0]||'';
 if(input.value!==selected){const c=cell(input.value);$('value').value=c?.text||'';$('current').textContent=c?'Current amount: '+c.text:''}
 if(!rows.length){input.disabled=true;$('affected').disabled=true}
}
function analysisGate(){
 if(inputRows&&inputRows.size){filterInputs();return}
 const message=language.value==='de'?(inputRows?'Keine bearbeitbaren Analysewerte':'Auf abgeschlossene Analyse warten...'):(inputRows?'No editable analyzed values':'Waiting for analysis to finish...');
 $('input').replaceChildren(new Option(message,''));$('input').value='';$('input').disabled=true;
 $('value').disabled=true;$('value').value='';$('value').placeholder=message;$('current').textContent='';$('affected').disabled=true;
 if(document.getElementById('addPendingChange'))$('addPendingChange').disabled=true;
}
function linkedTable(container,headers,rows,records,multiple=false){
 const tableElement=document.createElement('table'),head=document.createElement('tr');
 for(const label of headers){const th=document.createElement('th');th.textContent=label;head.append(th)}tableElement.append(head);
 rows.forEach((values,index)=>{const row=document.createElement('tr'),record=records[index];
  const ids=(record.ids||[]).filter(id=>{const c=cell(id);return c?.editable===true||(id==='revenue_12'&&statement()?.export_mode==='direct')});
  const selectable=ids.length===1||(multiple&&ids.length===2);
  values.forEach((value,column)=>{const td=document.createElement('td');
   if(column===1&&selectable){const button=document.createElement('button');button.type='button';button.textContent=value;button.title=language.value==='de'?'Betrag als Eingabe auswählen':'Select this amount as input';button.style.cssText='width:auto;margin:0;padding:0;background:transparent;color:#255bce;text-decoration:underline';
    button.onclick=async()=>{if(busy)return;if(ids.length===1){await choose(ids[0]);return}const choices=document.createElement('div');for(const id of ids){const c=cell(id),pick=document.createElement('button');pick.type='button';pick.textContent=c.text+' · '+c.column;pick.onclick=()=>choose(id);choices.append(pick)}td.replaceChildren(choices)};td.append(button);
   }else td.textContent=value;row.append(td);
  });tableElement.append(row);
 });container.replaceChildren(tableElement);
}
async function choose(id){
 if(busy)return;
 if(!Array.from($('input').options).some(o=>o.value===id)){status(language.value==='de'?'Dieser Jahresbetrag ist nur bei aktivierter Kostenplanung bearbeitbar.':'This annual amount is editable when realistic expense planning is enabled.',true);return}
 $('input').value=id;await selectInput();$('input').scrollIntoView({behavior:'smooth',block:'center'});$('value').focus();$('value').select();
}
function render(result){
 summaryInputs(result);
 const w=t();title.textContent=result.summary.title;progress.textContent=w.ready.replace('GPT-4.1',result.model||'AI');body.replaceChildren();
 const overview=document.createElement('p');overview.textContent=result.summary.overview;body.append(overview);
 for(const text of [...result.summary.highlights,...result.summary.cautions]){const p=document.createElement('p');p.textContent=text;body.append(p)}
 const verification=document.createElement('p');verification.className='hint';verification.textContent=`${w.verification}: ${result.facts.source_verified?w.verified:w.unverified} · ${result.facts.pages} ${language.value==='de'?'Seiten':'pages'} · ${result.facts.fields} ${language.value==='de'?'Felder':'fields'}`;body.append(verification);
 if(result.facts.page_coverage){const coverage=document.createElement('details'),caption=document.createElement('summary'),rows=document.createElement('div');caption.textContent=language.value==='de'?`Alle ${result.facts.pages} Seiten wurden gelesen`:`All ${result.facts.pages} pages read`;coverage.append(caption,rows);table(rows,language.value==='de'?['Seite','Betragsfelder','Lesemethode','Bearbeitbare Felder']:['Page','Amount fields','Reading method','Editable fields'],result.facts.page_coverage.map(p=>[p.page,p.fields,p.mode==='ocr'?'OCR':language.value==='de'?'PDF-Text':'PDF text',p.editable]));body.append(coverage)}
 if(result.facts.susa_computed){const p=document.createElement('p');p.textContent=w.susa;body.append(p)}
 const labels=new Map(result.summary.cost_labels.map(v=>[v.key,v.label]));
 for(const period of result.facts.periods){
  const details=document.createElement('details'),caption=document.createElement('summary'),metrics=document.createElement('div'),costs=document.createElement('div');
  details.open=period.kind!=='month';caption.textContent=periodName(result,period);details.append(caption,metrics);
  linkedTable(metrics,[w.metric,w.amount,language.value==='de'?'Quelle':'Source'],period.metrics.map(v=>[labels.get(v.key)||w[v.key]||v.label||v.key,v.amount,(v.computed?w.computed:w.printed)+(v.pages?.length?' · '+(language.value==='de'?'Seite ':'Page ')+v.pages.join(', '):'')]),period.metrics);
  if(period.costs.length){const heading=document.createElement('h3');heading.textContent=w.costs;details.append(heading,costs);linkedTable(costs,[w.metric,w.amount],period.costs.map(v=>[labels.get(v.key)||v.label,v.amount]),period.costs,true)}
  body.append(details);
 }
 controls();
}
function labels(){title.textContent=t().heading;retry.textContent=t().retry;languageLabel.textContent='Analysis language / Analysesprache';
 const hint=Array.from($('file').parentElement.querySelectorAll('p.hint')).find(p=>p.textContent.startsWith('Upload to analyze automatically.')||p.dataset.summaryUpload==='true');
 if(hint){hint.dataset.summaryUpload='true';hint.textContent=t().info}
}
async function load(signed){
 if(!signed)return;source=signed;const current=++generation,lang=language.value;panel.hidden=false;body.replaceChildren();retry.hidden=true;labels();
 if(cache.has(lang)){pending=false;language.disabled=false;render(cache.get(lang));return}
 pending=true;language.disabled=true;progress.textContent=t().loading;controls();
 try{
  const job=await api('/api/finance/summary-start',{pdf,analysis:signed,language:lang});let r;
  do{await new Promise(resolve=>setTimeout(resolve,1500));if(current!==generation)return;r=await api('/api/finance/analysis-job',{job:job.job})}while(r.state!=='complete');
  if(current!==generation)return;cache.set(lang,r.result);render(r.result);
 }catch(e){if(current===generation){progress.textContent=(language.value==='de'?'KI-Zusammenfassung nicht verfügbar: ':'AI summary unavailable: ')+e.message;retry.hidden=false}}
 finally{if(current===generation){pending=false;language.disabled=false;controls()}}
}
const summaryApi=api;api=async function(path,data){const result=await summaryApi(path,data);if(path==='/api/finance/workflow-analyze'){cache.clear();load(result)}return result};
const summaryReset=reset;reset=function(){++generation;source=null;pending=false;inputRows=null;language.disabled=false;cache.clear();panel.hidden=true;body.replaceChildren();summaryReset()};
const summaryControls=controls;controls=function(){summaryControls();analysisGate()};
const analyzedSelect=selectInput;selectInput=async function(){if(!inputRows?.size)return;return analyzedSelect()};$('input').onchange=selectInput;
language.onchange=()=>{labels();if(source)load(source)};
window.addEventListener('app-language-change',e=>{if(language.value!==e.detail){language.value=e.detail;language.onchange()}});
retry.onclick=()=>{if(!pending&&source)load(source)};
window.addEventListener('finance-model-change',()=>{cache.clear();inputRows=null;if(source)load(source)});
labels();
controls();
})();
