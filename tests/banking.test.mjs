import test from 'node:test';
import assert from 'node:assert/strict';
import {bankingPanel,bankingTeaser} from '../site/banking.mjs';
import {fundingPage} from '../site/funding.mjs';

const NOW=Date.parse('2026-09-29T12:00:00Z'),url='https://www.fdic.gov/qbp.xlsx';
const p=(date,value,extra={})=>({date,value,cell:'G10',url,...extra});
function measure(id,value,prior,year){
  const unit=['deposits','assets','net_income'].includes(id)?'USD millions':id==='institutions'?'Count':'Percent';
  return {id,label:id,unit,frequency:'Quarterly',annualized:['nco','roa'].includes(id),stock_flow:['nco','roa','net_income'].includes(id)?'flow':'stock',definition:id+' published definition',sheet:'All Insured Institutions',row_label:id,population:'All Insured Institutions',current:p('2026-06-30',value),prior:p('2026-03-31',prior),year_ago:p('2025-06-30',year),observations:[p('2025-06-30',year),p('2026-03-31',prior),p('2026-06-30',value)]};
}
function bundle(extra={}){return {status:'ok',captured_at:'2026-09-29T00:00:00Z',last_success:'2026-09-29T00:00:00Z',edition:'2026 Q2',quarter_end:'2026-06-30',url,notes_url:'https://www.fdic.gov/notes.pdf',population:'FDIC-insured commercial banks and savings institutions',validation:{status:'reconciled'},metrics:[measure('noncurrent','0.93','0.90','0.89'),measure('nco','0.63','0.65','0.69'),measure('coverage','172.68','174.50','171.00'),measure('roa','1.25','1.20','1.10'),measure('equity_assets','9.92','9.80','9.90'),measure('deposits','20000000','19900000','19000000')],context:[measure('institutions','4430','4450','4500'),measure('assets','26462210','26000000','25000000'),measure('net_income','80000','75000','70000')],...extra};}
const render=(b,opts={})=>bankingPanel({banking:b},{now:NOW,...opts});

test('six-metric table retains quarter and units, with nine internal history choices',()=>{
  const html=render(bundle());assert.match(html,/Current · 2026-06-30/);assert.match(html,/Prior quarter · 2026-03-31/);assert.match(html,/Year ago · 2025-06-30/);
  assert.match(html,/20,000.00 USD bn/);assert.match(html,/0.93%/);assert.match(html,/1.25%/);assert.equal((html.match(/<option value=/g)||[]).length,9);
  assert.match(html,/#funding\?view=banking&metric=net_income/);assert.match(html,/data-banking-metric="assets"/);assert.match(html,/tabindex="0" role="region" aria-label="Banking conditions comparison"/);
});
test('mixed movements describe metrics, without a composite health judgement',()=>{
  const html=render(bundle());assert.match(html,/Noncurrent loan share rose while the quarterly net charge-off rate fell/);assert.match(html,/Reserve coverage fell and bank equity\/assets rose/);assert.doesNotMatch(html,/system is healthy|system is distressed|health score: /i);
});
test('missing values remain unavailable while real zero is preserved',()=>{
  const b=bundle();b.metrics[0].current.value='0';b.metrics[0].prior.value='0';b.metrics[1].current.value=null;
  const html=render(b);assert.match(html,/Noncurrent loan share was unchanged/);assert.match(html,/>0.00%<\/a>/);assert.match(html,/Unavailable/);assert.doesNotMatch(html,/NaN|undefined/);
});
test('period comparisons require exact adjacent and year-ago quarter ends',()=>{
  const b=bundle();b.metrics[0].prior=p('2025-12-31','7.77');b.metrics[0].year_ago=p('2025-03-31','8.88');
  const html=render(b);assert.doesNotMatch(html,/7.77%|8.88%|Noncurrent loan share rose/);assert.match(html,/Unavailable/);
});
test('performance ratios must be explicitly annualized and are never reannualized',()=>{
  const b=bundle();let html=render(b);assert.match(html,/Quarterly · annualized/);assert.match(html,/>1.25%<\/a>/);assert.doesNotMatch(html,/>5.00%<\/a>/);
  b.metrics.find(m=>m.id==='roa').annualized=false;html=render(b);assert.doesNotMatch(html,/>1.25%<\/a>/);assert.match(html,/Basis unavailable/);
  b.metrics.find(m=>m.id==='nco').frequency='Annual';assert.doesNotMatch(render(b),/>0.63%<\/a>/);
});
test('wrong units and unsafe numeric evidence URLs are suppressed',()=>{
  const b=bundle();b.metrics[0].unit='Fraction';b.metrics[1].current.url='javascript:bad()';b.metrics[1].observations[2].url='javascript:bad()';const html=render(b);
  assert.doesNotMatch(html,/href="javascript:|>0.93%<\/a>|>0.63%<\/a>/);assert.match(html,/Unavailable/);
});
test('staleness has its own clock with deterministic 36-hour boundary',()=>{
  const b=bundle({last_success:'2026-09-28T00:00:00Z'});assert.doesNotMatch(render(b),/retrieval older than 36 hours/);assert.match(render(b,{now:NOW+1}),/FDIC retrieval older than 36 hours/);
  assert.match(render(bundle({status:'stale',attempted_at:'2026-09-29T05:00:00Z'})),/Last attempt 2026-09-29T05:00:00Z/);assert.match(bankingTeaser({banking:b},{now:NOW+1}),/FDIC retrieval older than 36 hours/);
});
test('failed validation or unavailable source suppresses all retained metrics',()=>{
  for(const b of [bundle({validation:{status:'failed'}}),bundle({status:'unavailable'}),{}]){const html=render(b);assert.match(html,/No validated banking measures/);assert.doesNotMatch(html,/0.93%/);}
});
test('null historical quarters stay explicit and are not substituted as zero',()=>{
  const b=bundle();b.metrics[0].observations=[p('2025-12-31','0.88'),p('2026-03-31',null,{missing_reason:'Not published'}),p('2026-06-30','0.93')];
  const html=render(b);assert.match(html,/2 observed quarters · 1 unavailable quarters/);assert.match(html,/Unavailable · Not published/);assert.match(html,/2026-03-31/);
});
test('population/method remains explicit and all provider strings are escaped',()=>{
  const b=bundle({population:'<script>bad()</script>',edition:'<img>',attribution:'<svg>',terms_url:'javascript:bad()'});b.metrics[0].definition='<b>definition</b>';
  const html=render(b);assert.doesNotMatch(html,/<script>|<img>|<svg>|href="javascript:/);assert.match(html,/&lt;b&gt;definition/);assert.match(html,/not unweighted institution averages/);assert.match(html,/without a double-counting adjustment/);assert.match(html,/90\+ days past due plus nonaccrual/);
});
test('context history uses its own units and invalid requested measure falls back',()=>{
  assert.match(render(bundle(),{metric:'assets'}),/data-metric="assets"/);assert.match(render(bundle(),{metric:'institutions'}),/4,430/);assert.match(render(bundle(),{metric:'bogus'}),/data-metric="noncurrent"/);
});
test('historical reconstruction exceptions preserve published values and disclose exact residuals',()=>{
  const b=bundle({coverage:{note:'Current comparisons reconcile; early historical ratios may differ.'},quality_notes:[{date:'1984-03-31',metric_id:'noncurrent',published:'4.10',calculated:'4.13',residual:'-0.03',note:'Published ratio retained.'}]});
  const html=render(b);assert.match(html,/Current comparisons reconcile/);assert.match(html,/do not establish uniform historical reconciliation/);assert.match(html,/1984-03-31/);assert.match(html,/-0.03 percentage points/);assert.match(html,/4.10 Percent/);
});
test('Funding separates the banking panel from the rate section and keeps a compact default teaser',()=>{
  const d={banking:bundle(),series:[],sources:[]};
  const banking=fundingPage(d,{view:'banking',metric:'deposits',now:NOW});assert.match(banking,/id="banking-panel" data-metric="deposits"/);assert.doesNotMatch(banking,/id="funding-comparison"|id="funding-stress-chart"/);
  const funding=fundingPage(d,{now:NOW});assert.match(funding,/class="section banking-teaser"/);assert.match(funding,/id="funding-comparison"/);assert.doesNotMatch(funding,/id="banking-panel"|id="banking-history-chart"/);
});
test('assets exposes balance-sheet identity exceptions in USD millions, not ratio units',()=>{
  const note={date:'1984-03-31',metric_id:'balance_sheet',published:'3373920',calculated:'3373658',residual:'262',unit:'USD millions',note:'Published assets differ from liabilities plus inclusive equity beyond rounding. Source values retained without repair.'};
  const b=bundle({quality_notes:[note]});b.context.find(m=>m.id==='net_income').label='Quarterly net income attributable to banks';
  const html=render(b,{metric:'assets'});assert.match(html,/Liabilities \+ inclusive equity/);assert.match(html,/3373920 USD millions/);assert.match(html,/262 USD millions/);assert.match(html,/Published values are retained/);assert.doesNotMatch(html,/262 percentage points|quarterly bank-attributable<\/span>/);
  assert.match(html,/Quarterly bank-attributable net income/);
});
test('net income exposes inclusive-income accounting exceptions separately from the headline measure',()=>{
  const note={date:'1984-03-31',metric_id:'income_bridge',published:'1200',calculated:'1198',residual:'2',unit:'USD millions',note:'Inclusive net income differs from bank income plus noncontrolling interests. Source values retained.'};
  const html=render(bundle({quality_notes:[note]}),{metric:'net_income'});
  assert.match(html,/Historical reconciliation exceptions · 1/);assert.match(html,/Published inclusive income/);assert.match(html,/Bank income \+ noncontrolling interests/);assert.match(html,/1200 USD millions/);assert.match(html,/2 USD millions/);assert.doesNotMatch(html,/2 percentage points/);
  assert.match(html,/Quarterly bank-attributable net income/);
});
