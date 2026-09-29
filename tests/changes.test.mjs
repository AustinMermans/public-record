import test from 'node:test';
import assert from 'node:assert/strict';
import {changeEdition,filterChanges} from '../site/changes.mjs';

const item=(overrides={})=>({id:'one',domain:'Economic data',kind:'Revision to observed value',title:'Output',date:'2026-06-30',before:2,after:2.5,unit:'Percent',url:'https://example.gov/current',previous_url:'https://example.gov/prior',detail_url:'#economy?series=GDP',from_capture:'2026-09-26T12:00:00Z',to_capture:'2026-09-28T12:00:00Z',...overrides});
const data=(items=[],channels=[])=>({changes:{items,channels},series:[],financials:{companies:[{cik:'000001',name:'Example issuer'}]}});
const channel=(overrides={})=>({id:'gdp',label:'Output',domain:'Economic data',status:'compared',from_capture:'2026-09-26',to_capture:'2026-09-28',...overrides});
test('banking decimal-string changes retain their percentage, monetary and count units',()=>{
  for(const [unit,before,after,expected] of [['Percent','0.98','0.93','0.93%'],['USD millions','20000','20722','20,722 USD millions'],['Count','4240','4238','4,238 institutions']]){
    assert.ok(changeEdition(data([item({unit,before,after})])).includes(expected));
  }
});

test('filters are exact, intersect, sort by capture then period, and do not mutate input',()=>{
  const items=[item({id:'old',date:'2026-03-31'}),item({id:'company',domain:'Companies',cik:'000001'}),item({id:'latest'})];
  assert.deepEqual(filterChanges(items).map(x=>x.id),['company','latest','old']);
  assert.deepEqual(filterChanges(data(items),{company:'000001',domain:'Companies',kind:'Revision to observed value'}).map(x=>x.id),['company']);
  assert.equal(filterChanges(items,{company:'1'}).length,0);assert.equal(items[0].id,'old');
});
test('ledger paginates all records with shareable filter-preserving links and clamped pages',()=>{
  const items=Array.from({length:251},(_,i)=>item({id:String(i).padStart(3,'0'),domain:'Companies',cik:'000001'}));
  const html=changeEdition(data(items),{filters:{company:'000001',domain:'Companies'},page:2});
  assert.match(html,/Showing 101–200 of 251 matching items/);assert.equal((html.match(/<tr id="change-/g)||[]).length,100);
  assert.match(html,/#changes\?company=000001&amp;domain=Companies&amp;page=3/);
  assert.match(html,/tabindex="0" role="region" aria-label="Change ledger"/);
  const last=changeEdition(data(items),{page:999});assert.match(last,/Showing 201–251/);assert.equal((last.match(/<tr id="change-/g)||[]).length,51);
  assert.match(changeEdition(data(items),{page:NaN}),/Showing 1–100/);
});
test('the front shows active desks, groups court-feed entries by linked docket, and preserves the ledger',()=>{
  const items=[...Array.from({length:5},(_,i)=>item({id:'g'+i,title:'Metric '+i})),
    ...Array.from({length:4},(_,i)=>item({id:'court'+i,title:'Court '+i,domain:'Disclosures',source_id:i===3?'nysd':'cand',kind:i===3?'Record metadata changed':'Newly captured document',url:i<3?'https://court.gov/case/1':'https://court.gov/case/2'}))];
  const channels=[channel(),channel({id:'cand',label:'Northern California',domain:'Disclosures',from_capture:'2026-09-27T13:00:00Z',to_capture:'2026-09-28T14:30:00Z'}),channel({id:'nysd',label:'Southern New York',domain:'Disclosures',from_capture:'2026-09-29T18:51:48Z',to_capture:'2026-09-29T19:12:38Z'})];
  const compact=changeEdition(data(items,channels),{compact:true});
  assert.equal((compact.match(/class="change-desk(?: |")/g)||[]).length,2);
  assert.match(compact,/Showing 3 of 5 developments · 3 of 5 ledger items/);
  assert.match(compact,/4 ledger differences: 3 newly captured entries, 1 metadata change; 2 distinct docket links/);
  assert.match(compact,/3 ledger entries · 1 distinct docket link/);
  assert.match(compact,/Sep 27 9:00 AM EDT → Sep 28 10:30 AM EDT/);
  assert.match(compact,/Sep 29 · 2:51 PM–3:12 PM EDT/);
  assert.match(compact,/title="2026-09-29T18:51:48Z → 2026-09-29T19:12:38Z"/);
  assert.match(compact,/partial rolling feeds, not all filings or rulings/);
  assert.match(compact,/#changes\?domain=Disclosures&amp;source=cand/);
  assert.doesNotMatch(compact,/Court 0|Court 1|Court 2|Court 3/);
  assert.match(compact,/4 other desks without ledger entries · check comparison coverage/);
  assert.match(changeEdition(data(items,channels)),/Court 0/);
});
test('a court-only capture is visible on the front without implying a new ruling',()=>{
  const items=[item({id:'docket',domain:'Disclosures',source_id:'nysd',url:'https://court.gov/docket',kind:'Newly captured document'})];
  const html=changeEdition(data(items,[channel({id:'nysd',label:'Southern New York',domain:'Disclosures'})]),{compact:true});
  assert.match(html,/Court-feed activity/);assert.match(html,/1 ledger difference: 1 newly captured entry, 0 metadata changes/);assert.match(html,/not all filings or rulings/);
  assert.doesNotMatch(html,/4 other desks/);
  assert.match(html,/5 other desks without ledger entries/);
});
test('source filters are exact and survive ledger pagination links',()=>{
  const items=Array.from({length:105},(_,i)=>item({id:'d'+i,domain:'Disclosures',source_id:'nysd',url:'https://court.gov/'+i}));
  items.push(item({id:'other',domain:'Disclosures',source_id:'cand',url:'https://court.gov/other'}));
  assert.equal(filterChanges(items,{domain:'Disclosures',source:'nysd'}).length,105);
  const html=changeEdition(data(items,[channel({id:'nysd',label:'Southern New York',domain:'Disclosures'})]),{filters:{domain:'Disclosures',source:'nysd'}});
  assert.match(html,/#changes\?domain=Disclosures&amp;source=nysd&amp;page=2/);
  assert.match(html,/<option value="nysd" selected>Southern New York<\/option>/);
  assert.match(html,/Disclosures · Southern New York · Showing 1–100 of 105 matching items/);
});
test('calendar differences become a visible front desk while unavailable channels remain qualified',()=>{
  const html=changeEdition(data([item({id:'date-change',domain:'Calendar',title:'Release rescheduled',kind:'Schedule changed'})],
    [channel({id:'calendar',domain:'Calendar'}),channel({id:'bls',domain:'Calendar',status:'unavailable'}),channel({id:'fred',domain:'Economic data',status:'baseline'})]),{compact:true});
  assert.match(html,/<h3><a href="#changes\?domain=Calendar">Calendar<\/a><\/h3>/);
  assert.match(html,/Release rescheduled/);
  assert.match(html,/1 baseline; 0 unavailable/);
  assert.match(html,/without ledger entries · check comparison coverage/);
});
test('verified filing identities group across capture windows without deleting source ledger rows',()=>{
  const items=[item({id:'filing',domain:'Companies',cik:'000001',development_id:'filing:000001:abc',kind:'Newly captured filing',title:'Issuer report',before:undefined,after:undefined,form:'10-Q',report_period:'2026-06-30',filed:'2026-07-30',summary:'Revenue and balance-sheet update.'}),item({id:'financial',domain:'Companies',cik:'000001',development_id:'filing:000001:abc',kind:'Revised reported financial fact',title:'Issuer revenue',from_capture:'2026-09-01T12:00:00Z',before:1000000,after:1100000,unit:'USD'})];
  const html=changeEdition(data(items));assert.match(html,/Showing 1 of 1 developments · 2 of 2 ledger items/);assert.match(html,/1 related ledger entry/);assert.equal((html.match(/<tr id="change-/g)||[]).length,2);
  assert.match(html,/2026-09-01T12:00:00Z/);assert.match(html,/Revenue and balance-sheet update/);assert.match(html,/Report end 2026-06-30/);assert.match(html,/1,100,000 USD/);
});
test('derived fallback grouping requires exact issuer, period, accession and capture window',()=>{
  const fact=item({id:'fact',domain:'Companies',cik:'000001',accession:'abc',kind:'Revised reported financial fact'});
  const calc=item({...fact,id:'calc',kind:'Recalculated financial metric'});
  assert.match(changeEdition(data([fact,calc]),{compact:true}),/Showing 1 of 1 developments · 2 of 2 ledger items/);
  assert.match(changeEdition(data([fact,{...calc,accession:'other'}]),{compact:true}),/Showing 2 of 2 developments/);
});
test('bulk same-series revisions form one development led by newest affected period',()=>{
  const items=['2020-01-01','2025-01-01','2026-01-01'].map((date,i)=>item({id:'r'+i,series_id:'GDP',source_id:'fred-gdp',date}));
  const html=changeEdition(data(items),{compact:true});assert.match(html,/Showing 1 of 1 developments · 3 of 3 ledger items/);assert.ok(html.indexOf('2026-01-01')<html.indexOf('2020-01-01'));assert.match(html,/2 related ledger entries/);
});
test('empty states distinguish compared no-change, first baseline and unavailable channels',()=>{
  assert.match(changeEdition(data([],[channel()])),/No comparable changes in 1 compared channel/);
  const html=changeEdition(data([],[channel({status:'baseline'}),channel({id:'missing',status:'unavailable'})]));assert.match(html,/Not compared: no successful capture pair/);assert.match(html,/1 baseline; 1 unavailable/);assert.doesNotMatch(html,/No comparable changes/);
  assert.match(changeEdition(data([item()]),{filters:{domain:'Outlook'}}),/No items match these filters/);
});
test('coverage displays collection errors and unknown issuer labels use the supplied company',()=>{
  const html=changeEdition(data([item({cik:'000009',company:'New registrant',domain:'Companies'})],[channel({status:'unavailable',error:'HTTP 403: source refused request'})]));
  assert.match(html,/HTTP 403: source refused request/);assert.match(html,/<option value="000009">New registrant<\/option>/);
});
test('before and after values link to exact supplied evidence and horizons stay explicit',()=>{
  const html=changeEdition(data([item({domain:'Outlook',target:'2026 Q3',published_at:'2026-09-25',previous_published_at:'2026-09-20',comparison_boundary:true,summary:'Target boundary.'})]));
  assert.match(html,/href="https:\/\/example.gov\/prior"[^>]*>2%<\/a>/);assert.match(html,/href="https:\/\/example.gov\/current"[^>]*>2.5%<\/a>/);
  assert.match(html,/Forecast \/ target: 2026 Q3/);assert.match(html,/Prior publication 2026-09-20/);assert.match(html,/Comparison boundary; not a numerical revision/);
});
test('all content is escaped and unsafe source or detail URLs never become links',()=>{
  const html=changeEdition(data([item({title:'<script>alert(1)</script>',id:'"><script>',url:'javascript:alert(1)',previous_url:'javascript:bad()',detail_url:'javascript:bad()',before:'<img onerror=bad()>',summary:'<b>fake</b>'})],[channel({label:'<svg>'})]));
  assert.doesNotMatch(html,/<script>|<img|<svg>|href="javascript:/);assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;b&gt;fake&lt;\/b&gt;/);
});
test('exact decimal dollar strings remain readable without float coercion',()=>{
  const html=changeEdition({changes:{items:[{id:'dollar',domain:'Economic data',kind:'Revised fiscal value',title:'Treasury receipts',before:'9007199254740993.01',after:'9007199254740993.02',unit:'USD',url:'https://example.gov',from_capture:'2026-01-01',to_capture:'2026-01-02'}],channels:[]}});
  assert.match(html,/9,007,199,254,740,993\.01 USD/);
  assert.match(html,/9,007,199,254,740,993\.02 USD/);
});
