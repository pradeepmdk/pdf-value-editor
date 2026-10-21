/* Reviewed expense planning replaces the single-field profit/loss target UI. */
(()=>{
const panel=document.createElement('div');
panel.innerHTML='<label><input id="expensePlanning" type="checkbox" style="width:auto" checked> Realistic expense planning</label><p class="hint">Changing income keeps expenses unchanged unless you enter an expense change or enable the sales-volume assumption below. Payroll, telephone, rent and taxes do not automatically follow income.</p><label><input id="assumeVolume" type="checkbox" style="width:auto"> Assume the income change comes from sales volume</label><p class="hint">Optional scenario: propose bounded changes to variable costs. This assumes unchanged prices and a similar sales mix. It does not prove capacity, actual budgets or that the target is achievable.</p>';
$('value').after(panel);
const periodHint=document.createElement('p');periodHint.className='hint';periodHint.textContent='Cash-basis BWA: monthly corrections update year-to-date. A year-to-date correction is assigned to the displayed current month, keeping earlier months unchanged. Enter both amounts explicitly to use a different split. Previous-year inputs stay unchanged. Full-year income allocation remains a separate planning operation.';panel.append(periodHint);
const review=document.createElement('div'),heading=document.createElement('h3'),note=document.createElement('p'),limits=document.createElement('div'),changes=document.createElement('div'),create=document.createElement('button');
review.id='expenseReview';heading.textContent='Review expense assumptions and changes';note.className='hint';limits.className='scroll';changes.className='scroll';create.type='button';create.textContent='I reviewed these assumptions — create modified PDF';review.append(heading,note,limits,changes,create);$('resultWrap').before(review);review.hidden=true;
let accepted=null;
function supported(){return statement()?.export_mode==='direct'||['datev_cash_basis','addison_susa'].includes(statement()?.profile)}
function active(){return !!analysis&&supported()&&$('expensePlanning').checked}
function annualOption(){
 const c=cell('revenue_12');if(!c||!supported())return;
 const existing=Array.from($('input').options).find(o=>o.value===c.id);
 if(active()&&!existing)$('input').append(new Option(`${c.text} | Annual income (planning allocation across months)`,c.id));
 if(!active()&&existing){const selected=$('input').value===c.id;existing.remove();if(selected||!$('input').value){$('input').value=statement().cells.find(c=>c.editable===true)?.id||'';$('value').value=cell($('input').value)?.text||''}}
}
const oldControls=controls;controls=function(){oldControls();panel.hidden=!!analysis&&!supported();$('expensePlanning').disabled=busy||!analysis||!supported();annualOption();
 $('assumeVolume').disabled=busy||!active();
 if(active()){$('affected').textContent='Preview realistic adjustments';let hasEdits=false;try{hasEdits=payload().edits.length>0}catch{}$('affected').disabled=busy||!aiEnabled||!hasEdits;$('proportionalSimulation').checked=false;$('proportionalSimulation').disabled=true;}
 create.disabled=busy||!accepted;
};
const oldInvalidate=invalidate;invalidate=function(clearProposal=true){accepted=null;review.hidden=true;oldInvalidate(clearProposal)};
const oldReset=reset;reset=function(){accepted=null;review.hidden=true;oldReset()};
$('expensePlanning').onchange=()=>{invalidate();if(!active()&&cell($('input').value)?.editable===false){annualOption();selectInput()}};
$('assumeVolume').onchange=()=>invalidate();
const simulation=$('proportionalSimulation');if(simulation?.parentElement){simulation.parentElement.hidden=true;if(simulation.parentElement.nextElementSibling)simulation.parentElement.nextElementSibling.hidden=true}
const oldAffected=$('affected').onclick;$('affected').onclick=async()=>{
 if(!active())return oldAffected();let batch;
 try{batch={...payload(),assume_volume:$('assumeVolume').checked};if(!batch.edits.length)throw Error('Enter a changed income or expense amount before previewing.')}catch(e){status(e.message,true);return}
 invalidate();busy=true;controls();status('OpenRouter is proposing bounded expense assumptions; Python will calculate and verify the changes...');
 try{
  const job=await api('/api/finance/forecast-start',batch);let response;
  do{await new Promise(resolve=>setTimeout(resolve,1500));response=await api('/api/finance/analysis-job',{job:job.job})}while(response.state!=='complete');
  const result=response.result;note.textContent=result.summary+' '+result.note;
  table(limits,['Expense','Before','Proposed','Why changed / unchanged','Safeguard minimum','Safeguard maximum','Behaviour','Evidence / assumption'],result.limits.map(v=>[v.context,v.before,v.after,v.adjustment_basis,v.minimum,v.maximum,v.category,v.reason+' '+v.policy]));
  table(changes,['Field','Page','Before','After','Reason'],result.changes.map(c=>[c.context,c.page,c.text,c.new,c.reason]));
  accepted={batch,forecast:result.forecast};review.hidden=false;review.scrollIntoView({behavior:'smooth',block:'start'});status('Review the expense limits and changed amounts in the document area. The modified PDF contains only the amount changes; highlights appear in its preview.');
 }catch(e){status(e.message,!e.recovered)}finally{busy=false;controls()}
};
create.onclick=async()=>{
 if(busy||!accepted)return;const saved=accepted;busy=true;controls();status('Creating the reviewed planning PDF and highlighted preview...');
 try{const result=await api('/api/finance/forecast-apply',{pdf,analysis,forecast:saved.forecast,reviewed:true,allow_raster:$('raster').checked});
  if(resultUrl)URL.revokeObjectURL(resultUrl);resultUrl=pdfUrl(result.pdf);$('download').href=resultUrl;$('download').download=$('file').files[0].name.replace(/\.[^.]+$/,'')+'-expense-planning.pdf';$('download').textContent='Download planning PDF';$('download').hidden=false;
  displayModifiedPdf();$('resultWrap').querySelector('h2').textContent='Expense planning — highlighted changes';$('resultWrap').scrollIntoView({behavior:'smooth',block:'start'});status(`${result.changes.length} changed fields. ${result.note}`);
 }catch(e){status(e.message,true)}finally{busy=false;controls()}
};
controls();
})();
