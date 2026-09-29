import test from 'node:test';
import assert from 'node:assert/strict';
import {indicatorHref,metricLink,detailTarget} from '../site/metric-links.mjs';
import {fundingPage} from '../site/funding.mjs';
import {deskPage} from '../site/publication.mjs';
import {forecastPanels} from '../site/editorial.mjs';

test('indicator drill-down preserves preferred measure and full history',()=>{
  const href=indicatorHref('CPIAUCSL');
  assert.equal(href,'#economy?series=CPIAUCSL&transform=default&period=all');
  assert.ok(indicatorHref('X&Y').includes('X%26Y'));
});
test('metric values are accessible links, including zero, but missing values are not',()=>{
  const html=metricLink(indicatorHref('UNRATE'),'Unemployment',0,'%');
  assert.match(html,/<a class="metric-link"/);assert.match(html,/Unemployment: 0%. View detail/);
  for(const v of [null,undefined,'—'])assert.doesNotMatch(metricLink(indicatorHref('X'),'Missing',v),/<a/);
  assert.doesNotMatch(metricLink('javascript:bad','Unsafe',2),/<a/);
  assert.doesNotMatch(metricLink(indicatorHref('X'),'<script>', '<img>'),/<script>|<img>/);
});
test('detail routing allows only known report sections',()=>{
  assert.equal(detailTarget('funding',new URLSearchParams('view=banking&metric=noncurrent')),'banking-panel');
  assert.equal(detailTarget('fiscal',new URLSearchParams('view=monthly')),'fiscal-monthly');
  assert.equal(detailTarget('fiscal',new URLSearchParams('view=fytd')),'fiscal-fytd');
  assert.equal(detailTarget('fiscal',new URLSearchParams('view=unknown')),null);
  assert.equal(detailTarget('funding',new URLSearchParams('view=spread')),'funding-comparison');
  assert.equal(detailTarget('outlook',new URLSearchParams('forecast=gdpnow')),'forecast-gdpnow');
  assert.equal(detailTarget('outlook',new URLSearchParams('forecast=sep')),'forecast-sep');
  assert.equal(detailTarget('outlook',new URLSearchParams('forecast=unknown')),null);
});
test('funding headline links point to each rate, the spread detail, and global stress',()=>{
  const date='2026-09-25';
  const series=['NYFED-SOFR','NYFED-EFFR','OFR-FSI'].map((id,i)=>({id,source_id:id,name:id,publisher:'Source',url:'https://example.gov',captured_at:'2026-09-28',observations:[[date,i+1]],details:[{date,rate:i+1}]}));
  const html=fundingPage({series,sources:[]});
  for(const id of ['NYFED-SOFR','NYFED-EFFR','OFR-FSI'])assert.ok(html.includes('series='+id));
  assert.match(html,/href="#funding\?view=spread"/);
  assert.match(html,/id="funding-comparison"/);
});
test('outlook headline number and projection count target the corresponding report',()=>{
  const forecasts=[{id:'gdpnow',title:'GDPNow',value:2.5,target:'Q3',unit:'Percent',published_at:'2026-09-28',url:'https://example.gov',status:'ok'},
    {id:'sep',title:'SEP',rows:[{name:'GDP',values:[2]}],horizons:['2026'],published_at:'2026-09-16',url:'https://example.gov',status:'ok'}];
  const html=deskPage({research:{forecasts}},'outlook-home',{});
  assert.match(html,/class="metric-link" href="#outlook\?forecast=gdpnow"/);
  assert.match(html,/href="#outlook\?forecast=sep">1 indicators across 1 projection horizons/);
  const panels=forecastPanels({forecasts});
  assert.match(panels,/id="forecast-gdpnow"/);assert.match(panels,/id="forecast-sep"/);
});
