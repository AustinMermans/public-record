import test from 'node:test';
import assert from 'node:assert/strict';
import {observationLabel,suffixFor,isUpcoming,transformSeries,matchLens,parseTerms} from '../site/data-utils.mjs';
test('quarterly and daily periods remain distinguishable',()=>{
 assert.equal(observationLabel({frequency:'Quarterly'},'2026-04-01'),'Q2 2026');
 assert.equal(observationLabel({frequency:'Daily'},'2026-09-25'),'Sep 25, 2026');
 assert.equal(observationLabel({frequency:'Monthly'},'2026-08-01'),'Aug 2026');
});
test('spread is percentage points not percent',()=>assert.equal(suffixFor({id:'T10Y2Y'},'Percentage points'),' pp'));
test('elapsed timestamp excluded; date-only today preserved',()=>{
 const now=new Date('2026-09-28T21:18:00Z');
 assert.equal(isUpcoming('2026-09-28T11:30:00-04:00',now),false);
 assert.equal(isUpcoming('2026-09-28',now),true);
 assert.equal(isUpcoming('2026-09-29T08:30:00-04:00',now),true);
});
test('yoy matches month rather than accidentally using 12th prior row',()=>{
 const s={transform:'yoy',observations:[['2025-01-01',100],['2025-03-01',200],['2026-01-01',110],['2026-02-01',300],['2026-03-01',210]]};
 const p=transformSeries(s).points;assert.equal(p.length,2);assert.ok(Math.abs(p[0][1]-10)<1e-9);assert.ok(Math.abs(p[1][1]-5)<1e-9);
});
test('GDP annualization and payroll delta',()=>{
 assert.ok(Math.abs(transformSeries({transform:'qoq',observations:[['2026-01-01',100],['2026-04-01',101]]}).points[0][1]-4.060401)<1e-8);
 assert.equal(transformSeries({transform:'change',observations:[['2026-07-01',159000],['2026-08-01',159162]],unit:'Thousands'}).points[0][1],162);
});
test('exposure matches disclose exact field and literal term, no regex',()=>{
 const r={title:'Semiconductor disclosures',summary:'Patent grant',agencies:['Commerce Department']};
 assert.deepEqual(matchLens(r,['patent','commerce']),[{term:'patent',field:'summary'},{term:'commerce',field:'agency'}]);
 assert.deepEqual(matchLens(r,['.*']),[]);
 assert.deepEqual(parseTerms(' Patent, patent, commerce, '),['patent','commerce']);
});
