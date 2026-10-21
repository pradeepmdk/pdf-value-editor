/* App-wide English/German switch. Source text is English; German comes from
   window.I18N_DE (i18n-de.js). Text, attributes and dialogs are translated in
   place, including text that scripts or server messages add later, and are
   restored when switching back. Keys may contain {1}, {2}… placeholders. */
(()=>{
const DE=window.I18N_DE||{},exact=new Map(),patterns=[];
for(const [en,de] of Object.entries(DE)){
 if(!/\{\d+\}/.test(en)){exact.set(en,de);continue}
 const names=[],source=en.split(/(\{\d+\})/).map(part=>{const m=part.match(/^\{(\d+)\}$/);if(m){names.push(m[1]);return '(.+?)'}return part.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}).join('');
 patterns.push({re:new RegExp('^'+source+'$','s'),names,de,size:en.replace(/\{\d+\}/g,'').length});
}
patterns.sort((a,b)=>b.size-a.size);
// Server messages are often a fixed sentence followed by details.
const prefixes=[...exact.keys()].filter(k=>k.length>10&&/[:.]$/.test(k)).sort((a,b)=>b.length-a.length);
function one(text){
 if(exact.has(text))return exact.get(text);
 for(const p of patterns){const m=text.match(p.re);if(!m)continue;let out=p.de;p.names.forEach((name,i)=>{out=out.split('{'+name+'}').join(translate(m[i+1]))});return out}
 return null;
}
function translate(text){
 if(typeof text!=='string')return text;
 const core=text.trim();if(!core||!/[A-Za-z]/.test(core))return text;
 let out=one(core);
 if(out==null)for(const k of prefixes)if(core.startsWith(k)&&core.length>k.length){out=exact.get(k)+' '+translate(core.slice(k.length).trim());break}
 if(out==null){const parts=core.split(/(?<=[.!?])\s+(?=[A-Z"(])/);if(parts.length>1){const done=parts.map(p=>one(p)??p);if(done.some((v,i)=>v!==parts[i]))out=done.join(' ')}}
 return out==null?text:text.match(/^\s*/)[0]+out+text.match(/\s*$/)[0];
}

let lang='en';
try{lang=localStorage.getItem('appLanguage')||localStorage.getItem('financeAnalysisLanguage')||''}catch{}
if(lang!=='de'&&lang!=='en')lang=(navigator.language||'').toLowerCase().startsWith('de')?'de':'en';
window.appLanguage=()=>lang;
window.appTranslate=text=>lang==='de'?translate(text):text;
for(const name of ['alert','confirm','prompt']){const original=window[name];if(original)window[name]=(message,...rest)=>original.call(window,window.appTranslate(String(message??'')),...rest)}

const ATTRS=['placeholder','title','aria-label','alt'],texts=new WeakMap(),attrs=new WeakMap();
let englishTitle=null;
function skipped(el){return !el||!!el.closest('script,style,textarea,[data-no-translate]')}
function text(node){
 if(skipped(node.parentElement))return;
 let state=texts.get(node);
 if(!state||state.shown!==node.nodeValue){state={source:node.nodeValue};texts.set(node,state)}
 const value=lang==='de'?translate(state.source):state.source;
 state.shown=value;if(node.nodeValue!==value)node.nodeValue=value;
}
function attribute(el,name){
 let state=attrs.get(el);if(!state){state={};attrs.set(el,state)}
 const current=el.getAttribute(name);if(current==null)return;
 if(!state[name]||state[name].shown!==current)state[name]={source:current};
 const value=lang==='de'?translate(state[name].source):state[name].source;
 state[name].shown=value;if(current!==value)el.setAttribute(name,value);
}
function element(el){
 if(skipped(el))return;
 for(const name of ATTRS)if(el.hasAttribute(name))attribute(el,name);
 if(el.tagName==='INPUT'&&/^(button|submit|reset)$/i.test(el.type))attribute(el,'value');
}
function walk(root){
 if(root.nodeType===3)return text(root);
 if(root.nodeType!==1||skipped(root))return;
 element(root);
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_ELEMENT|NodeFilter.SHOW_TEXT);let node;
 while((node=walker.nextNode()))node.nodeType===3?text(node):element(node);
}
function apply(){
 document.documentElement.lang=lang;
 if(englishTitle==null)englishTitle=document.title;
 document.title=lang==='de'?translate(englishTitle):englishTitle;
 walk(document.body);
}
function start(){
 const box=document.createElement('label'),select=document.createElement('select');
 box.setAttribute('data-no-translate','');box.id='appLanguageSwitch';
 box.style.cssText='position:fixed;top:10px;right:14px;z-index:1000;display:flex;gap:6px;align-items:center;margin:0;width:auto;padding:4px 8px;background:#fff;border:1px solid #c9d2e3;border-radius:8px;font:14px system-ui;color:#17243b;box-shadow:0 1px 3px #0002';
 box.append('Sprache / Language',select);
 select.style.cssText='width:auto;margin:0;padding:3px 6px;font:inherit';select.setAttribute('aria-label','Sprache / Language');
 select.append(new Option('English','en'),new Option('Deutsch','de'));select.value=lang;
 select.onchange=()=>{
  lang=select.value;try{localStorage.setItem('appLanguage',lang)}catch{}
  apply();window.dispatchEvent(new CustomEvent('app-language-change',{detail:lang}));
 };
 document.body.append(box);apply();
 new MutationObserver(records=>{for(const r of records){
  if(r.type==='characterData')text(r.target);
  else if(r.type==='attributes')element(r.target);
  else r.addedNodes.forEach(walk);
 }}).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:[...ATTRS,'value']});
}
if(document.body)start();else document.addEventListener('DOMContentLoaded',start);
})();
