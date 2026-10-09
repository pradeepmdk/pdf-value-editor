/* Exact string formatting: never use floating-point arithmetic or round cents. */
function normalizeFinancialAmount(input,locale='de',originalSuffix=''){
 if(!['de','en'].includes(locale))throw Error('Choose German or International number format.');
 let text=String(input).trim().replace(/\s/g,'');
 const suffixMatch=text.match(/[SH]$/i),suffix=suffixMatch?suffixMatch[0].toUpperCase():originalSuffix;
 if(suffixMatch)text=text.slice(0,-1);
 if(!/^[+-]?\d[\d.,]*$/.test(text))throw Error('Enter a numeric amount, for example 62315.78 or 62.315,78.');
 const sign=text[0]==='-'?'-':'';text=text.replace(/^[+-]/,'');
 const preferredDecimal=locale==='de'?',':'.',preferredGroup=locale==='de'?'.':',';
 const separators=[...text.matchAll(/[.,]/g)],last=separators.at(-1);
 let integer=text,fraction='00';
 if(last){const tail=text.slice(last.index+1),kinds=new Set(separators.map(m=>m[0]));
  if(tail.length===1||tail.length===2){integer=text.slice(0,last.index);fraction=tail.padEnd(2,'0')}
  else if(tail.length===3&&kinds.size===1&&last[0]===preferredGroup){integer=text}
  else throw Error('Ambiguous separators or more than two decimal places. Use '+(locale==='de'?'1.234,56.':'1,234.56.'));
 }
 if(/[.,]/.test(integer)){
  const groups=integer.split(/[.,]/);
  if(!/^\d{1,3}$/.test(groups[0])||groups.slice(1).some(g=>!/^\d{3}$/.test(g)))throw Error('Invalid thousands grouping. Check the amount before continuing.');
  integer=groups.join('');
 }
 integer=integer.replace(/^0+(?=\d)/,'');
 return sign+integer.replace(/\B(?=(\d{3})+(?!\d))/g,preferredGroup)+preferredDecimal+fraction+suffix;
}
if(typeof module!=='undefined')module.exports={normalizeFinancialAmount};
