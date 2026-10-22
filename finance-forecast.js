/* AI realistic scenario: after your own change, the AI researches real figures for
   the document year on the web and decides what drives every other account in the
   same period column. Python calculates the amounts and all totals. */
(()=>{
const panel=document.createElement('div');panel.className='scenario-option';
panel.innerHTML='<label><input id="expensePlanning" type="checkbox" style="width:auto" checked> Realistic AI scenario (web research for the document year)</label><p class="hint">After your change, the AI searches the web for real figures for the year of this document (inflation, wages, energy, fuel, rents, industry prices) and adjusts every other account in the same period column. Python calculates all amounts and totals. Each analysis uses a few cents of OpenRouter credit.</p>';
$('value').after(panel);
const review=document.createElement('div'),heading=document.createElement('h3'),note=document.createElement('p'),facts=document.createElement('p'),sources=document.createElement('ul'),limits=document.createElement('div'),changes=document.createElement('div'),create=document.createElement('button');
review.id='expenseReview';heading.textContent='Review the AI scenario: researched figures and proposed amounts';note.className='hint';facts.className='facts';sources.className='sources';limits.className='scroll';changes.className='scroll';create.type='button';create.textContent='I reviewed the figures and sources — create modified PDF';
const sourceHeading=document.createElement('h4');sourceHeading.textContent='Researched figures (web sources)';
const accountHeading=document.createElement('h4'),changeHeading=document.createElement('h4');accountHeading.textContent='Proposed accounts';changeHeading.textContent='All changed fields, including recalculated totals';
const prompts=document.createElement('div');prompts.className='prompt-log';
review.append(heading,note,facts,prompts,sourceHeading,sources,accountHeading,limits,changeHeading,changes,create);$('resultWrap').before(review);review.hidden=true;
let accepted=null;
function supported(){return statement()?.export_mode==='direct'||['datev_cash_basis','buhl_bwa'].includes(statement()?.profile)}
function active(){return !!analysis&&supported()&&$('expensePlanning').checked}
const drivers={sales:'Sales volume',indicator:'Researched figure',none:'Unchanged'};
const oldControls=controls;controls=function(){oldControls();panel.hidden=!!analysis&&!supported();$('expensePlanning').disabled=busy||!analysis||!supported();
 if(active()){let count=0;try{count=payload().edits.length}catch{}const hasEdits=count>0;$('affected').textContent=hasEdits?`Preview realistic AI scenario (${count})`:'Preview realistic AI scenario';if(analysis)$('model').textContent='AI scenario: account names and amounts are sent to OpenRouter (about $0.10-0.15 per preview). Python calculates every amount.';$('affected').disabled=busy||!aiEnabled||!hasEdits;$('proportionalSimulation').checked=false;$('proportionalSimulation').disabled=true;}
 else $('affected').textContent='Recalculate & create PDF';
 create.disabled=busy||!accepted;
};
const oldInvalidate=invalidate;invalidate=function(clearProposal=true){accepted=null;review.hidden=true;oldInvalidate(clearProposal)};
const oldReset=reset;reset=function(){accepted=null;review.hidden=true;oldReset()};
$('expensePlanning').onchange=()=>invalidate();
const simulation=$('proportionalSimulation');if(simulation?.parentElement){simulation.parentElement.hidden=true;if(simulation.parentElement.nextElementSibling)simulation.parentElement.nextElementSibling.hidden=true}
function el(tag,className,text){const e=document.createElement(tag);if(className)e.className=className;if(text!=null)e.textContent=text;return e}
function percent(value){const n=Number(value);return el('span',n>0?'up':n<0?'down':'flat',`${n>0?'+':''}${value} %`)}
function showFacts(r,sales){
 facts.replaceChildren();
 const chip=(label,...value)=>{const c=el('span','fact');c.append(el('b',null,label),...value);facts.append(c)};
 chip('Document year',r.document_year);chip('Region',r.region);chip('Industry',r.industry);
 for(const v of sales)chip('Sales change',`${v.column} `,percent(v.change_percent));
}
function showSources(research){
 sources.replaceChildren();
 for(const v of research.indicators){
  const li=el('li'),value=el('span','value'),a=el('a',null,v.source_title||v.source_url);
  a.href=v.source_url;a.target='_blank';a.rel='noopener noreferrer';a.title=v.source_url;value.append(percent(v.change_percent));
  li.append(el('b',null,v.name),value,el('span','period',v.period),a);sources.append(li);
 }
}
function showPrompts(list){
 prompts.replaceChildren();if(!list?.length){prompts.hidden=true;return}prompts.hidden=false;
 const head=el('div','prompt-head');head.append(el('b',null,'Prompts sent to the AI'),el('span','hint',` ${list.length} AI calls · model ${list[0].model}`));prompts.append(head);
 for(const p of list){
  const box=el('details','prompt-step'),summary=el('summary');
  summary.append(el('b',null,p.step),' ',el('span','badge '+(p.web_search?'web':'none'),p.web_search?'Web search on':'No web search'),' ',el('code',null,p.file));box.append(summary);
  const block=(title,text)=>{if(!text)return;box.append(el('h5',null,title));const pre=el('pre',null,text);pre.dataset.noTranslate='';box.append(pre)};
  block('Instructions (system prompt)',p.system);block('Data sent (user message)',p.user);block('AI research answer',p.response);
  prompts.append(box);
 }
}
function showAccounts(rows){
 const t=el('table'),head=el('tr');
 for(const label of ['Account','Before','Proposed','Change %','Driver','Researched figure','Reason'])head.append(el('th',null,label));t.append(head);
 for(const v of rows){
  const tr=el('tr'),change=el('td'),driver=el('td');change.append(percent(v.change_percent));driver.append(el('span','badge '+v.driver,drivers[v.driver]||v.driver));
  tr.append(el('td',null,v.context),el('td',null,v.before),el('td',null,v.after),change,driver,el('td',null,v.indicators.join(', ')),el('td',null,v.reason));t.append(tr);
 }
 limits.replaceChildren(t);
}
const oldAffected=$('affected').onclick;$('affected').onclick=async()=>{
 if(!active())return oldAffected();let batch;
 try{batch={...payload(),language:window.appLanguage?.()||'en'};if(!batch.edits.length)throw Error('Enter a changed amount before previewing.')}catch(e){status(e.message,true);return}
 invalidate();busy=true;controls();status('The AI is researching real figures for the document year and proposing the other accounts; Python will calculate and verify every amount...');
 try{
  const job=await api('/api/finance/scenario-start',batch);let response;
  do{await new Promise(resolve=>setTimeout(resolve,1500));response=await api('/api/finance/analysis-job',{job:job.job})}while(response.state!=='complete');
  const result=response.result,r=result.research;
  note.textContent=result.summary+' '+result.note;
  showFacts(r,result.sales_change);
  showPrompts(result.prompts);
  showSources(r);
  showAccounts(result.accounts);
  table(changes,['Field','Page','Before','After','Reason'],result.changes.map(c=>[c.context,c.page,c.text,c.new,c.reason]));
  accepted={batch,scenario:result.scenario};review.hidden=false;review.scrollIntoView({behavior:'smooth',block:'start'});status('Review the researched figures, their sources and the proposed amounts. Then create the PDF; highlights appear only in its preview.');
 }catch(e){status(e.message,!e.recovered)}finally{busy=false;controls()}
};
create.onclick=async()=>{
 if(busy||!accepted)return;const saved=accepted;busy=true;controls();status('Creating the reviewed scenario PDF and highlighted preview...');
 try{const result=await api('/api/finance/scenario-apply',{pdf,analysis,scenario:saved.scenario,reviewed:true,allow_raster:$('raster').checked});
  if(resultUrl)URL.revokeObjectURL(resultUrl);resultUrl=pdfUrl(result.pdf);$('download').href=resultUrl;$('download').download=$('file').files[0].name.replace(/\.[^.]+$/,'')+'-ai-scenario.pdf';$('download').textContent='Download scenario PDF';$('download').hidden=false;
  displayModifiedPdf();$('resultWrap').querySelector('h2').textContent='AI scenario — highlighted changes';$('resultWrap').scrollIntoView({behavior:'smooth',block:'start'});status(`${result.changes.length} changed fields. ${result.note}`);
 }catch(e){status(e.message,true)}finally{busy=false;controls()}
};
controls();
})();
