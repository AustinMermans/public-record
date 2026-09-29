import test from 'node:test';
import assert from 'node:assert/strict';
import {energyPage} from '../site/energy.mjs';
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
    metrics,crude_history:[['2026-09-11',423429],['2026-09-18',426398]]}});

test('energy read separates three stocks, dates and source links without price inference',()=>{
  const html=energyPage(data());
  assert.match(html,/Commercial crude rose 2\.969 million barrels/);
  assert.match(html,/gasoline fell 1\.686 and distillate fell 0\.428/);
  assert.match(html,/12\.7% below the comparable week/);
  assert.match(html,/Week ended Sep 18, 2026 · Published Sep 23, 2026/);
  assert.match(html,/#energy\?metric=gasoline/);
  assert.match(html,/https:\/\/ir\.eia\.gov\/wpsr\/table4\.csv/);
  assert.match(html,/current EIA rolling edition/);
  assert.match(html,/not demand or price forecasts/);
  assert.doesNotMatch(html,/shortage|bullish|bearish|consensus surprise/i);
});

test('shareable selected product opens its own figures, not the crude chart',()=>{
  const html=energyPage(data(),'gasoline');
  assert.match(html,/id="energy-gasoline"/);
  assert.match(html,/206\.046 million barrels on Sep 18/);
  assert.doesNotMatch(html,/id="energy-chart"/);
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
