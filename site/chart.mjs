// All interactions inspect real observations; never interpolate a displayed value.
export function nearestIndex(dates, target) {
  if (!dates.length) return -1;
  let lo = 0, hi = dates.length - 1;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (dates[mid] < target) lo = mid + 1;
    else hi = mid;
  }
  return lo > 0 && target - dates[lo - 1] <= dates[lo] - target ? lo - 1 : lo;
}

export function chartGeometry(points, width) {
  const height = width < 500 ? 270 : 310, L = 66, R = 18, T = 20, B = 42;
  const dates = points.map(p => Date.parse(p[0]));
  const values = points.map(p => p[1]);
  const lo = Math.min(...values), hi = Math.max(...values), pad = (hi - lo || 1) * .12;
  const min = lo - pad, max = hi + pad;
  return {width, height, L, R, T, B, dates, min, max,
    x: i => L + (dates[i] - dates[0]) / (dates.at(-1) - dates[0] || 1) * (width - L - R),
    y: v => T + (max - v) / (max - min) * (height - T - B)};
}

export function chartMarkup(points, {width, label, unit, esc, nf, tick, idPrefix='chart', connect=()=>true, axisPrecision}) {
  if (points.length < 2) return '<div class="empty">Not enough observations to draw this window.</div>';
  const g = chartGeometry(points, width), {height, L, R, T, B, min, max, x, y} = g;
  let svg = '';
  for (let i = 0; i < 5; i++) {
    const v = min + (max - min) * i / 4;
    svg += `<line class="grid" x1="${L}" x2="${width - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 12}" y="${y(v) + 4}" text-anchor="end">${nf(v, axisPrecision ?? (Math.abs(max) > 1000 ? 0 : 1))}</text>`;
  }
  const ticks = width < 500 ? 3 : 5;
  for (let i = 0; i < ticks; i++) {
    const ix = Math.round(i * (points.length - 1) / (ticks - 1));
    svg += `<text x="${x(ix)}" y="${height - 9}" text-anchor="${i === 0 ? 'start' : i === ticks - 1 ? 'end' : 'middle'}">${esc(tick(points[ix][0]))}</text>`;
  }
  if (min < 0 && max > 0) svg += `<line class="zero" x1="${L}" x2="${width - R}" y1="${y(0)}" y2="${y(0)}"/>`;
  const path = points.map((p, i) => `${i && connect(points[i-1],p) ? 'L' : 'M'}${x(i).toFixed(2)},${y(p[1]).toFixed(2)}`).join(' ');
  const gapEnds=new Set();
  points.forEach((p,i)=>{if(i&&!connect(points[i-1],p)){gapEnds.add(i-1);gapEnds.add(i);}});
  for(const i of gapEnds)svg+=`<circle class="trace" cx="${x(i).toFixed(2)}" cy="${y(points[i][1]).toFixed(2)}" r="2.5"/>`;
  svg += `<path class="trace" d="${path}"/><g class="chart-cursor" aria-hidden="true"><line class="crosshair" y1="${T}" y2="${height - B}"/><circle r="5"/></g><rect class="chart-hit" x="${L}" y="${T}" width="${width - L - R}" height="${height - T - B}" fill="transparent"/>`;
  return `<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(label)}; ${esc(unit)}. Explore exact values with the observation slider below.">${svg}</svg>
    <div class="chart-inspection"><div class="chart-readout"></div><span class="chart-selection-state meta"></span></div>
    <div class="chart-scrubber"><button type="button" data-chart-step="-1" aria-label="Previous observation">←</button><label class="sr-only" for="${esc(idPrefix)}-observation">Inspect observation</label><input class="chart-observation" id="${esc(idPrefix)}-observation" type="range" min="0" max="${points.length - 1}" step="1" value="${points.length - 1}" aria-describedby="${esc(idPrefix)}-help"><button type="button" data-chart-step="1" aria-label="Next observation">→</button><button type="button" class="chart-latest" id="${esc(idPrefix)}-latest">Latest</button></div>
    <p class="meta chart-help" id="${esc(idPrefix)}-help">Hover to inspect · click or tap to pin · slider or arrow buttons to step</p><span class="sr-only chart-announcement" id="${esc(idPrefix)}-announcement" role="status"></span>`;
}

export function bindChart(container, points, {label, unit, nf, selection}) {
  const svg = container.querySelector('svg.chart');
  if (!svg || points.length < 2) return;
  const g = chartGeometry(points, svg.viewBox.baseVal.width);
  const slider = container.querySelector('.chart-observation');
  const hit = container.querySelector('.chart-hit');
  let index = selection ? nearestIndex(g.dates, Date.parse(selection.date)) : points.length - 1;
  let pinned = selection?.pinned || false;
  function show(next, announce = false) {
    index = Math.max(0, Math.min(points.length - 1, next));
    const p = points[index], text = `${label(p[0])} · ${nf(p[1], 3)} ${unit}`;
    const line = container.querySelector('.crosshair'), dot = container.querySelector('.chart-cursor circle');
    line.setAttribute('x1', g.x(index)); line.setAttribute('x2', g.x(index));
    dot.setAttribute('cx', g.x(index)); dot.setAttribute('cy', g.y(p[1]));
    container.querySelector('.chart-readout').textContent = text;
    container.querySelector('.chart-selection-state').textContent = pinned ? 'Pinned' : index === points.length - 1 ? 'Latest in view' : 'Inspecting';
    slider.value = index; slider.setAttribute('aria-valuetext', text);
    for (const btn of container.querySelectorAll('[data-chart-step]')) btn.disabled = Number(btn.dataset.chartStep) < 0 ? index === 0 : index === points.length - 1;
    if (announce) container.querySelector('.chart-announcement').textContent = text + (pinned ? ' · pinned' : ' · latest in view');
  }
  function atPointer(e) {
    const rect = svg.getBoundingClientRect(), local = (e.clientX - rect.left) * g.width / rect.width;
    const ratio = Math.max(0, Math.min(1, (local - g.L) / (g.width - g.L - g.R)));
    return nearestIndex(g.dates, g.dates[0] + ratio * (g.dates.at(-1) - g.dates[0]));
  }
  hit.addEventListener('pointermove', e => {if (!pinned && e.pointerType !== 'touch') show(atPointer(e));});
  hit.addEventListener('click', e => {pinned = true; show(atPointer(e), true);});
  svg.addEventListener('pointerleave', () => {if (!pinned) show(points.length - 1);});
  slider.addEventListener('input', () => {pinned = true; show(Number(slider.value));});
  // Avoid the page's filter-change handler rebuilding this focused control.
  slider.addEventListener('change', e => e.stopPropagation());
  for (const btn of container.querySelectorAll('[data-chart-step]')) btn.addEventListener('click', () => {pinned = true; show(index + Number(btn.dataset.chartStep), true);});
  container.querySelector('.chart-latest').addEventListener('click', () => {pinned = false; show(points.length - 1, true);});
  show(index);
  return () => ({date: points[index][0], pinned});
}
