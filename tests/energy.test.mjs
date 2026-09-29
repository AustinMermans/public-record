import test from 'node:test';
import assert from 'node:assert/strict';
import {energyPage, sameSeason} from '../site/energy.mjs';
import {buildSearchIndex, deskPage} from '../site/publication.mjs';

const table='https://ir.eia.gov/wpsr/table4.csv';
const metrics=[
  {id:'crude',label:'Commercial crude, excluding SPR',current:'426.398',weekly_change:'2.969',year_change_pct:'2.8'},
  {id:'gasoline',label:'Motor gasoline',current:'206.046',weekly_change:'-1.686',year_change_pct:'-4.9'},
  {id:'distillate',label:'Distillate fuel oil',current:'107.431',weekly_change:'-0.428',year_change_pct:'-12.7'}
].map(m=>({...m,unit:'million barrels',current_week:'2026-09-18',prior_week:'2026-09-11',year_ago_week:'2025-09-19',url:table}));
const data=()=>({sources:[],records:[],events:[],series:[],corporate:{companies:[]},
  energy:{status:'ok',week_end:'2026-09-18',published_at:'2026-09-23',captured_at:'2026-09-29T20:00:00Z',
    table_url:table,json_url:'https://ir.eia.gov/wpsr/psw00.json',schedule_url:'https://www.eia.gov/petroleum/supply/weekly/schedule.php',
    history_urls:{gasoline:'https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WGTSTUS1&f=W',distillate:'https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WDISTUS1&f=W'},
    metrics,crude_history:[['2026-09-11',423429],['2026-09-18',426398]],
    product_history:{gasoline:[['2026-09-11',207732],['2026-09-18',206046]],distillate:[['2026-09-11',107859],['2026-09-18',107431]]}}});

test('energy read separates three stocks, dates and source links without price inference',()=>{
  const html=energyPage(data());
  assert.match(html,/Commercial crude rose 2\.969 million barrels/);
  assert.match(html,/gasoline fell 1\.686 and distillate fell 0\.428/);
  assert.match(html,/12\.7% below the comparable week/);
  assert.match(html,/Week ended Sep 18, 2026 · Published Sep 23, 2026/);
  assert.match(html,/#energy\?metric=gasoline/);
  assert.match(html,/https:\/\/ir\.eia\.gov\/wpsr\/table4\.csv/);
  assert.match(html,/current EIA series edition/);
  assert.match(html,/not demand or price forecasts/);
  assert.doesNotMatch(html,/shortage|bullish|bearish|consensus surprise/i);
});

test('shareable selected product opens its own figures and source-bound history',()=>{
  const html=energyPage(data(),'gasoline');
  assert.match(html,/id="energy-gasoline"/);
  assert.match(html,/206\.046 million barrels on Sep 18/);
  assert.match(html,/id="energy-chart"/);
  assert.match(html,/#energy\?metric=gasoline&range=all/);
  assert.match(html,/WGTSTUS1/);
  assert.doesNotMatch(html,/Crude history JSON/);
  assert.match(energyPage(data(),'gasoline','10'),/#energy\?metric=distillate&range=10/);
  const missing=data();delete missing.energy.product_history.distillate;
  missing.energy.history_errors={distillate:'Source unavailable'};
  assert.match(energyPage(missing,'distillate'),/Historical chart unavailable.*Source unavailable/);
});

test('five separate nearest-calendar-week levels form a descriptive seasonal range',()=>{
  const points=[['2021-09-17',120000],['2022-09-16',118000],['2023-09-15',126000],
    ['2024-09-20',121000],['2025-09-19',123000],['2026-09-18',107431]];
  assert.deepEqual(sameSeason(points,'2026-09-18',107.431),
    {min:118,max:126,first:2021,last:2025,position:'below',
      observations:points.slice(0,5).map(([day,value])=>[day,value/1000])});
  assert.equal(sameSeason(points.slice(1),'2026-09-18',107.431),null);
  const newYear=[['2021-01-01',100000],['2021-12-31',101000],['2022-12-30',102000],
    ['2024-01-05',103000],['2025-01-03',104000],['2026-01-02',99000]];
  assert.equal(sameSeason(newYear,'2026-01-02',99).position,'below');
  const leap=[['2031-02-28',101000],['2032-02-27',102000],['2033-02-25',103000],
    ['2033-03-04',999000],['2034-03-03',104000],['2035-03-02',105000],['2036-02-29',99000]];
  const leapReference=sameSeason(leap,'2036-02-29',99);
  assert.equal(leapReference.max,105);
  assert.ok(leapReference.observations.some(([day])=>day==='2033-02-25'));
  assert.ok(!leapReference.observations.some(([day])=>day==='2033-03-04'));
});

test('stale capture is labeled and index and Economy desk lead to energy',()=>{
  const fixture=data();fixture.energy.status='stale';fixture.energy.attempted_at='2026-09-30T20:00:00Z';
  assert.match(energyPage(fixture),/Stale; last attempted/);
  const hits=buildSearchIndex(fixture).filter(row=>row.kind==='indicator'&&row.title.includes('Petroleum:'));
  assert.equal(hits.length,3);
  assert.equal(hits[2].url,'#energy?metric=distillate');
  const desk=deskPage(fixture,'economy-home',{kpi:()=>'',brief:()=>'',agenda:()=>'',nextEvents:()=>[]});
  assert.match(desk,/#energy/);
});
