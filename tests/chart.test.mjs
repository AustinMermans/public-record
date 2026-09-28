import test from 'node:test';
import assert from 'node:assert/strict';
import {nearestIndex, chartGeometry, chartMarkup} from '../site/chart.mjs';

test('nearest observation clamps edges, resolves ties, and respects missing periods', () => {
  assert.equal(nearestIndex([], 3), -1);
  assert.equal(nearestIndex([10], 100), 0);
  const dates = [10, 20, 100];
  for (const [target, expected] of [[-50,0],[15,0],[19,1],[51,1],[61,2],[1000,2]]) assert.equal(nearestIndex(dates, target), expected);
});
test('geometry uses elapsed dates, not equally spaced observations', () => {
  const g = chartGeometry([['2020-01-01', 2], ['2020-01-02', 2], ['2020-01-11', 2]], 400);
  assert.ok(Math.abs((g.x(1)-g.x(0))/(g.x(2)-g.x(0))-.1)<1e-9);
  assert.ok(Number.isFinite(g.y(2)));
  assert.equal(g.x(0), g.L);
  assert.equal(g.x(2), 400-g.R);
});
test('chart supplies one full plot target and access to every observation', () => {
  const points = Array.from({length:200}, (_,i)=>[new Date(Date.UTC(2020,0,i+1)).toISOString().slice(0,10),i]);
  const html = chartMarkup(points,{width:400,label:'Test',unit:'Percent',esc:String,nf:String,tick:String});
  assert.match(html,/class="chart-hit"/);
  assert.match(html,/max="199"/);
  assert.match(html,/Inspect observation/);
  assert.doesNotMatch(html,/data-point=/);
  assert.match(chartMarkup([],{}),/Not enough observations/);
});
