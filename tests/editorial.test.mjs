import test from 'node:test';
import assert from 'node:assert/strict';
import {monthCells,moveMonth,easternDay,recordExplanation,calendarGrid} from '../site/editorial.mjs';
test('calendar includes leap day and Monday-based alignment',()=>{const d=monthCells('2024-02');assert.equal(d.filter(Boolean).length,29);assert.equal(d[3],'2024-02-01');assert.equal(d.length%7,0);});
test('month navigation crosses years',()=>{assert.equal(moveMonth('2026-12',1),'2027-01');assert.equal(moveMonth('2026-01',-1),'2025-12');});
test('calendar groups by Eastern date rather than UTC date',()=>assert.equal(easternDay('2026-09-29T02:00:00+00:00'),'2026-09-28'));
test('motion not treated as outcome',()=>{const s=recordExplanation({domain:'Legal',summary:'[Motion to Dismiss] ( 3 )'});assert.match(s.text,/not a dismissal ruling/);});
test('unknown entry stays attributed to feed',()=>assert.equal(recordExplanation({domain:'Legal',summary:'[Miscellaneous Filing] ( 2 )'}).label,'Court feed'));
test('calendar exposes selected day and event count',()=>{const grid=calendarGrid([{date:'2026-09-28'}],'2026-09','2026-09-28','2026-09-28');assert.match(grid,/aria-pressed="true" aria-label="2026-09-28, 1 events"/);});
