/* Two document previews; calculation checks remain unchanged. */
(()=>{
let highlightedUrl=null;
const style=document.createElement('style');style.textContent=`.preview-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px}.preview-toolbar button{width:auto;margin:0}.preview-expanded{position:fixed;inset:0;z-index:10000;background:white;padding:16px;overflow:auto}.preview-expanded iframe{height:calc(100vh - 100px)}#selectedWrap{display:none!important}`;document.head.append(style);
let expanded=null,previousOverflow='';
function closeExpanded(){if(expanded){expanded.classList.remove('preview-expanded');expanded=null;document.body.style.overflow=previousOverflow}}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeExpanded()});
for(const id of ['originalWrap','resultWrap']){const target=$(id),heading=target.querySelector('h2'),bar=document.createElement('div'),button=document.createElement('button');bar.className='preview-toolbar';button.type='button';button.textContent='Fullscreen';button.onclick=()=>{if(expanded===target){closeExpanded();button.textContent='Fullscreen';return}closeExpanded();previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden';expanded=target;target.classList.add('preview-expanded');button.textContent='Close fullscreen'};heading.replaceWith(bar);bar.append(heading,button)}
$('originalWrap').querySelector('h2').textContent='Original PDF - selected amount';
$('resultWrap').querySelector('h2').textContent='Recalculated PDF';
function selectedPage(){return cell($('input').value)?.page||1}
function showPage(){if(originalUrl)$('original').src=originalUrl+'#page='+selectedPage();if(highlightedUrl||resultUrl)$('result').src=(highlightedUrl||resultUrl)+'#page='+selectedPage()}
const oldInvalidate=invalidate;invalidate=function(clearProposal=true){closeExpanded();if(highlightedUrl)URL.revokeObjectURL(highlightedUrl);highlightedUrl=null;oldInvalidate(clearProposal)};
const oldApi=api;api=async function(path,data){if(path==='/api/finance/workflow-analyze'){const job=await oldApi('/api/finance/workflow-analyze-start',data);let attempts=0;while(true){await new Promise(resolve=>setTimeout(resolve,1500));const response=await oldApi('/api/finance/analysis-job',{job:job.job});if(response.state==='complete')return response.result;if(++attempts%10===0)status('Still loading document amounts and analyzing the report. Large scans can take several minutes...')}}const r=await oldApi(path,data);if(path==='/api/finance/workflow-apply'&&r.highlighted){if(highlightedUrl)URL.revokeObjectURL(highlightedUrl);highlightedUrl=pdfUrl(r.highlighted.after)}return r};
const oldApply=$('apply').onclick;$('apply').onclick=async()=>{await oldApply();if(!$('download').hidden){showPage();$('resultWrap').scrollIntoView({behavior:'smooth',block:'start'})}};
const previewSelectInput=selectInput;selectInput=async function(){await previewSelectInput();showPage();$('selectedWrap').hidden=true};$('input').onchange=selectInput;
// The user authorized automatic application after validated GPT analysis.
for(const id of ['accept','plan','apply'])$(id).hidden=true;
const technical=document.createElement('details'),technicalSummary=document.createElement('summary');technicalSummary.textContent='Calculation details';technical.append(technicalSummary);technical.hidden=true;$('proposalWrap').before(technical);technical.append($('proposalWrap'));
const ruleTable=$('rules'),ruleHeading=ruleTable.previousElementSibling;technical.append(ruleHeading,ruleTable);
ruleHeading.textContent='Applied calculation rules';
for(const id of ['cells','changes','summary']){const element=$(id);if(id!=='summary')element.previousElementSibling.hidden=true;element.hidden=true}
$('affected').textContent='Recalculate & create PDF';
const simulationLabel=document.createElement('label'),simulationToggle=document.createElement('input');simulationToggle.type='checkbox';simulationToggle.id='proportionalSimulation';simulationToggle.checked=true;simulationToggle.style.width='auto';simulationLabel.append(simulationToggle,document.createTextNode(' Proportional planning simulation'));
const simulationHint=document.createElement('p');simulationHint.className='hint';simulationHint.textContent='Change one revenue or expense amount per month. Sales and all operating expenses in that month scale by the same percentage; totals recalculate. Zero expenses stay zero. Export is labelled Simulation, not actual bookkeeping or a tax filing.';$('affected').before(simulationLabel,simulationHint);simulationToggle.onchange=()=>invalidate();
$('rasterWrap').querySelector('label').lastChild.textContent=' Allow image-based export for scans (replacement fonts are approximate; review the PDF preview).';
const simulationPayload=payload;payload=function(){return {...simulationPayload(),proportional_simulation:simulationToggle.checked}};
$('affected').onclick=async()=>{
    let batch;
    try{batch=payload();if(!batch.edits.length){status('Enter at least one amount different from the original before recalculating.',true);$('value').focus();return}if(batch.edits.length>30){status('A batch supports up to 30 changed amounts.',true);return}}catch(e){status(e.message,true);$('value').focus();return}
    invalidate();busy=true;controls();status('GPT is identifying affected values, then Python will calculate and create your PDF...');
    try{
        if(batch.proportional_simulation){status('Calculating proportional planning simulation...');const verified=await api('/api/finance/workflow-plan',batch);showChanges(verified.changes);approved=true;await $('apply').onclick();if(!$('download').hidden){$('download').download=$('download').download.replace('-reviewed-recalculated.pdf','-simulation.pdf');$('download').textContent='Download simulation PDF';$('resultWrap').querySelector('h2').textContent='Proportional simulation PDF'}return}
        proposal=await api('/api/general/dependencies',batch);
        $('proposalNote').textContent=proposal.note;
        table($('proposals'),['Target','Calculation','Explanation'],proposal.suggestions.map(r=>[field(r.target),formula(r),r.reason||'Source-validated relationship']));
        $('unresolved').textContent=proposal.unresolved.map(r=>`${field(r.id)}: ${r.reason}`).join('; ');
        $('proposalWrap').hidden=false;showChanges(proposal.changes);
        if(proposal.unresolved.length)throw Error('Some calculation relationships remain unresolved. No PDF was created. See Calculation details.');
        if(!proposal.changes.length)throw Error('No changed amounts were identified. Enter a replacement amount.');
        rules=proposal.suggestions.map(r=>({target:r.target,terms:r.terms.map(t=>({...t}))}));showRules();
        status('Verifying calculations and complete supported dependency coverage...');
        const verified=await api('/api/finance/workflow-plan',{...batch,rules});
        showChanges(verified.changes);approved=true;
        await $('apply').onclick();
    }catch(e){approved=false;status(e.message,!e.recovered)}finally{busy=false;controls()}
};
// Selecting a file starts extraction/OCR and GPT interpretation immediately.
$('analyze').hidden=true;
const advanced=document.createElement('details'),advancedTitle=document.createElement('summary');advancedTitle.textContent='Optional format and scan settings';advanced.append(advancedTitle);
const formatLabel=document.querySelector('label[for="locale"]'),rotationLabel=document.querySelector('label[for="rotation"]');
formatLabel.before(advanced);advanced.append(formatLabel,$('locale'),rotationLabel,$('rotation'));
const retry=document.createElement('button');retry.type='button';retry.textContent='Retry analysis';retry.hidden=true;$('analyze').after(retry);
retry.onclick=async()=>{retry.hidden=true;await $('analyze').onclick();retry.hidden=!!analysis};
const originalUpload=$('file').onchange;
$('file').onchange=async()=>{retry.hidden=true;await originalUpload();if(pdf){await $('analyze').onclick();retry.hidden=!!analysis}};
for(const id of ['locale','rotation'])$(id).onchange=async()=>{if(pdf){retry.hidden=true;await $('analyze').onclick();retry.hidden=!!analysis}};
const uploadHint=document.createElement('p');uploadHint.className='hint';uploadHint.textContent='Upload to analyze automatically with GPT. Scanned pages are read with OCR first. Enter changes, then recalculate and download. AI analysis uses your OpenRouter credits.';$('file').after(uploadHint);
$('analyze').parentElement.querySelector('h2').textContent='1. Upload your document';
const amountLoading=document.createElement('p');amountLoading.className='hint amount-loading';amountLoading.setAttribute('role','status');amountLoading.setAttribute('aria-live','polite');amountLoading.hidden=true;
const spinner=document.createElement('span');spinner.className='amount-spinner';spinner.setAttribute('aria-hidden','true');amountLoading.append(spinner,document.createTextNode('Loading amounts from your document...'));$('input').after(amountLoading);
style.textContent+='.amount-loading{display:flex;align-items:center;gap:9px}.amount-spinner{display:inline-block;width:18px;height:18px;border:2px solid #dce2ec;border-top-color:#255bce;border-radius:50%;animation:amount-spin .8s linear infinite}@keyframes amount-spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.amount-spinner{animation:none}}';
const loadingControls=controls;controls=function(){loadingControls();const supported=statement()?.export_mode==='direct';if(analysis&&!supported)simulationToggle.checked=false;simulationToggle.disabled=busy||!supported;simulationHint.textContent=analysis&&!supported?'Proportional simulation currently supports annual DATEV BWA only. This document uses reviewed account formulas.':'Change one revenue or expense amount per month. Sales and all operating expenses in that month scale by the same percentage; totals recalculate. Export is labelled Simulation.';$('rasterWrap').hidden=!statement()?.cells.some(c=>c.mode==='ocr');if(!busy&&analysis&&simulationToggle.checked){try{$('affected').disabled=!payload().edits.length}catch{$('affected').disabled=false}}const loading=busy&&!analysis;amountLoading.hidden=!loading;$('input').setAttribute('aria-busy',String(loading));if(!analysis){const placeholder=new Option(loading?'Loading amounts...':pdf?'Amounts unavailable - retry analysis':'Upload a document to load amounts','');$('input').replaceChildren(placeholder);$('current').textContent='';$('value').value='';$('value').placeholder=loading?'Please wait for amounts to load':''}};
controls();
})();
