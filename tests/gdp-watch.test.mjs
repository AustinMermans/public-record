import test from 'node:test';
import assert from 'node:assert/strict';
import {gdpWatchState,gdpWatchPanel,gdpWatchResults,gdpWatchTeaser,gdpWatchAnnouncement} from '../site/gdp-watch.mjs';
import {buildSearchIndex,deskPage} from '../site/publication.mjs';

const asOf='2026-09-29';
const source='https://www.atlantafed.org/research-and-data/data/gdpnow';
const workbook='https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/survey-of-professional-forecasters/historical-data/medianGrowth.xlsx';
const release='https://www.bea.gov/news/2026/gdp-advance-estimate-2nd-quarter-2026';
const fixture=()=>({
  captured_at:'2026-09-29T20:39:04Z',sources:[],records:[],series:[],events:[],corporate:{companies:[]},
  research:{forecasts:[{id:'gdpnow',title:'Atlanta Fed GDPNow',target:'2026 Q3',value:5,published_at:'2026-09-25',captured_at:'2026-09-29T20:39:07Z',unit:'Percent · quarterly annualized',status:'ok',url:source,basis:'Model estimate, not an official forecast.'}]},
  spf:{status:'ok',captured_at:'2026-09-29T20:39:08Z',sources:{medianGrowth:{url:workbook}},series:{RGDP:{unit:'percent, quarter-over-quarter annualized growth',points:[
    {target:'2026Q2',survey:'2026Q2',released:'2026-05-15',value:2.1028,cell:'RGDP!C232'},
    {target:'2026Q3',survey:'2026Q2',released:'2026-05-15',value:2.2233,cell:'RGDP!D232'},
    {target:'2026Q3',survey:'2026Q3',released:'2026-08-14',value:2.4624,cell:'RGDP!C233'},
    {target:'2026Q4',survey:'2026Q3',released:'2026-08-14',value:2.2707,cell:'RGDP!D233'}
  ]}}},
  bea_releases:{status:'ok',schedule:{url:'https://www.bea.gov/news/schedule/full'},releases:[
    {quarter:'2026Q2',stage:'advance',published_at:'2026-07-30',captured_at:'2026-09-29T20:39:08Z',value:1.5,display_value:'1.5',unit:'percent',basis:'quarterly seasonally adjusted annual rate',url:release},
    {quarter:'2026Q2',stage:'second',published_at:'2026-08-26',captured_at:'2026-09-29T20:39:08Z',value:1.5,display_value:'1.5',unit:'percent',basis:'quarterly seasonally adjusted annual rate',url:'https://www.bea.gov/news/2026/gdp-second-estimate-and-corporate-profits-2nd-quarter-2026'}
  ],scheduled:[{quarter:'2026Q3',stage:'advance',date:'2026-10-29',title:'GDP (Advance Estimate), 3rd Quarter 2026'}]}
});

test('default watch aligns the same Q3 target and keeps future BEA as pending',()=>{
  const d=fixture(),s=gdpWatchState(d,{asOf});
  assert.equal(s.target,'2026Q3');
  assert.equal(s.model.value,5);
  assert.equal(s.spf.value,2.4624);
  assert.equal(s.bea,null);
  assert.equal(s.scheduled.date,'2026-10-29');
  assert.ok(Math.abs(s.contrast-2.5376)<1e-10);
  const html=gdpWatchResults(d,{asOf});
  assert.match(html,/GDPNow \(2026-09-25\) is about 2\.5 percentage points above the SPF-derived estimate \(2026-08-14\)/);
  assert.match(html,/scheduled 2026-10-29; no published value verified/);
  assert.doesNotMatch(html,/1\.5<small>%<\/small>/);
  assert.doesNotMatch(html,/surprise of|consensus forecast/);
  assert.match(html,/median forecast GDP levels, not a median of individual growth forecasts/);
  assert.match(html,/historical cells come from the workbook edition retrieved now/);
});

test('selecting Q2 does not splice Q3 nowcast with Q2 advance release',()=>{
  const d=fixture(),s=gdpWatchState(d,{target:'2026Q2',asOf});
  assert.equal(s.model,null);
  assert.equal(s.spf.value,2.1028);
  assert.equal(s.bea.value,1.5);
  assert.equal(s.contrast,null);
  const html=gdpWatchResults(d,{target:'2026Q2',asOf});
  assert.match(html,/No retained GDPNow estimate for 2026 Q2/);
  assert.match(html,/BEA advance estimate for 2026 Q2/);
  assert.match(html,/#gdp-releases\?quarter=2026Q2/);
  assert.doesNotMatch(html,/5\.0<small>%<\/small>/);
  assert.doesNotMatch(html,/second estimate for 2026 Q2/);
});

test('stale, aged, misdefined or unavailable inputs withhold the numerical contrast',()=>{
  const d=fixture();d.research.forecasts[0].status='stale';
  assert.equal(gdpWatchState(d,{asOf}).contrast,null);
  assert.match(gdpWatchResults(d,{asOf}),/stale capture/);
  d.research.forecasts[0].status='ok';d.research.forecasts[0].published_at='2026-09-01';
  assert.equal(gdpWatchState(d,{asOf}).contrast,null);
  d.research.forecasts[0].published_at='2026-09-25';d.spf.status='stale';
  assert.equal(gdpWatchState(d,{asOf}).contrast,null);
  d.spf.status='ok';d.spf.series.RGDP.unit='percent, year-over-year';
  assert.equal(gdpWatchState(d,{asOf}).contrast,null);
  d.spf.series.RGDP.unit='percent, quarter-over-quarter annualized growth';d.research.forecasts[0].unit='Percent · annual Q4/Q4';
  assert.equal(gdpWatchState(d,{asOf}).contrast,null);
  d.research.forecasts[0].unit='Percent · quarterly annualized';d.research.forecasts[0].status='unavailable';
  assert.equal(gdpWatchState(d,{asOf}).model,null);
});

test('release day or stale BEA schedule cannot promote the cross-source contrast as current',()=>{
  const d=fixture();
  d.research.forecasts[0].published_at='2026-10-28';
  d.research.forecasts[0].captured_at='2026-10-28T20:00:00Z';
  d.spf.captured_at='2026-10-28T20:00:00Z';
  assert.equal(gdpWatchState(d,{asOf:'2026-10-29'}).contrast,null);
  assert.equal(gdpWatchTeaser(d,{asOf:'2026-10-29'}),'');
  assert.match(gdpWatchResults(d,{asOf:'2026-10-29'}),/Scheduled date passed without a verified release/);
  d.bea_releases.scheduled=[];
  assert.equal(gdpWatchState(d,{asOf:'2026-10-28'}).contrast,null);
  d.bea_releases.scheduled=[{quarter:'2026Q3',stage:'advance',date:'2026-10-29'}];
  d.bea_releases.status='stale';
  assert.equal(gdpWatchState(d,{asOf:'2026-10-28'}).contrast,null);
});

test('same-day or future source claims are not treated as released forecasts',()=>{
  const d=fixture();d.research.forecasts[0].published_at='2026-10-01';
  assert.equal(gdpWatchState(d,{asOf}).model,null);
  d.research.forecasts[0].published_at='2026-09-25';d.spf.series.RGDP.points.find(p=>p.survey==='2026Q3').released='2026-10-01';
  assert.equal(gdpWatchState(d,{asOf}).contrast,null);
});

test('small nonzero contrasts never render as signed or directional zero',()=>{
  const d=fixture();d.research.forecasts[0].value=2.5;
  const html=gdpWatchResults(d,{asOf});
  assert.match(html,/less than 0\.1 percentage point above/);
  assert.doesNotMatch(html,/0\.0 percentage points above/);
  d.spf.series.RGDP.points.find(p=>p.survey==='2026Q3').value=2.5;
  assert.match(gdpWatchResults(d,{asOf}),/at the same numerical rate as/);
});

test('only a source-bound advance release fills the actual slot',()=>{
  const d=fixture();d.bea_releases.releases=d.bea_releases.releases.filter(r=>r.stage==='second');
  assert.equal(gdpWatchState(d,{target:'2026Q2',asOf}).bea,null);
  d.bea_releases.releases[0].stage='advance';d.bea_releases.releases[0].display_value='4.0';
  assert.equal(gdpWatchState(d,{target:'2026Q2',asOf}).bea,null);
  d.bea_releases.status='unavailable';
  assert.equal(gdpWatchState(d,{target:'2026Q2',asOf}).bea,null);
});

test('watch panel, front and search lead to a shareable selected target',()=>{
  const d=fixture();
  assert.match(gdpWatchPanel(d,{target:'2026Q2',asOf}),/<option value="2026Q2" selected>/);
  assert.doesNotMatch(gdpWatchPanel(d,{asOf}),/id="gdp-watch-results" role="status"/);
  assert.match(gdpWatchPanel(d,{asOf}),/id="gdp-watch-announcement" role="status"/);
  assert.equal(gdpWatchAnnouncement(gdpWatchState(d,{target:'2026Q2',asOf})),'2026 Q2 selected. GDPNow unavailable. SPF 2.10 percent. BEA advance 1.5 percent.');
  assert.match(gdpWatchTeaser(d,{asOf}),/#outlook\?forecast=gdp-watch&amp;quarter=2026Q3|#outlook\?forecast=gdp-watch&quarter=2026Q3/);
  const front=deskPage(d,'outlook-home',{},{});
  assert.match(front,/One-quarter GDP watch/);
  const row=buildSearchIndex(d).find(r=>r.title==='GDP target watch · 2026 Q3');
  assert.equal(row.url,'#outlook?forecast=gdp-watch&quarter=2026Q3');
  d.research.forecasts[0].status='stale';
  assert.equal(gdpWatchTeaser(d,{asOf}), '');
});
