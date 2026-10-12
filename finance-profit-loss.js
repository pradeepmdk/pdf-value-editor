/* A desired result is solved from verified formulas, then reviewed before export. */
(()=>{
const panel=document.createElement('div');
panel.innerHTML='<label><input id="profitLossEnabled" type="checkbox" style="width:auto"> Set a profit / loss target</label><div id="profitLossFields" hidden><label for="profitLossKind">Desired result</label><select id="profitLossKind"><option value="profit">Profit</option><option value="loss">Loss</option></select><label for="profitLossPeriod">Result period</label><select id="profitLossPeriod"></select><p id="profitLossCurrent" class="hint"></p><label for="profitLossAmount">Target amount (positive value)</label><input id="profitLossAmount" inputmode="decimal" placeholder="1.000,00"><p id="profitLossSourceInfo" class="hint"></p><div id="profitLossCounterpartWrap" hidden><label for="profitLossCounterpart">Matching debit / credit input</label><select id="profitLossCounterpart"></select></div><p id="profitLossNote" class="hint"></p></div><p id="profitLossUnavailable" class="hint" hidden></p>';
$('current').after(panel);
const review=document.createElement('div'),reviewTitle=document.createElement('h3'),reviewNote=document.createElement('p'),reviewTable=document.createElement('div'),create=document.createElement('button');
const replacementLabel=document.querySelector('label[for="value"]');
reviewTitle.textContent='Review profit / loss changes';reviewTable.className='scroll';create.type='button';create.textContent='Create PDF with these changes';review.append(reviewTitle,reviewNote,reviewTable,create);panel.after(review);review.hidden=true;
let configuration=null,reviewedBatch=null;
function active(){return !!analysis&&$('profitLossEnabled').checked}
function period(){return configuration?.periods.find(p=>p.id===$('profitLossPeriod').value)}
function option(c){return new Option(`${c.text} | ${c.context} | page ${c.page}`,c.id)}
function counterparts(){
 const source=cell($('input').value),previous=$('profitLossCounterpart').value;
 const opposite={1:2,2:1,3:4,4:3}[source?.column_index];
 const choices=(statement()?.cells||[]).filter(c=>c.editable===true&&/^\d+$/.test(c.row||'')&&Number(c.row)<4000&&c.column_index===opposite);
 $('profitLossCounterpart').replaceChildren(new Option('Choose a matching entry',''),...choices.map(option));
 if(choices.some(c=>c.id===previous))$('profitLossCounterpart').value=previous;
}
function showPeriod(){
 const p=period();
 if(p&&!p.sources.includes($('input').value)){
  const previous=cell($('input').value);
  const eligible=p.sources.map(id=>cell(id)).filter(c=>c?.editable===true);
  const next=eligible.find(c=>previous&&c.row===previous.row)||eligible[0];
  if(next){$('input').value=next.id;$('value').value=next.text;$('current').textContent='Current amount: '+next.text}
 }
 const selected=cell($('input').value);
 $('profitLossCurrent').textContent=p?'Current result: '+p.current:'';
 $('profitLossSourceInfo').textContent=p?.sources.includes(selected?.id)?'Using input: '+selected.context:'No verified input is available for this result period.';
 counterparts();
}
function syncSelectedPeriod(){
 if(!period()?.sources.includes($('input').value)){
  const matching=configuration?.periods.find(p=>p.sources.includes($('input').value));
  if(matching)$('profitLossPeriod').value=matching.id;
 }
 showPeriod();
}
const previousApi=api;api=async function(path,data){
 const r=await previousApi(path,data);
 if(path==='/api/finance/workflow-analyze'){
  try{configuration=await previousApi('/api/finance/profit-loss-options',{pdf,analysis:r});
   $('profitLossPeriod').replaceChildren(...configuration.periods.map(p=>new Option(p.label,p.id)));
   $('profitLossCounterpartWrap').hidden=!configuration.requires_counterpart;
   $('profitLossNote').textContent=configuration.note;
  }catch(e){configuration=null;$('profitLossUnavailable').textContent=e.message}
 }
 return r;
};
const previousReset=reset;reset=function(){configuration=null;reviewedBatch=null;$('profitLossEnabled').checked=false;review.hidden=true;$('profitLossFields').hidden=true;$('profitLossAmount').value='';previousReset()};
const previousInvalidate=invalidate;invalidate=function(clearProposal=true){reviewedBatch=null;review.hidden=true;previousInvalidate(clearProposal)};
const previousPayload=payload;payload=function(){const p=previousPayload();if(active()){
 if(!period()?.sources.includes($('input').value))throw Error('The selected input does not contribute to this profit/loss result period.');
 p.profit_loss={kind:$('profitLossKind').value,period:$('profitLossPeriod').value,amount:normalizeFinancialAmount($('profitLossAmount').value,$('locale').value,''),source:$('input').value,counterpart:$('profitLossCounterpart').value};
}return p};
const previousControls=controls;controls=function(){previousControls();const supported=!!configuration?.periods.length;
 if(active()&&!busy&&period()&&!period().sources.includes($('input').value))showPeriod();
 $('profitLossEnabled').disabled=busy||!analysis||!supported;
 $('profitLossFields').hidden=!active();$('profitLossUnavailable').hidden=!analysis||supported;
 if(analysis&&!supported&&!configuration)$('profitLossUnavailable').textContent='Profit/loss targets need a recognized result formula.';
 else if(analysis&&!supported)$('profitLossUnavailable').textContent='No verified profit/loss formula is available for this report.';
 for(const id of ['profitLossKind','profitLossPeriod','profitLossAmount','profitLossCounterpart'])$(id).disabled=busy||!analysis;
 $('value').hidden=active();if(replacementLabel)replacementLabel.hidden=active();
 if(document.getElementById('addPendingChange'))$('addPendingChange').hidden=active();
 if(analysis&&!busy)$('value').placeholder='';
 if(active()){$('affected').textContent='Preview profit / loss changes';$('affected').disabled=busy||!$('profitLossAmount').value.trim()||!period()?.sources.includes($('input').value);$('proportionalSimulation').disabled=true;$('value').disabled=true;}
 else $('affected').textContent='Recalculate & create PDF';
 create.disabled=busy||!reviewedBatch;
};
$('profitLossEnabled').onchange=()=>{if(active()){$('proportionalSimulation').checked=false;syncSelectedPeriod()}invalidate()};
$('profitLossPeriod').onchange=()=>{showPeriod();invalidate()};
$('profitLossKind').onchange=()=>invalidate();$('profitLossAmount').oninput=()=>invalidate();
$('profitLossAmount').onblur=()=>{if(!$('profitLossAmount').value.trim())return;try{$('profitLossAmount').value=normalizeFinancialAmount($('profitLossAmount').value,$('locale').value,'')}catch(e){status(e.message,true)}};
$('profitLossCounterpart').onchange=()=>invalidate();
const previousSelect=selectInput;selectInput=async function(){await previousSelect();if(active())syncSelectedPeriod();controls()};$('input').onchange=selectInput;
const previousAffected=$('affected').onclick;$('affected').onclick=async()=>{
 if(!active())return previousAffected();
 let batch;try{batch=payload()}catch(e){status(e.message,true);return}
 invalidate();busy=true;controls();status('Calculating the selected input needed for your profit/loss target...');
 try{const r=await api('/api/finance/profit-loss-preview',batch);reviewNote.textContent=`${r.profit_loss.period}: ${r.profit_loss.before} → ${r.profit_loss.after}. Review the adjusted inputs and dependent totals before creating the PDF.`;
  table(reviewTable,['Field','Page','Before','After'],r.changes.map(c=>[c.context,c.page,c.text,c.new]));
  reviewedBatch={...batch,rules:r.rules};review.hidden=false;status('Profit/loss target verified. Review the proposed changes, then create the PDF.');
 }catch(e){status(e.message,true)}finally{busy=false;controls()}
};
create.onclick=async()=>{
 if(!reviewedBatch||busy)return;const batch=reviewedBatch;busy=true;controls();status('Creating and verifying the PDF for your reviewed profit/loss target...');
 try{const r=await api('/api/finance/workflow-apply',{...batch,allow_raster:$('raster').checked});
  if(resultUrl)URL.revokeObjectURL(resultUrl);resultUrl=pdfUrl(r.pdf);$('download').href=resultUrl;
  $('download').download=$('file').files[0].name.replace(/\.[^.]+$/,'')+'-profit-loss-recalculated.pdf';$('download').textContent='Download recalculated PDF';$('download').hidden=false;
  displayModifiedPdf();status(`${r.profit_loss.period} result: ${r.profit_loss.after}. ${r.changes.length} fields changed. Inspect the highlighted changes in the final PDF preview before downloading.`);
  $('resultWrap').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(e){status(e.message,true)}finally{busy=false;controls()}
};
controls();
})();
