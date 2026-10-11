const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map(),created=[];
class Element{
 constructor(){this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.textContent='';this.files=[{name:'sample.pdf'}]}
 set innerHTML(html){for(const m of html.matchAll(/id="([^"]+)"/g))elements.set(m[1],new Element());elements.get('profitLossKind').value='profit'}
 append(...items){this.children.push(...items)}
 after(){}
 replaceChildren(...items){this.children=items;this.value=items[0]?.value||''}
 get options(){return this.children}
 scrollIntoView(){}
}
function $(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id)}
const cells=[{id:'revenue',text:'2.000,00',value:'2000',context:'Revenue / Month',page:1,editable:true},{id:'staff',text:'500,00',value:'500',context:'Payroll / Month',page:1,editable:true},{id:'revenue_next',text:'2.000,00',context:'Revenue / Next month',page:1,editable:true},{id:'unrelated',text:'0,00',context:'Unrelated input',page:1,editable:true}];
const calls=[];
const context={document:{createElement:()=>{const e=new Element();created.push(e);return e},querySelector:()=> $('replacementLabel'),getElementById:id=>elements.get(id)},Option:function(text,value){this.textContent=text;this.value=value},$: $,analysis:null,pdf:'original',busy:false,resultUrl:null,
 statement:()=>({cells}),cell:id=>cells.find(c=>c.id===id),status:()=>{},table:()=>{},pdfUrl:()=> 'blob:result',URL:{revokeObjectURL:()=>{}},normalizeFinancialAmount:require('./amount-format.js').normalizeFinancialAmount,
 controls:()=>{$('value').disabled=context.busy;$('proportionalSimulation').disabled=context.busy},reset:()=>{context.analysis=null;context.controls()},invalidate:()=>{context.controls()},selectInput:async()=>{},payload:()=>({pdf:'original',analysis:context.analysis,edits:[],rules:[]}),
 api:async(path,data)=>{calls.push({path,data});if(path.endsWith('-options'))return {periods:[{id:'final_0',label:'Month',current:'1.500,00',sources:['revenue','staff']},{id:'final_1',label:'Next month',current:'2.000,00',sources:['revenue_next']},{id:'ytd',label:'Year to date',current:'3.500,00',sources:['revenue','staff','revenue_next']}],note:'Verified result',requires_counterpart:false};if(path.endsWith('-analyze'))return {analysis:{statement:{cells}}};if(path.endsWith('-preview'))return {changes:[],rules:[],profit_loss:{period:'Month',before:'1.500,00',after:'-1.000,00'}};if(path.endsWith('-apply'))return {pdf:'edited',changes:[],profit_loss:{period:'Month',after:'-1.000,00'}};throw Error(path)}
};
$('locale').value='de';$('input').value='staff';$('addPendingChange');$('affected').onclick=()=>{throw Error('Normal workflow should not run in target mode')};
vm.createContext(context);vm.runInContext(fs.readFileSync('finance-profit-loss.js','utf8'),context);
(async()=>{
 context.analysis=await context.api('/api/finance/workflow-analyze',{});context.controls();
 assert.equal($('profitLossEnabled').disabled,false);
 $('profitLossEnabled').checked=true;$('profitLossEnabled').onchange();
 assert.equal($('profitLossFields').hidden,false);assert.equal(elements.has('profitLossSource'),false);assert.match($('profitLossSourceInfo').textContent,/Payroll/);assert.equal($('value').disabled,true);assert.equal($('value').hidden,true);assert.equal($('replacementLabel').hidden,true);assert.equal($('addPendingChange').hidden,true);
 $('profitLossKind').value='loss';$('profitLossAmount').value='1000';$('profitLossAmount').oninput();
 assert.equal(context.payload().profit_loss.amount,'1.000,00');assert.equal(context.payload().profit_loss.kind,'loss');
 assert.equal(context.payload().profit_loss.source,'staff');
 $('profitLossPeriod').value='ytd';$('profitLossPeriod').onchange();$('profitLossAmount').value='1.000.000,00';$('profitLossAmount').oninput();
 assert.equal($('affected').disabled,false);assert.equal(context.payload().profit_loss.source,'staff');assert.equal(context.payload().profit_loss.period,'ytd');
 $('profitLossPeriod').value='final_0';$('profitLossPeriod').onchange();
 $('input').value='revenue_next';await context.selectInput();assert.equal($('profitLossPeriod').value,'final_1');assert.equal(context.payload().profit_loss.source,'revenue_next');
 $('input').value='unrelated';await context.selectInput();assert.equal($('affected').disabled,false);assert.equal(context.payload().profit_loss.source,'revenue_next');
 $('input').value='staff';await context.selectInput();assert.equal($('profitLossPeriod').value,'final_0');
 $('input').value='';context.controls();assert.equal($('affected').disabled,false);assert.equal(context.payload().profit_loss.source,'revenue');
 await $('affected').onclick();assert.equal(calls.at(-1).path,'/api/finance/profit-loss-preview');
 const create=created.find(e=>e.textContent==='Create PDF with these changes');
 assert.equal(create.disabled,false);await create.onclick();assert.equal(calls.at(-1).path,'/api/finance/workflow-apply');assert.equal(calls.at(-1).data.profit_loss.kind,'loss');assert.equal($('download').hidden,false);
 // A later input change clears review; switching off restores the normal input.
 $('profitLossAmount').value='2000';$('profitLossAmount').oninput();assert.equal(create.disabled,true);
 $('profitLossEnabled').checked=false;$('profitLossEnabled').onchange();
 assert.equal($('value').disabled,false);assert.equal($('value').hidden,false);assert.equal($('replacementLabel').hidden,false);assert.equal($('addPendingChange').hidden,false);assert.equal(context.payload().profit_loss,undefined);
 context.reset();assert.equal($('profitLossEnabled').checked,false);assert.equal($('profitLossFields').hidden,true);
 console.log('PASS: profit/loss controls, selected input, amount formatting, preview request, invalidation and reset');
})().catch(e=>{console.error(e);process.exitCode=1});
