import test from 'node:test';
import assert from 'node:assert/strict';
import {financialProfile} from '../site/financials.mjs';

const point=(value,overrides={})=>({value,unit:'USD',concept:'us-gaap:Revenues',start:'2026-04-01',end:'2026-06-30',accession:'0001-26-000001',filed:'2026-07-20',form:'10-Q',url:'https://www.sec.gov/Archives/current.htm',evidence_label:'fact_source_reported',...overrides});
const row=(current=point(200e6),prior=point(100e6,{start:'2025-04-01',end:'2025-06-30',url:'https://www.sec.gov/Archives/prior.htm'}),overrides={})=>({id:'revenue',label:'Revenue',concept:'us-gaap:Revenues',unit:'USD',current,prior,comparison_status:'comparable',...overrides});
const section=(rows=[row()],overrides={})=>({id:'operating',title:'Reported quarter operations',period_type:'quarter',start:'2026-04-01',end:'2026-06-30',period_label:'2026-04-01 to 2026-06-30',rows,...overrides});
const company=(overrides={})=>({cik:'0001',name:'Example',status:'ok',profile_type:'operating_company',captured_at:'2026-09-28T00:00:00Z',anchor:{form:'10-Q',filed:'2026-07-20',report_period:'2026-06-30',url:'https://www.sec.gov/Archives/current.htm'},sections:[section()],annual_history:[],qa_flags:[],...overrides});
const render=c=>financialProfile({financials:{companies:[c]}},'0001');

test('reported values retain exact source links, periods, units and positive-prior changes',()=>{
  const html=render(company());
  assert.match(html,/200\.00 USD mn/);assert.match(html,/100\.00 USD mn/);assert.match(html,/\+100\.00%/);
  assert.match(html,/href="https:\/\/www.sec.gov\/Archives\/current.htm"/);assert.match(html,/href="https:\/\/www.sec.gov\/Archives\/prior.htm"/);
  assert.match(html,/2026-04-01 → 2026-06-30/);assert.match(html,/2025-04-01 → 2025-06-30/);assert.match(html,/scope="row"/);
  assert.match(html,/data-label="Current"/);assert.match(html,/data-label="Prior-year period"/);assert.match(html,/data-label="Change"/);
});
test('missing values remain missing while an actual zero remains visible',()=>{
  const html=render(company({sections:[section([row(point(0),null),row(null,null,{id:'missing',label:'Missing metric'})])]}));
  assert.match(html,/0\.00 USD/);assert.match(html,/Not available/);assert.match(html,/No comparable prior/);assert.doesNotMatch(html,/NaN|undefined/);
  assert.match(financialProfile({},'0001'),/not available for this registrant/);
});
test('nonpositive priors use absolute changes and margin differences use percentage points',()=>{
  for(const prior of [0,-100]) {
    const html=render(company({sections:[section([row(point(100),point(prior))])]}));
    assert.match(html,/Absolute change · prior ≤ 0/);assert.doesNotMatch(html,/\d\.\d+%/);
  }
  const html=render(company({sections:[section([row(point(20,{unit:'Percent',concept:'operating_margin'}),point(15,{unit:'Percent',concept:'operating_margin'}),{id:'operating_margin',unit:'Percent',label:'Operating margin'})])]}));
  assert.match(html,/\+5\.00 pp/);assert.doesNotMatch(html,/33\.33%/);
});
test('comparisons require approved matching concepts and units',()=>{
  for(const overrides of [{unit:'EUR'},{concept:'us-gaap:SalesRevenueNet'}]) {
    const html=render(company({sections:[section([row(point(200),point(100,overrides))])]}));
    assert.match(html,/No comparable prior/);assert.doesNotMatch(html,/\+100\.00%/);
    if(overrides.unit)assert.match(html,/100\.00 EUR/);
  }
  assert.match(render(company({sections:[section([row(point(200),point(100),{comparison_status:'missing_required_source'})])]})),/No comparable prior/);
});
test('derived values expose input sources and are never described as directly reported',()=>{
  const a=point(50e6,{concept:'us-gaap:NetCashProvidedByUsedInOperatingActivities'}),b=point(20e6,{concept:'us-gaap:PaymentsToAcquirePropertyPlantAndEquipment'});
  const p=point(30e6,{concept:'cfo_less_cash_ppe',evidence_label:'derived_calculation',formula:'Operating cash flow − cash PPE payments',inputs:[a,b]});
  const html=render(company({sections:[section([row(p,null,{id:'cfo_less_cash_ppe',concept:'Public Record calculation',evidence_label:'derived_calculation'})],{id:'cash_flow',period_type:'ytd',title:'Reported year-to-date cash generation'})]}));
  assert.match(html,/Year to date/);assert.match(html,/Public Record calculation/);assert.match(html,/50\.00 USD mn/);assert.match(html,/20\.00 USD mn/);assert.match(html,/Operating cash flow − cash PPE payments/);
  assert.doesNotMatch(html,/free cash flow|distributable cash/i);
});
test('bank profiles do not receive industrial margin or cash-flow templates',()=>{
  const html=render(company({profile_type:'bank',sections:[section([row(),row(null,null,{id:'operating_margin',label:'Operating margin'})]),section([row(null,null,{id:'cfo_less_cash_ppe',label:'Cash template'})],{id:'cash_flow'})]}));
  assert.doesNotMatch(html,/Operating margin|Cash template/);assert.match(html,/Revenue/);
});
test('annual history is collapsed, filing-bound and limited to five periods',()=>{
  const annuals=Array.from({length:6},(_,i)=>section([row()],{id:'annual',period_type:'annual',period_label:`Annual ${2025-i}`,anchor:{form:'10-K',filed:`${2026-i}-02-01`,url:`https://www.sec.gov/Archives/annual-${i}.htm`}}));
  const html=render(company({annual_history:annuals}));
  assert.match(html,/<details class="financial-history section"><summary>Annual history · 5 filed periods/);assert.match(html,/annual-4.htm/);assert.doesNotMatch(html,/annual-5.htm/);
  assert.match(html,/<div class="table-wrap" tabindex="0" role="region" aria-label="Annual financial history">/);
});
test('stale and unavailable status, specialist boundaries and source exceptions remain explicit',()=>{
  const html=render(company({status:'stale',last_success:'2026-09-25T12:00:00Z',boundary:'REIT: earnings are not FFO.',qa_flags:[{area:'revenue',severity:'high',issue:'Conflicting current facts.',period:'2026-06-30'}]}));
  assert.match(html,/Stale · last successful facts/);assert.match(html,/2026-09-25T12:00:00Z/);assert.match(html,/earnings are not FFO/);assert.match(html,/Conflicting current facts/);
  assert.match(render(company({status:'unavailable',sections:[]})),/Collection unavailable/);
  const empty=render(company({status:'ok',sections:[section([row(null,null)])]}));
  assert.match(empty,/Current facts unavailable/);assert.match(empty,/No mapped current-period values/);
});
test('all source strings are escaped and unsafe links never become numeric evidence',()=>{
  const html=render(company({boundary:'<script>bad</script>',sections:[section([row(point(123,{url:'javascript:alert(1)'}),null,{label:'<img src=x onerror=bad>',issue:'<b>unsafe</b>'})])]}));
  assert.doesNotMatch(html,/<script>|<img|href="javascript:/);assert.match(html,/&lt;script&gt;/);assert.match(html,/Source link unavailable/);assert.doesNotMatch(html,/123\.00 USD/);
});
