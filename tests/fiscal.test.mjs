import test from 'node:test';
import assert from 'node:assert/strict';
import {fiscalPage,fiscalTeaser} from '../site/fiscal.mjs';
const t3='https://api.fiscaldata.treasury.gov/mts_table_3',t9='https://api.fiscaldata.treasury.gov/mts_table_9';
function bundle(overrides={}){
  return {status:'ok',captured_at:new Date().toISOString(),edition:'2026-08-31',url:t3,validation:{status:'reconciled'},periods:{current_month:{start:'2026-08-01',end:'2026-08-31'},current_fytd:{start:'2025-10-01',end:'2026-08-31'},prior_fytd:{start:'2024-10-01',end:'2025-08-31'}},metrics:[{id:'receipts',unit:'USD',current_fytd:'5000000000000.10',prior_fytd:'4900000000000.05',url:t3},{id:'outlays',unit:'USD',current_fytd:'6500000000000',prior_fytd:'6100000000000',url:t3},{id:'net_interest',unit:'USD',current_fytd:'900000000000',prior_fytd:'800000000000',url:t9},{id:'balance',unit:'USD',current_fytd:'-1499999999999.90',prior_fytd:'-1199999999999.95',url:t3}],bridge:{status:'reconciled',unit:'USD',current_deficit:'1499999999999.90',prior_deficit:'1199999999999.95',deficit_change:'299999999999.95',net_interest_change:'100000000000',other_outlays_change:'300000000000',receipts_change:'100000000000.05',receipts_contribution:'-100000000000.05',component_sum:'299999999999.95',residual:'0.00',sources:[t3,t9]},monthly_status:'ok',monthly_coverage:{start:'2026-07-31',end:'2026-08-31',edition:'2026-08-31'},monthly:[{date:'2026-07-31',fiscal_year:'2026',receipts:'100000000000',outlays:'200000000000',balance:'-100000000000',url:t3},{date:'2026-08-31',fiscal_year:'2026',receipts:'250000000000',outlays:'200000000000',balance:'50000000000',url:t3}],...overrides};
}
test('FYTD displays four linked actual measures with complete matched spans and decimal delta',()=>{
  const html=fiscalPage({fiscal:bundle()});
  assert.equal((html.match(/class="kpi"/g)||[]).length,4);assert.match(html,/2025-10-01 → 2026-08-31/);assert.match(html,/2024-10-01 → 2025-08-31/);
  assert.match(html,/1,500.00 USD bn deficit/);assert.match(html,/title="100000000000.05 USD"/);assert.match(html,/href="https:\/\/api.fiscaldata.treasury.gov\/mts_table_9"/);
  assert.match(html,/tabindex="0" role="region" aria-label="Fiscal year-to-date comparison"/);
  assert.match(html,/includes accrued interest on the public debt/);assert.match(html,/Treasury source data may be reused commercially or noncommercially/);assert.match(html,/https:\/\/fiscaldata.treasury.gov\/about-us\//);
});
test('surplus and real zero are not deficits or missing values',()=>{
  const f=bundle();f.metrics.find(x=>x.id==='balance').current_fytd='25000000000';
  assert.match(fiscalTeaser({fiscal:f}),/25.00 USD bn surplus/);assert.doesNotMatch(fiscalTeaser({fiscal:f}),/deficit/);
  f.metrics.find(x=>x.id==='balance').current_fytd='0.00';assert.match(fiscalTeaser({fiscal:f}),/0.00 USD bn balanced/);
});
test('missing amounts and incompatible units do not become zeros or financial comparisons',()=>{
  const f=bundle();f.metrics.find(x=>x.id==='receipts').current_fytd='null';f.metrics.find(x=>x.id==='net_interest').unit='Millions of USD';
  const html=fiscalPage({fiscal:f});assert.equal((html.match(/class="kpi"/g)||[]).length,2);assert.doesNotMatch(html,/NaN|undefined/);
  f.metrics.find(x=>x.id==='balance').current_fytd=null;assert.match(fiscalTeaser({fiscal:f}),/Validated fiscal data unavailable/);
});
test('mismatched fiscal cutoff suppresses prior comparison and bridge',()=>{
  const f=bundle();f.periods.prior_fytd.end='2025-09-30';const html=fiscalPage({fiscal:f});
  assert.match(html,/Matched prior fiscal period unavailable/);assert.match(html,/Not comparable/);assert.match(html,/reconciled accounting bridge is unavailable/);assert.doesNotMatch(html,/aria-label="Deficit accounting bridge"/);
});
test('the accounting bridge displays signed contributions and explicitly denies causality',()=>{
  const html=fiscalPage({fiscal:bundle()});assert.match(html,/\+100.00 USD bn/);assert.match(html,/-100.00 USD bn/);assert.match(html,/Receipts \(sign reversed\)/);
  assert.match(html,/An accounting decomposition, not policy causality/);assert.match(html,/Deficit is not the change in debt/);assert.match(html,/aria-hidden="true" focusable="false"/);
});
test('failed validation or unavailable collection fails closed even if amounts remain',()=>{
  for(const f of [bundle({status:'unavailable'}),bundle({validation:{status:'failed'}}),{}]){const html=fiscalPage({fiscal:f});assert.match(html,/No validated fiscal amounts/);assert.doesNotMatch(html,/1,500.00/);}
});
test('stale and old-successful captures are flagged at the headline and point of use',()=>{
  for(const f of [bundle({status:'stale'}),bundle({captured_at:'2020-01-01T00:00:00Z'})]){const html=fiscalPage({fiscal:f});assert.ok((html.match(/class="(?:meta )?warning"/g)||[]).length>=5);assert.match(fiscalTeaser({fiscal:f}),/class="warning"/);}
  assert.match(fiscalPage({fiscal:bundle({captured_at:'2020-01-01T00:00:00Z'})}),/Retrieval older than 36 hours/);
  const f=bundle({captured_at:'2026-09-28T00:00:00Z'});
  assert.doesNotMatch(fiscalPage({fiscal:f},{now:Date.parse('2026-09-29T12:00:00Z')}),/Retrieval older than 36 hours/);
  assert.match(fiscalPage({fiscal:f},{now:Date.parse('2026-09-29T12:00:01Z')}),/Retrieval older than 36 hours/);
});
test('monthly view preserves signed balance, edition, source links and shareable controls',()=>{
  const html=fiscalPage({fiscal:bundle()},{view:'monthly',metric:'balance'});
  assert.match(html,/data-view="monthly" data-metric="balance"/);assert.match(html,/-100.00 USD bn/);assert.match(html,/50.00 USD bn/);assert.match(html,/Positive balance = surplus; negative = deficit/);
  assert.match(html,/#fiscal\?view=fytd&metric=balance/);assert.match(html,/id="fiscal-monthly-chart"/);assert.match(html,/Edition 2026-08-31/);
  assert.doesNotMatch(fiscalPage({fiscal:bundle({monthly_status:'unavailable'})},{view:'monthly'}),/id="fiscal-monthly-chart"/);
});
test('invalid query options fall back safely and strings/source links are escaped',()=>{
  const f=bundle({edition:'<img onerror=bad()>',url:'javascript:bad()',attribution:'<script>bad()</script>'});f.metrics[0].url='javascript:bad()';
  const html=fiscalPage({fiscal:f},{view:'<script>',metric:'<svg>'});assert.match(html,/data-view="fytd" data-metric="balance"/);assert.doesNotMatch(html,/<img|<script>|href="javascript:/);assert.match(html,/&lt;img/);assert.match(html,/Source link unavailable/);
});
test('teaser links the displayed FYTD measure to its exact table instead of monthly history',()=>{
  const html=fiscalTeaser({fiscal:bundle()});assert.match(html,/#fiscal\?view=fytd&metric=balance/);assert.doesNotMatch(html,/view=monthly/);assert.match(html,/FYTD 2025-10-01 → 2026-08-31/);
});
test('plain-language comparison handles deficit directions, surplus transitions and no change',()=>{
  const f=bundle();assert.match(fiscalPage({fiscal:f}),/FYTD deficit was 300.00 USD bn larger/);
  f.bridge.deficit_change='-5000000000';assert.match(fiscalPage({fiscal:f}),/FYTD deficit was 5.00 USD bn smaller/);
  f.bridge.current_deficit='-1000000000';assert.match(fiscalPage({fiscal:f}),/FYTD budget balance was 5.00 USD bn stronger/);
  f.bridge.deficit_change='5000000000';assert.match(fiscalPage({fiscal:f}),/FYTD budget balance was 5.00 USD bn weaker/);
  f.bridge.deficit_change='0.00';assert.match(fiscalPage({fiscal:f}),/FYTD budget balance was unchanged/);
});
