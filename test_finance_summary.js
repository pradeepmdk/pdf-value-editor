const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),created=[],calls=[];let fail=false;
class Element{
 constructor(){this.children=[];this.value='';this.textContent='';this.hidden=false;this.dataset={};this.style={}}
 append(...items){this.children.push(...items);if(!this.value)this.value=items[0]?.value||''}
 after(){}
 before(){}
 replaceChildren(...items){this.children=items}
 setAttribute(){}
 scrollIntoView(){}
 focus(){}
 select(){}
 get options(){return this.children}
 querySelectorAll(){return [get('uploadHint')]}
}
function get(id){if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)}
get('file').parentElement=new Element();get('uploadHint').textContent='Upload to analyze automatically.';
const result=lang=>({language:lang,summary:{title:lang==='de'?'Dokumentübersicht':'Document overview',overview:'Description',highlights:[],cautions:[],cost_labels:[{key:'phone',label:lang==='de'?'Telefon':'Telephone'}]},facts:{pages:1,fields:2,source_verified:true,periods:[{kind:'ytd',metrics:[{key:'income',amount:'1.000,00',computed:false,ids:['c1']}],costs:[{key:'phone',label:'Telefon',amount:'10,00'}]}]}});
const context={document:{createElement:()=>{const e=new Element();created.push(e);return e},querySelector:()=>get('mainTitle'),getElementById:get},Option:function(text,value){this.textContent=text;this.value=value},$:get,localStorage:{getItem:()=>null,setItem:()=>{}},pdf:'pdf',busy:false,cell:id=>id==='c1'?{id,editable:true,text:'1.000,00'}:null,statement:()=>({}),controls:()=>{},selectInput:async()=>{calls.push({path:'select-input',id:get('input').value})},table:()=>{},reset:()=>{},setTimeout:fn=>{fn();return 0},
 api:async(path,data)=>{calls.push({path,data});if(path.endsWith('-analyze'))return {analysis:{statement:{}}};if(path.endsWith('-start'))return {job:data.language};if(path.endsWith('/analysis-job')){if(fail)throw Error('Service unavailable');return {state:'complete',result:result(data.job)}}throw Error(path)}};
context.controls=()=>{get('input').disabled=false;get('value').disabled=false;get('affected').disabled=false};
const events={};context.window={addEventListener:(name,handler)=>{events[name]=handler}};
vm.createContext(context);vm.runInContext(fs.readFileSync('finance-summary.js','utf8'),context);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const select=created.find(n=>n.id==='analysisLanguage');assert.equal(select.value,'en');
 assert.equal(get('input').disabled,true);assert.equal(get('input').options[0].value,'');assert.match(get('input').options[0].textContent,/Waiting for analysis/);
 await context.api('/api/finance/workflow-analyze',{});await flush();
 assert.equal(get('input').disabled,false);assert.equal(get('value').disabled,false);
 assert.equal(get('input').options.length,1);assert.equal(get('input').options[0].value,'c1');assert.match(get('input').options[0].textContent,/Income.*Year to date/);
 get('input').append(new context.Option('Unrelated raw value','other'));context.controls();assert.equal(get('input').options.length,1);
 const amount=created.find(n=>n.textContent==='1.000,00'&&typeof n.onclick==='function');assert.ok(amount);await amount.onclick();assert.equal(get('input').value,'c1');assert.equal(calls.at(-1).path,'select-input');
 assert.equal(calls.some(c=>c.path==='/api/finance/summary-start'&&c.data.language==='en'),true);
 assert.equal(get('uploadHint').textContent.includes('not the PDF file'),true);
 select.value='de';select.onchange();await flush();assert.equal(calls.at(-1).data.job,'de');
 assert.equal(created.some(n=>n.textContent==='Dokumentübersicht'),true);
 const count=calls.length;select.value='en';select.onchange();await flush();assert.equal(calls.length,count);
 context.reset();fail=true;await context.api('/api/finance/workflow-analyze',{});await flush();
 assert.equal(created.some(n=>n.textContent.includes('AI summary unavailable: Service unavailable')),true);
 assert.equal(get('input').disabled,true);assert.equal(get('value').disabled,true);assert.equal(get('affected').disabled,true);assert.equal(get('input').options[0].value,'');
 console.log('PASS: automatic upload summary, English/German switching, cached translations and independent AI error handling');
})().catch(e=>{console.error(e);process.exitCode=1});
