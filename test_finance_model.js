const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=[],calls=[],events=[];let invalidations=0;
class Element{
 constructor(){this.children=[];this.style={}}
 append(...v){this.children.push(...v)}
 after(){}
 replaceChildren(...v){this.children=v}
 get selectedOptions(){return this.children.filter(v=>v.value===this.value)}
}
const models=[{id:'openai/gpt-4.1',name:'GPT-4.1'},{id:'google/gemini-4-argon',name:'Gemini 4 Argon'}];
const ctx={document:{createElement:()=>{const e=new Element();nodes.push(e);return e},querySelector:()=>new Element()},
 Option:function(text,value){this.textContent=text;this.value=value},localStorage:{getItem:()=>models[1].id,setItem:()=>{}},
 api:async(path,data)=>{calls.push({path,data});return data},controls:()=>{},busy:false,
 invalidate:()=>{invalidations++},status:()=>{},window:{dispatchEvent:e=>events.push(e.type)},Event:function(type){this.type=type},
 fetch:async()=>({ok:true,json:async()=>({models,default:models[0].id})})};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('finance-model.js','utf8'),ctx);
(async()=>{
 await new Promise(r=>setImmediate(r));const select=nodes.find(v=>v.id==='aiModel');
 assert.equal(select.value,models[1].id);
 await ctx.api('/api/finance/summary-start',{language:'en'});assert.equal(calls.at(-1).data.ai_model,models[1].id);
 select.value=models[0].id;select.onchange();assert.equal(invalidations,1);assert.deepEqual(events,['finance-model-change']);
 await ctx.api('/api/finance/forecast-start',{});assert.equal(calls.at(-1).data.ai_model,models[0].id);
 ctx.busy=true;ctx.controls();assert.equal(select.disabled,true);
 console.log('PASS model preference, request routing, invalidation and busy state');
})().catch(e=>{console.error(e);process.exitCode=1});
