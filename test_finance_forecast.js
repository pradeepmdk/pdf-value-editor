const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),created=[];
class Element{
 constructor(){this.children=[];this.value='';this.textContent='';this.checked=false;this.disabled=false;this.hidden=false;this.files=[{name:'cash.pdf'}]}
 set innerHTML(html){for(const m of html.matchAll(/id="([^"]+)"/g))nodes.set(m[1],new Element());get('expensePlanning').checked=true}
 append(...items){for(const item of items){if(typeof item==='object')item.parent=this;this.children.push(item)}}
 after(){}
 before(...items){this.insertedBefore=items}
 replaceChildren(...items){this.children=[];this.append(...items);this.value=items[0]?.value||''}
 get options(){return this.children}
 scrollIntoView(){}
 querySelector(){return get('heading')}
 remove(){this.parent.children=this.parent.children.filter(c=>c!==this)}
}
function get(id){if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)}
const cells=[{id:'revenue_0',text:'100,00',context:'Revenue / Month',editable:true},{id:'revenue_12',text:'1.200,00',context:'Annual income',editable:false}];
const calls=[];
const context={document:{createElement:()=>{const n=new Element();created.push(n);return n}},Option:function(text,value){const n=new Element();n.textContent=text;n.value=value;return n},$:get,analysis:{},pdf:'source',busy:false,aiEnabled:true,resultUrl:null,
 statement:()=>({export_mode:'direct',cells}),cell:id=>cells.find(c=>c.id===id),controls:()=>{get('affected').disabled=context.busy},invalidate:()=>context.controls(),reset:()=>{context.analysis=null;context.controls()},
 payload:()=>({pdf:'source',analysis:context.analysis,edits:[{id:get('input').value,value:get('value').value}]}),selectInput:async()=>{},status:()=>{},table:()=>{},pdfUrl:()=> 'blob:clean',URL:{revokeObjectURL:()=>{}},displayModifiedPdf:()=>{get('result').src='blob:highlighted'},setTimeout:fn=>{fn();return 0},
 api:async(path,data)=>{calls.push({path,data});if(path.endsWith('-start'))return {job:'job'};if(path.endsWith('/analysis-job'))return {state:'complete',result:{summary:'Planning',note:'Review sources',accounts:[],changes:[],sales_change:[{column:'Month',change_percent:'5.00'}],research:{document_year:'2025',region:'Germany',industry:'Trade',indicators:[{name:'CPI',change_percent:'2.2',period:'2025',source_title:'Destatis',source_url:'https://www.destatis.de/cpi'}]},scenario:{signature:'signed'}}};if(path.endsWith('-apply'))return {pdf:'pdf',changes:[],note:'Planning simulation'};throw Error(path)}
};
get('input').replaceChildren(new context.Option('Revenue','revenue_0'));get('value').value='200,00';get('affected').onclick=()=>{};
vm.createContext(context);vm.runInContext(fs.readFileSync('finance-forecast.js','utf8'),context);
(async()=>{
 assert.equal(nodes.has('profitLossEnabled'),false);assert.equal(get('expensePlanning').checked,true);context.window={appLanguage:()=>'de'};
 await get('affected').onclick();assert.equal(calls[0].path,'/api/finance/scenario-start');assert.equal(calls[0].data.language,'de');
 const list=created.find(n=>n.children.some(c=>c.children?.some(a=>a.href==='https://www.destatis.de/cpi')));assert.ok(list,'source link listed');
 const create=created.find(n=>n.textContent.includes('I reviewed'));assert.equal(get('resultWrap').insertedBefore[0].id,'expenseReview');assert.equal(create.disabled,false);await create.onclick();
 assert.equal(calls.at(-1).path,'/api/finance/scenario-apply');assert.equal(calls.at(-1).data.scenario.signature,'signed');assert.equal(calls.at(-1).data.reviewed,true);assert.equal(get('result').src,'blob:highlighted');assert.match(get('download').download,/ai-scenario/);
 context.invalidate();assert.equal(create.disabled,true);
 get('expensePlanning').checked=false;get('expensePlanning').onchange();assert.equal(get('affected').textContent,'Recalculate & create PDF');
 console.log('PASS: AI scenario default, language passed, sources listed, reviewed export, highlights, invalidation and plain recalculation fallback');
})().catch(e=>{console.error(e);process.exitCode=1});
