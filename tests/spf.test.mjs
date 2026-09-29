import test from 'node:test';
import assert from 'node:assert/strict';
import {spfPanel,spfResults,spfState,spfTeaser} from '../site/spf.mjs';
import {detailTarget} from '../site/metric-links.mjs';

const point=(survey,released,target,value,cell)=>({survey,released,target,value,cell});
const spf={status:'ok',captured_at:'2026-09-29T17:00:00Z',sources:{medianGrowth:{url:'https://www.philadelphiafed.org/growth.xlsx'},medianLevel:{url:'https://www.philadelphiafed.org/level.xlsx'},release_dates:{url:'https://www.philadelphiafed.org/dates.txt'}},series:{
  RGDP:{unit:'percent annualized q/q',points:[point('2026Q2','2026-05-15','2026Q4',1.578,'RGDP!E232'),point('2026Q3','2026-08-14','2026Q3',2.4624,'RGDP!C233'),point('2026Q3','2026-08-14','2026Q4',2.2707,'RGDP!D233'),point('2026Q3','2026-08-14','2027Q1',2.1229,'RGDP!E233'),point('2026Q3','2026-08-14','2027Q2',2.1163,'RGDP!F233'),point('2026Q3','2026-08-14','2027Q3',2.2432,'RGDP!G233')]},
  UNEMP:{unit:'percent quarterly average',points:[point('2026Q2','2026-05-15','2026Q4',4.5,'UNEMP!E232'),point('2026Q3','2026-08-14','2026Q4',4.3,'UNEMP!D233')]},
  CPI:{unit:'percent annualized q/q',points:[point('2026Q3','2026-08-14','2026Q4',2.5227,'CPI!D233')]},
  CORECPI:{unit:'percent annualized q/q',points:[point('2026Q3','2026-08-14','2026Q4',2.7858,'CORECPI!D233')]},
  PCE:{unit:'percent annualized q/q',points:[point('2026Q3','2026-08-14','2026Q4',2.55,'PCE!D233')]},
  COREPCE:{unit:'percent annualized q/q',points:[point('2026Q3','2026-08-14','2026Q4',2.6158,'COREPCE!D233')]}
}};

test('SPF state defaults to next quarter; exact calendar target joins prior survey across shifting horizon columns',()=>{
  const state=spfState(spf);assert.equal(state.target,'2026Q4');assert.equal(state.metric,'RGDP');
  assert.equal(spfState(spf,{metric:'COREPCE',target:'2026Q4'}).target,'2026Q4');
  assert.deepEqual(state.points.map(p=>p.cell),['RGDP!E232','RGDP!D233']);
  const html=spfResults(spf);assert.match(html,/\+0\.7 percentage points since 2026 Q2/);
  assert.match(html,/Real GDP growth · 2026 Q4/);
  assert.match(html,/2\.27%/);
  assert.match(html,/RGDP!D233/);
  assert.doesNotMatch(html,/RGDP!C233/);
});
test('first target does not invent a zero revision; all five latest survey targets are shown',()=>{
  const html=spfResults(spf,{target:'2027Q3'});
  assert.match(html,/First forecast for this target/);
  assert.match(html,/Latest five-quarter path/);
  assert.match(html,/2026 Q3/);assert.match(html,/2027 Q3/);
  assert.equal((html.match(/class="numeric">2\./g)||[]).length,5);
});
test('SPF source, publication and capture clocks remain separate; stale state is visible',()=>{
  const html=spfPanel({...spf,status:'stale'},{metric:'UNEMP',target:'2026Q4'});
  assert.match(html,/2026-08-14/);assert.match(html,/2026-09-29T17:00:00Z/);
  assert.match(html,/Stale capture/);assert.match(html,/Median forecast workbook/);
  assert.match(html,/Quarterly average rate/);
  assert.equal(detailTarget('outlook',new URLSearchParams('forecast=spf&metric=UNEMP&target=2026Q4')),'forecast-spf');
});
test('Outlook teaser links to exact SPF measure and target; absent capture stays explicit',()=>{
  const teaser=spfTeaser(spf);assert.match(teaser,/#outlook\?forecast=spf&amp;metric=RGDP&amp;target=2026Q4/);
  assert.match(teaser,/Unemployment/);assert.match(teaser,/\+0\.7 pp vs 2026 Q2/);assert.match(teaser,/-0\.2 pp vs 2026 Q2/);assert.equal(spfTeaser(null),'');
  assert.match(spfPanel(null),/collection has not run/);
});
test('small nonzero forecast changes are not displayed as signed zero',()=>{
  const copy=structuredClone(spf);
  copy.series.CPI.points.unshift(point('2026Q2','2026-05-15','2026Q4',2.50,'CPI!E232'));
  copy.series.COREPCE.points.unshift(point('2026Q2','2026-05-15','2026Q4',2.63,'COREPCE!E232'));
  assert.match(spfResults(copy,{metric:'CPI',target:'2026Q4'}),/Up less than 0\.1 percentage point/);
  assert.match(spfResults(copy,{metric:'COREPCE',target:'2026Q4'}),/Down less than 0\.1 percentage point/);
  assert.doesNotMatch(spfTeaser(copy),/[+-]0\.0 pp/);
});
test('an older selected target keeps its actual survey attribution and latest-cell qualifier',()=>{
  const copy=structuredClone(spf);
  copy.series.RGDP.points.unshift(point('2026Q1','2026-02-13','2026Q2',2.1,'RGDP!D231'));
  const html=spfResults(copy,{metric:'RGDP',target:'2026Q2'});
  assert.match(html,/2026 Q1 survey, released 2026-02-13/);
  assert.doesNotMatch(html,/2026 Q3 survey, released 2026-02-13/);
  assert.match(html,/Latest forecast cell RGDP!D231/);
  assert.match(html,/Values shown to two decimals/);
});
