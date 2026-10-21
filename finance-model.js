/* A browser preference, carried on every request rather than server-global. */
(()=>{
 const select=document.createElement('select'),label=document.createElement('label'),hint=document.createElement('p');
 select.id='aiModel';label.htmlFor=select.id;label.textContent='AI model';
 select.style.cssText='max-width:360px;margin-bottom:8px';hint.className='hint';
 hint.textContent='Used for AI analysis and realistic expense assumptions. Model pricing varies; calculations remain verified locally.';
 document.querySelector('main > h1').after(label,select,hint);
 let chosen='openai/gpt-4.1';
 select.append(new Option('OpenAI GPT-4.1',chosen));
 const previousApi=api;
 api=async function(path,data){return previousApi(path,{...data,ai_model:chosen})};
 const previousControls=controls;
 controls=function(){previousControls();select.disabled=busy};
 select.onchange=()=>{
  chosen=select.value;try{localStorage.setItem('financeAIModel',chosen)}catch{}
  invalidate();
  window.dispatchEvent(new Event('finance-model-change'));
  status('AI model changed. New AI requests will use '+select.selectedOptions[0].textContent+'.');
 };
 fetch('/api/finance/models').then(r=>{if(!r.ok)throw Error('Unable to load AI models');return r.json()}).then(result=>{
  let saved;try{saved=localStorage.getItem('financeAIModel')}catch{}
  chosen=result.models.some(v=>v.id===saved)?saved:result.default;
  select.replaceChildren(...result.models.map(v=>new Option(v.name,v.id)));
  select.value=chosen;controls();
 }).catch(()=>{hint.textContent='Model list unavailable. GPT-4.1 remains selected; refresh to retry.'});
})();
