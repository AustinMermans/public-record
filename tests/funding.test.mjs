import test from 'node:test';
import assert from 'node:assert/strict';
import {alignedSpread, fundingPage, receipt, sourceNotice, sourceLabel, observationCsv} from '../site/funding.mjs';

const sofr={id:'NYFED-SOFR',source_id:'nyfed-sofr',publisher:'New York Fed',name:'SOFR',url:'https://www.newyorkfed.org/markets/reference-rates/sofr',observations:[['2026-09-24',3.91],['2026-09-25',3.90]],details:[],captured_at:'2026-09-28T20:00:00Z',attribution:'Source "notice"',terms_url:'https://www.newyorkfed.org/privacy/termsofuse'};
const effr={...sofr,id:'NYFED-EFFR',source_id:'nyfed-effr',observations:[['2026-09-23',3.87],['2026-09-25',3.88]]};
test('spread uses common dates and basis points, never mismatched latest rows',()=>{
  const p=alignedSpread(sofr,effr);assert.equal(p.length,1);assert.equal(p[0][0],'2026-09-25');assert.ok(Math.abs(p[0][1]-2)<1e-10);
  assert.deepEqual(alignedSpread(sofr,null),[]);
});
test('funding handles unavailable sources without fake values',()=>{
  const html=fundingPage({series:[],sources:[]});assert.match(html,/same-date comparison is unavailable/);assert.doesNotMatch(html,/NaN|undefined/);
});
test('receipts distinguish old retrieval from publisher observation date',()=>{
  const data={sources:[{id:'nyfed-sofr',status:'ok'}]};
  assert.match(receipt(data,sofr,new Date('2026-10-01')),/retrieval older than 36 hours/);
  assert.doesNotMatch(receipt(data,sofr,new Date('2026-09-28T22:00:00Z')),/older than/);
  data.sources[0].status='stale';assert.match(receipt(data,sofr,new Date('2026-09-28T22:00:00Z')),/stale/);
});
test('direct sources never masquerade as FRED and exports retain rights notices',()=>{
  assert.equal(sourceLabel(sofr),'New York Fed');
  assert.equal(sourceLabel({...sofr,source_id:'fred-SOFR'}),'New York Fed / FRED');
  assert.match(sourceNotice(sofr),/Source &quot;notice&quot;/);
  const csv=observationCsv(sofr,sofr.observations,'Percent');
  assert.match(csv,/attribution,terms_url/);assert.match(csv,/Source ""notice""/);
});
test('floating point residue does not become a zero-size spread change',()=>{
  const a={...sofr,observations:[['2026-09-24',4.35],['2026-09-25',3.90]]};
  const b={...effr,observations:[['2026-09-24',4.33],['2026-09-25',3.88]]};
  assert.match(fundingPage({series:[a,b],sources:[]}),/spread was unchanged/);
});
test('source-rate export links do not claim to export the derived spread',()=>{
  const html=fundingPage({series:[sofr,effr],sources:[]});
  assert.match(html,/SOFR history & export/);assert.match(html,/EFFR history & export/);
});
