const assert=require('node:assert/strict');
const {normalizeFinancialAmount:format}=require('./amount-format.js');
for(const [input,expected] of [['62315.78','62.315,78'],['62315','62.315,00'],['62,315.78','62.315,78'],['62.315,78','62.315,78'],['62.315.78','62.315,78'],['-1000.5','-1.000,50'],['1.234','1.234,00'],['00023,01','23,01'],['12345678901234567890.01','12.345.678.901.234.567.890,01']])assert.equal(format(input),expected);
assert.equal(format('473','de','S'),'473,00S');
assert.equal(format('1.234,56','en'),'1,234.56');
for(const input of ['1,234','12.3456','1.23.45','NaN','1e6',''])assert.throws(()=>format(input));
console.log('Amount formatting: exact cents, grouping, S/H suffixes and ambiguity checks passed.');
