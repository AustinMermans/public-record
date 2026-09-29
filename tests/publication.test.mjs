import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {normalize,buildSearchIndex,searchIndex,companyMentions,companyPage,deskPage,publicationHome,searchResults} from '../site/publication.mjs';
const d=JSON.parse(fs.readFileSync(new URL('../data/current.json',import.meta.url)));
d.corporate=JSON.parse(fs.readFileSync(new URL('../data/corporate/current.json',import.meta.url)));
d.research=JSON.parse(fs.readFileSync(new URL('../data/research/current.json',import.meta.url)));
const index=buildSearchIndex(d),apple=d.corporate.companies.find(c=>c.cik==='0000320193');
test('fiscal search leads to the fiscal comparison rather than an unrelated macro series',()=>{
  const fixture={...d,fiscal:{edition:'2026-08-31',status:'ok',metrics:[{id:'balance',label:'Surplus / deficit'}]}};
  const hits=searchIndex(buildSearchIndex(fixture),'federal deficit','indicator');
  assert.equal(hits.length,1);
  assert.equal(hits[0].url,'#fiscal?view=fytd&metric=balance');
  const government=deskPage(fixture,'government',{kpi:()=>'',brief:()=>'',agenda:()=>'',nextEvents:()=>[]});
  assert.match(government,/#fiscal/);
});
test('publication dates use Eastern days for timestamps and preserve date-only records',()=>{
  const record={id:'rollover',source_id:'court',domain:'Legal',kind:'Docket entry',title:'Example v. Example',summary:'[Notice of Appearance]',publisher:'Example court',url:'https://court.example/entry',date:'2026-09-28T03:59:18+00:00'};
  const fixture={...d,sources:[],records:[record]};
  const context={kpi:()=>'',brief:()=>'',agenda:()=>'',nextEvents:()=>[]};
  assert.match(deskPage(fixture,'disclosures-home',context),/2026-09-27/);
  assert.doesNotMatch(deskPage(fixture,'disclosures-home',context),/2026-09-28/);
  for(const [input,expected] of [['2026-09-28T03:59:18+00:00','2026-09-27'],['2026-01-01T04:30:00+00:00','2025-12-31'],['2026-09-28','2026-09-28']]) {
    const html=searchResults([{kind:'record',title:'Test entry',url:record.url,date:input}]);
    assert.match(html,new RegExp(expected));
  }
});
test('search ranks exact ticker/CIK profiles first and supports filing terms',()=>{
  for(const q of ['AAPL','0000320193','320193','Apple'])assert.equal(searchIndex(index,q)[0].url,'#company?cik=0000320193');
  const filings=searchIndex(index,'AAPL 10-K','filing');
  assert.ok(filings.length);assert.ok(filings.every(r=>r.title.includes('10-K')));
  assert.equal(searchIndex(index,'', '').length,0);
});
test('matching treats names/tickers as complete tokens, not substrings',()=>{
  assert.equal(normalize('Berkshire-Hathaway, Inc.'),'berkshire hathaway inc');
  assert.equal(searchIndex([{kind:'record',text:'pineapple',title:'Pineapple'}],'apple').length,0);
  assert.equal(companyMentions({records:[{title:'Pineapple market'},{title:'Apple Inc. v. Example'}]},apple).length,1);
});
test('distinct court entries sharing a docket URL remain searchable',()=>{
  assert.equal(index.filter(r=>r.kind==='record').length,d.records.length);
  const fixture={corporate:{companies:[]},sources:[],series:[],events:[],records:[{id:'a',title:'Example notice',url:'https://court.example/case/1'},{id:'b',title:'Example petition',url:'https://court.example/case/1'}]};
  assert.equal(searchIndex(buildSearchIndex(fixture),'petition').length,1);
});
test('profile continuation preserves its exact lexical-mention set',()=>{
  const ids=new Set(companyMentions(d,apple).map(r=>r.id));
  const rows=index.filter(r=>r.kind==='record'&&ids.has(r.recordId));
  assert.equal(rows.length,ids.size);
  if(ids.size>6)assert.ok(companyPage(d,apple.cik).includes('#search?mentions='+apple.cik));
});
test('company profiles distinguish CIK filings from unverified name matches',()=>{
  const html=companyPage(d,apple.cik);
  assert.match(html,/linked by SEC CIK/);assert.match(html,/not verified entity links/);
  assert.match(companyPage(d,'unknown'),/not in current coverage/);
  assert.match(html,/#corporate\?company=0000320193/);
});
test('all desk fronts render and shared homepage spans subjects',()=>{
  const ctx={kpi:id=>id,brief:()=>'',agenda:()=>'',nextEvents:()=>[]};
  for(const route of ['economy-home','business','government','disclosures-home','outlook-home','changes-home','news'])assert.match(deskPage(d,route,ctx),/<h1>/);
  const html=publicationHome(d,ctx);
  for(const title of ['Business','Economy','Government','Disclosures','Outlook','Changes','News'])assert.ok(html.includes(title));
  assert.match(deskPage(d,'news',ctx),/not independent news reporting/);
  assert.match(deskPage(d,'government',ctx),/not yet collected/);
});
test('search indexed company links resolve to known CIKs and external links remain source links',()=>{
  for(const row of index){assert.ok(row.url.startsWith('#')||row.url.startsWith('https://'));if(row.kind==='company')assert.ok(d.corporate.companies.some(c=>row.url.endsWith(c.cik)));}
});
