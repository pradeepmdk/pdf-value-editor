/* Multiple independent inputs, always calculated together from the original. */
(()=>{
const edits=new Map(),add=document.createElement('button'),list=document.createElement('div');
add.textContent='Add / update pending change';$('value').after(add,list);
function render(){list.replaceChildren();if(!edits.size)return;const heading=document.createElement('h3');heading.textContent=`Pending changes (${edits.size})`;list.append(heading);for(const [id,value] of edits){const row=document.createElement('p'),text=document.createElement('span'),remove=document.createElement('button');text.textContent=`${field(id)}: ${cell(id)?.text||''} → ${value}`;remove.textContent='Remove';remove.style.cssText='width:auto;padding:5px 10px;margin:5px';remove.disabled=busy;remove.onclick=()=>{edits.delete(id);invalidate();render()};row.append(text,remove);list.append(row)}}
const oldControls=controls;controls=function(){oldControls();add.disabled=busy||!analysis;render()};
const oldReset=reset;reset=function(){edits.clear();oldReset();render()};
add.onclick=()=>{const id=$('input').value,value=$('value').value.trim();if(!cell(id)||!value||value===cell(id).text){status('Enter an amount different from the original before adding a change.',true);return}if(!edits.has(id)&&edits.size>=30){status('A batch supports up to 30 changed inputs.',true);return}edits.set(id,value);invalidate();render();status(`${edits.size} pending change(s). Select another field to add more, then identify dependencies for all changes.`)};
const oldPayload=payload;payload=function(){const p=oldPayload(),current=p.edits[0],all=new Map(edits);if(cell(current.id)&&current.value.trim()!==cell(current.id).text)all.set(current.id,current.value);p.edits=[...all].map(([id,value])=>({id,value}));return p};
const note=document.createElement('p');note.className='hint';note.textContent='Add several independent changes before analysis. They are calculated together. AI dependency review may use one paid request per changed input.';list.after(note);
controls();
})();
