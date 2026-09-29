import test from 'node:test';
import assert from 'node:assert/strict';
import {gdpReleasePage,gdpReleaseTeaser,releaseState,revisedGdp} from '../site/gdp-releases.mjs';
import {buildSearchIndex} from '../site/publication.mjs';

const release=(quarter,stage,date,display,extra={})=>({quarter,stage,published_at:date,value:Number(display),display_value:display,unit:'percent',basis:'quarterly seasonally adjusted annual rate',url:'https://www.bea.gov/news/2026/gdp-'+stage+'-estimate-'+quarter.toLowerCase(),captured_at:'2026-09-29T12:00:00Z',sha256:'a'.repeat(64),locator:'Real GDP and Related Measures · Real GDP',...extra});
const data={bea_releases:{status:'ok',releases:[
  release('2026Q1','advance','2026-04-30','2.0'),
  release('2026Q1','second','2026-05-28','1.6'),
  release('2026Q1','third','2026-06-25','2.1'),
  release('2026Q2','advance','2026-07-30','1.5',{gdi_value:null}),
  release('2026Q2','second','2026-08-26','1.5',{revision_note:'BEA reports a downward revision of less than 0.1 percentage point.'})
],scheduled:[{quarter:'2026Q2',stage:'third',date:'2026-09-30',title:'GDP (Third Estimate)'},{quarter:'2026Q3',stage:'advance',date:'2026-10-29',title:'GDP (Advance Estimate)'}]},series:[{id:'GDPC1',source_id:'fred-GDPC1',observations:[['2026-01-01',300],['2026-04-01',301]],url:'https://fred.stlouisfed.org/series/GDPC1',captured_at:'2026-09-29T11:00:00Z'}]};

test('latest target is actual release, and scheduled third remains pending',()=>{
  const state=releaseState(data.bea_releases);
  assert.equal(state.latest,'2026Q2');
  assert.equal(state.grouped.get('2026Q2').size,2);
  const page=gdpReleasePage(data,null,'2026-09-29');
  assert.match(page,/GDP release record/);
  assert.match(page,/1\.5% real GDP growth/);
  assert.match(page,/Same 1\.5% at shown precision/);
  assert.match(page,/downward revision of less than 0\.1 percentage point/);
  assert.match(page,/Scheduled 2026-09-30\. A calendar entry is not a published result/);
  assert.match(page,/Next on BEA’s calendar.*2026-09-30.*2026 Q2 third estimate/);
  assert.match(page,/No verified Real GDI value extracted for this stage/);
  assert.doesNotMatch(page,/unchanged|0\.0 percentage point/i);
});

test('next scheduled GDP release spans quarters without making future values selectable',()=>{
  const page=gdpReleasePage(data,'2026Q2','2026-10-01');
  assert.match(page,/Next on BEA’s calendar.*2026-10-29.*2026 Q3 advance estimate/);
  assert.doesNotMatch(page,/<option value="2026Q3"/);
  assert.match(page,/BEA schedule ↗/);
});

test('same target stage changes use published previous stage only',()=>{
  const page=gdpReleasePage(data,'2026Q1');
  assert.match(page,/fell 0\.4 percentage points from the advance estimate/);
  assert.match(page,/rose 0\.5 percentage points from the second estimate/);
  assert.doesNotMatch(page,/Scheduled 2026-09-30/);
});

test('current revised GDP is separate and calculated only for adjacent quarters',()=>{
  const p=revisedGdp(data,'2026Q2');
  assert.ok(Math.abs(p.value-(100*((301/300)**4-1)))<1e-10);
  assert.match(gdpReleasePage(data,'2026Q2'),/different information set/);
  assert.equal(revisedGdp(data,'2026Q1'),null);
  const broken=structuredClone(data);broken.series[0].observations[0][0]='2025-10-01';
  assert.equal(revisedGdp(broken,'2026Q2'),null);
});

test('unsafe and ill-defined values are not presented as releases',()=>{
  const broken=structuredClone(data);
  broken.bea_releases.releases.push(release('2026Q3','advance','2026-10-29','4.2',{url:'javascript:alert(1)'}));
  broken.bea_releases.releases.push(release('2026Q3','second','2026-11-25','4.2',{basis:'year over year'}));
  assert.equal(releaseState(broken.bea_releases).latest,'2026Q2');
  assert.doesNotMatch(gdpReleasePage(broken),/4\.2/);
  assert.match(gdpReleaseTeaser(data),/#gdp-releases\?quarter=2026Q2/);
});

test('missing preceding stage and stale capture are not presented as a complete initial release',()=>{
  const broken=structuredClone(data);
  broken.bea_releases.status='stale';
  broken.bea_releases.captured_at='2026-09-28T00:00:00Z';
  broken.bea_releases.releases=broken.bea_releases.releases.filter(r=>!(r.quarter==='2026Q2'&&r.stage==='advance'));
  const page=gdpReleasePage(broken,'2026Q2');
  assert.match(page,/retained dated releases may be stale/);
  assert.match(page,/No preceding captured stage for comparison/);
  assert.doesNotMatch(page,/First published estimate for this quarter/);
});

test('search indexes only verified stages, not a future third estimate',()=>{
  const index=buildSearchIndex({...data,sources:[],records:[],events:[]});
  const q2=index.find(r=>r.title==='BEA GDP release history · 2026 Q2');
  assert.match(q2.summary,/Verified advance, second estimates/);
  assert.doesNotMatch(q2.summary,/third/);
  assert.doesNotMatch(q2.text,/third/);
});
