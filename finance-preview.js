/* Two document previews; calculation checks remain unchanged. */
(()=>{
let highlightedUrl=null;
const style=document.createElement('style');style.textContent=`.preview-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px}.preview-toolbar button{width:auto;margin:0}.preview-expanded{position:fixed;inset:0;z-index:10000;background:white;padding:16px;overflow:auto}.preview-expanded iframe{height:calc(100vh - 100px)}#selectedWrap{display:none!important}`;document.head.append(style);
let expanded=null,previousOverflow='';
const legacyFormula=formula;formula=function(rule){if(rule.operation==='percentage')return `${field(rule.terms[0].source)} / ${rule.absolute_denominator?'absolute ':''}${field(rule.terms[1].source)} × 100 (two decimals)`;return legacyFormula(rule)};
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
const simulationLabel=document.createElement('label'),simulationToggle=document.createElement('input');simulationToggle.type='checkbox';simulationToggle.id='proportionalSimulation';simulationToggle.checked=false;simulationToggle.style.width='auto';simulationLabel.append(simulationToggle,document.createTextNode(' Proportional planning simulation'));
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
        rules=proposal.suggestions.map(r=>({...r,terms:r.terms.map(t=>({...t}))}));showRules();
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
const uploadHint=document.createElement('p');uploadHint.className='hint';uploadHint.textContent='Upload to analyze automatically. Recognized BWA and SuSa layouts use verified format rules; other layouts use GPT. Scanned pages are read with OCR first. Enter changes, then recalculate and download. GPT analysis uses your OpenRouter credits.';$('file').after(uploadHint);
$('analyze').parentElement.querySelector('h2').textContent='1. Upload your document';
const amountLoading=document.createElement('p');amountLoading.className='hint amount-loading';amountLoading.setAttribute('role','status');amountLoading.setAttribute('aria-live','polite');amountLoading.hidden=true;
const spinner=document.createElement('span');spinner.className='amount-spinner';spinner.setAttribute('aria-hidden','true');amountLoading.append(spinner,document.createTextNode('Loading amounts from your document...'));$('input').after(amountLoading);
style.textContent+='.amount-loading{display:flex;align-items:center;gap:9px}.amount-spinner{display:inline-block;width:18px;height:18px;border:2px solid #dce2ec;border-top-color:#255bce;border-radius:50%;animation:amount-spin .8s linear infinite}@keyframes amount-spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.amount-spinner{animation:none}}';
const loadingControls=controls;controls=function(){loadingControls();const supported=statement()?.export_mode==='direct';if(analysis&&!supported)simulationToggle.checked=false;simulationToggle.disabled=busy||!supported;simulationHint.textContent=analysis&&!supported?'Proportional simulation currently supports annual DATEV BWA only. This document uses reviewed account formulas.':'Change one revenue or expense amount per month. Sales and all operating expenses in that month scale by the same percentage; totals recalculate. Export is labelled Simulation.';$('rasterWrap').hidden=!statement()?.cells.some(c=>c.mode==='ocr');if(!busy&&analysis&&simulationToggle.checked){try{$('affected').disabled=!payload().edits.length}catch{$('affected').disabled=false}}const loading=busy&&!analysis;amountLoading.hidden=!loading;$('input').setAttribute('aria-busy',String(loading));if(!analysis){const placeholder=new Option(loading?'Loading amounts...':pdf?'Amounts unavailable - retry analysis':'Upload a document to load amounts','');$('input').replaceChildren(placeholder);$('current').textContent='';$('value').value='';$('value').placeholder=loading?'Please wait for amounts to load':''}};
controls();
const formatNotice=document.createElement('p');formatNotice.className='hint';formatNotice.hidden=true;$('file').after(formatNotice);
const profileControls=controls;controls=function(){profileControls();formatNotice.hidden=!statement()?.profile;if(statement()?.profile){formatNotice.textContent=statement().profile==='datev_cash_basis'?'Cash-basis BWA: updates totals, percentages, comparisons and liquidity. Monthly edits also update year-to-date. Attached SuSa ledger pages remain unchanged source snapshots; tax amounts are independent.':'SuSa: add corresponding debit and credit movements to the same pending batch. Monthly edits also update year-to-date. Scanned export uses approximate fonts and requires image-export consent.';try{$('affected').disabled=busy||!payload().edits.length}catch{$('affected').disabled=busy} $('model').textContent='Recognized format: source-validated rules calculate these changes without an AI request.';if(!busy&&statement().discrepancies?.length){$('affected').disabled=true;status('Source discrepancies require review: '+statement().discrepancies.slice(0,5).join('; '),true)}}};
// A rendered page makes amount selection available for native PDFs and scans.
const interactive=document.createElement('div'),navigation=document.createElement('div'),pageChoice=document.createElement('select'),hint=document.createElement('p'),canvas=document.createElement('div'),selectionBox=document.createElement('div');
hint.className='hint';hint.textContent='Click an amount or drag a highlight over it to select its input.';
navigation.append(pageChoice);interactive.append(navigation,hint,canvas);$('original').before(interactive);interactive.hidden=true;
canvas.style.cssText='position:relative;touch-action:none;cursor:crosshair';
const image=$('selected');image.draggable=false;image.style.cssText='display:block;width:100%;height:auto;user-select:none';canvas.append(image,selectionBox);
selectionBox.style.cssText='position:absolute;border:2px solid #255bce;background:#255bce22;pointer-events:none;display:none';
let frame=null,start=null;
const selectionApi=api;api=async function(path,data){const r=await selectionApi(path,data);if(path==='/api/general/preview'&&r.width&&r.height){frame=r;interactive.hidden=false;$('original').hidden=true;pageChoice.replaceChildren(...Array.from({length:statement().pages},(_,i)=>new Option('Page '+(i+1),String(i+1))));pageChoice.value=String(r.page)}return r};
pageChoice.onchange=async()=>{if(busy)return;const c=statement()?.cells.find(c=>c.page===Number(pageChoice.value));if(!c){pageChoice.value=String(frame.page);status('No extracted amounts on that page. Use the full PDF viewer to inspect it.');return}busy=true;controls();try{const r=await api('/api/general/preview',{pdf,analysis,id:c.id});image.src='data:image/png;base64,'+r.image}catch(e){status(e.message,true)}finally{busy=false;controls()}};
const fullPdf=document.createElement('button');fullPdf.type='button';fullPdf.textContent='Show full PDF';navigation.append(fullPdf);fullPdf.onclick=()=>{$('original').hidden=!$('original').hidden;fullPdf.textContent=$('original').hidden?'Show full PDF':'Hide full PDF'};
function point(e){const b=image.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-b.left)/b.width)),Math.max(0,Math.min(1,(e.clientY-b.top)/b.height))]}
canvas.onpointerdown=e=>{if(e.button!==0||busy||!analysis||!frame)return;e.preventDefault();start=point(e);canvas.setPointerCapture(e.pointerId)};
canvas.onpointermove=e=>{if(!start)return;const end=point(e);selectionBox.style.display='block';selectionBox.style.left=100*Math.min(start[0],end[0])+'%';selectionBox.style.top=100*Math.min(start[1],end[1])+'%';selectionBox.style.width=100*Math.abs(start[0]-end[0])+'%';selectionBox.style.height=100*Math.abs(start[1]-end[1])+'%'};
canvas.onpointercancel=()=>{start=null;selectionBox.style.display='none'};
canvas.onpointerup=async e=>{
 if(!start)return;const end=point(e),origin=start;start=null;selectionBox.style.display='none';canvas.releasePointerCapture(e.pointerId);
 const bounds=image.getBoundingClientRect(),click=Math.abs(end[0]-origin[0])*bounds.width<4&&Math.abs(end[1]-origin[1])*bounds.height<4;
 const x0=Math.min(origin[0],end[0])*frame.width,y0=Math.min(origin[1],end[1])*frame.height,x1=Math.max(origin[0],end[0])*frame.width,y1=Math.max(origin[1],end[1])*frame.height;
 const matches=statement().cells.filter(c=>c.page===frame.page&&c.rotation===frame.rotation).filter(c=>{const [a,b,d,f]=c.box;return click?end[0]*frame.width>=a&&end[0]*frame.width<=d&&end[1]*frame.height>=b&&end[1]*frame.height<=f:Math.max(0,Math.min(x1,d)-Math.max(x0,a))*Math.max(0,Math.min(y1,f)-Math.max(y0,b))/((d-a)*(f-b))>=.5});
 if(matches.length!==1){status(matches.length?'Highlight a single amount to select its input.':'No amount selected. Click or highlight the printed amount.');return}
 const c=matches[0];if(c.editable===false||!Array.from($('input').options).some(o=>o.value===c.id)){status('This amount is calculated, read-only, or has insufficient OCR confidence. Select an editable source amount.');return}
 $('input').value=c.id;await selectInput();$('value').focus();$('value').select();
};
const selectionControls=controls;controls=function(){selectionControls();pageChoice.disabled=busy||!analysis;if(!analysis){interactive.hidden=true;$('original').hidden=false;frame=null}canvas.style.cursor=busy?'wait':'crosshair'};
})();
