import test from 'node:test';
import assert from 'node:assert/strict';
import {inflationState,inflationResults,inflationPage,inflationTeaser} from '../site/inflation.mjs';

const snapshot = (day,cpi,corePce='0.28') => ({captured_at:`${day}T18:00:00Z`,rows:[
  {basis:'mom',target:'2026-09',updated_on:day,values:{cpi,core_cpi:'0.20',pce:'0.44',core_pce:corePce}},
  {basis:'mom',target:'2026-08',updated_on:day,values:{cpi:null,core_cpi:null,pce:'0.34',core_pce:'0.27'}},
  {basis:'yoy',target:'2026-09',updated_on:day,values:{cpi:'3.57',core_cpi:'2.39',pce:'3.97',core_pce:'3.49'}},
  {basis:'quarterly_saar',target:'2026Q3',updated_on:day,values:{cpi:'1.53',core_cpi:'2.16',pce:'2.55',core_pce:'3.00'}}
]});
const first=snapshot('2026-09-28','0.40');
const last=snapshot('2026-09-29','0.50');
const bundle={status:'ok',captured_at:last.captured_at,rows:last.rows,history:[first,last]};

test('monthly comparison is same measure and same target',()=>{
  const state=inflationState(bundle);
  assert.equal(state.target,'2026-09');
  assert.equal(state.current,'0.50');
  assert.equal(state.previous.value,0.40);
  assert.match(inflationResults(bundle),/Up 0\.10 percentage point/);
  assert.match(inflationResults(bundle),/Monthly change · nonannualized/);
});

test('each metric retains its own earliest pending monthly target',()=>{
  assert.equal(inflationState(bundle,{metric:'cpi'}).target,'2026-09');
  assert.equal(inflationState(bundle,{metric:'core_pce'}).target,'2026-08');
  const teaser=inflationTeaser(bundle);
  assert.match(teaser,/CPI · September 2026/);
  assert.match(teaser,/Core PCE · August 2026/);
  assert.match(teaser,/#inflation-watch\?metric=core_pce&amp;|#inflation-watch\?metric=core_pce&basis/);
});

test('blank cell is released-state blank, never zero or agency actual',()=>{
  const result=inflationResults(bundle,{metric:'cpi',target:'2026-08'});
  assert.match(result,/leaves this forecast cell blank/);
  assert.match(result,/not zero/);
  assert.doesNotMatch(result,/0\.00%/);
});

test('basis controls and source links stay distinct',()=>{
  const yearly=inflationResults(bundle,{basis:'yoy',target:'2026-09'});
  assert.match(yearly,/Year-over-year change/);
  assert.match(yearly,/3\.57/);
  const quarter=inflationResults(bundle,{basis:'quarterly_saar',target:'2026Q3'});
  assert.match(quarter,/Quarterly change · annualized/);
  assert.match(quarter,/1\.53/);
  assert.match(inflationPage(bundle),/clevelandfed\.org\/indicators-and-data\/inflation-nowcasting/);
});

test('stale and first-capture states do not manufacture a change',()=>{
  const single={...bundle,history:[last],status:'stale'};
  const result=inflationResults(single);
  assert.match(result,/First retained Public Record capture/);
  assert.match(result,/Retained from a stale capture/);
});

test('two captures on the same model-update day are not a daily comparison',()=>{
  const sameDay={...bundle,history:[snapshot('2026-09-29','0.50'),last]};
  assert.match(inflationResults(sameDay,{basis:'quarterly_saar',metric:'core_pce'}),
    /No earlier model-update day has been captured/);
});

test('publisher change language uses displayed precision, never signed zero',()=>{
  const current={...bundle,publisher_history:{url:'https://example.test/chart',paths:[
    {target:'2026-09',edition_date:'2026-09-29',series:{cpi:[['2026-09-22','0.434980660787975'],['2026-09-23','0.499733447951985']]}},
    {target:'2026-08',edition_date:'2026-09-29',series:{core_pce:[['2026-09-10','0.274534658779718'],['2026-09-11','0.274409309156788']]}}
  ]}};
  assert.match(inflationResults(current),/0\.43% → 0\.50% \(\+0\.07 percentage points\)/);
  const core=inflationResults(current,{metric:'core_pce'});
  assert.match(core,/Unchanged at the table&#39;s 0\.01-point precision/);
  assert.doesNotMatch(core,/−0\.000|-0\.000/);
  assert.doesNotMatch(inflationTeaser(current),/−0\.000|-0\.000/);
});
