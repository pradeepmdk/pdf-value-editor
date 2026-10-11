const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
class Element{
 constructor(){this.children=[];this._value='';this.hidden=false;this.checked=false;this.disabled=false}
 get value(){return this._value}
 set value(v){this._value=v}
 append(...items){this.children.push(...items);if(!this._value)this._value=this.children[0]?.value||''}
 replaceChildren(...items){this.children=items;this._value=items[0]?.value||''}
 removeAttribute(){}
 setAttribute(){}
 after(){}
 scrollIntoView(){}
 set innerHTML(html){for(const m of html.matchAll(/id="([^"]+)"/g))elements.set(m[1],new Element());get('profitLossKind').value='profit'}
 get options(){return this.children}
}
const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
const source={analysis:{statement:{locale:'de',pages:1,notes:[],export_mode:'native',cells:[
 {id:'c1',text:'2.837,82',context:'Revenue / Month',page:1,editable:true,mode:'text'},
 {id:'c2',text:'100,00',context:'Calculated total',page:1,editable:false,mode:'text'}]}}};
const context={document:{getElementById:get,createElement:()=>new Element(),querySelector:()=>get('replacementLabel')},Option:function(text,value){this.textContent=text;this.value=value},normalizeFinancialAmount:require('./amount-format.js').normalizeFinancialAmount,
 fetch:async()=>({json:async()=>({enabled:true})}),URL:{revokeObjectURL:()=>{}},simulationToggle:new Element(),simulationHint:new Element(),amountLoading:new Element()};
vm.createContext(context);
const html=fs.readFileSync('finance.html','utf8');vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
// Exercise the actual loading wrapper together with the real analysis handler.
const loading=fs.readFileSync('finance-preview.js','utf8').split(/\r?\n/).find(line=>line.startsWith('const loadingControls=controls;'));
vm.runInContext(loading,context);context.source=source;
vm.runInContext("pdf='original';api=async(path)=>path.endsWith('-analyze')?source:path.endsWith('-options')?{periods:[{id:'month',label:'Month',current:'-11.613,65',sources:['c1']},{id:'ytd',label:'Year to date',current:'-34.873,94',sources:['c1']}],requires_counterpart:false,note:'Verified result'}:{image:'preview',page:1};",context);
vm.runInContext(fs.readFileSync('finance-profit-loss.js','utf8'),context);
(async()=>{
 await get('analyze').onclick();
 assert.equal(get('input').value,'c1');assert.equal(get('input').options.length,1);assert.equal(get('input').options[0].textContent.includes('Loading'),false);
 assert.equal(get('value').value,'2.837,82');assert.equal(get('selected').src,'data:image/png;base64,preview');assert.equal(get('input').disabled,false);
 get('profitLossEnabled').checked=true;get('profitLossEnabled').onchange();get('profitLossPeriod').value='ytd';get('profitLossPeriod').onchange();get('profitLossAmount').value='100.000,00';get('profitLossAmount').oninput();
 assert.equal(get('affected').disabled,false);
 get('input').replaceChildren(new context.Option('Loading amounts...',''));context.controls();
 assert.equal(get('input').value,'c1');
 assert.equal(get('affected').disabled,false);assert.equal(context.payload().profit_loss.source,'c1');assert.equal(context.payload().profit_loss.period,'ytd');
 console.log('PASS: real analysis/loading/profit handlers clear the loading placeholder and enable a 100.000,00 year-to-date target without manual input selection');
})().catch(e=>{console.error(e);process.exitCode=1});
