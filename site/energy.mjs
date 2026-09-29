import {chartMarkup, bindChart} from './chart.mjs';

const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const source = (url, label) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`;
const signed = (v, unit='') => `${Number(v)>0?'+':''}${Number(v).toFixed(unit==='%'?1:3)}${unit}`;
const date = v => new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(new Date(v+'T12:00:00Z'));
const captureTime = v => new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit',timeZone:'America/New_York',timeZoneName:'short'}).format(new Date(v));

export function energyPage(data, selected='crude') {
  const e=data.energy;
  if(!e?.metrics?.length)return `<div class="page-title"><div><div class="section-no">Economy / Energy</div><h1>Petroleum inventories</h1></div></div><p>The EIA stock capture is unavailable. ${source('https://www.eia.gov/petroleum/supply/weekly/','Weekly Petroleum Status Report')}</p>`;
  const metrics=e.metrics, current=metrics.find(m=>m.id===selected)||metrics[0];
  const stale=e.status!=='ok';
  const crude=metrics.find(m=>m.id==='crude'),gas=metrics.find(m=>m.id==='gasoline'),dist=metrics.find(m=>m.id==='distillate');
  const read=`Commercial crude ${Number(crude.weekly_change)>=0?'rose':'fell'} ${Math.abs(Number(crude.weekly_change)).toFixed(3)} million barrels in the reported week; gasoline ${Number(gas.weekly_change)>=0?'rose':'fell'} ${Math.abs(Number(gas.weekly_change)).toFixed(3)} and distillate ${Number(dist.weekly_change)>=0?'rose':'fell'} ${Math.abs(Number(dist.weekly_change)).toFixed(3)}. Distillate stocks were ${Math.abs(Number(dist.year_change_pct)).toFixed(1)}% ${Number(dist.year_change_pct)<0?'below':'above'} the comparable week a year earlier. These are inventories, not demand or price forecasts.`;
  return `<div class="page-title"><div><div class="section-no">Economy / EIA</div><h1>Petroleum inventories</h1></div></div>
    <div class="energy-edition meta">Week ended ${esc(date(e.week_end))} · Published ${esc(date(e.published_at))} · Captured ${esc(captureTime(e.captured_at))}${stale?` · <strong class="warning">Stale; last attempted ${esc(captureTime(e.attempted_at))}</strong>`:''} · ${source(e.table_url,'EIA Table 4')}</div>
    <p class="energy-lead">${esc(read)}</p>
    <div class="energy-metrics" role="group" aria-label="Petroleum stock measures">${metrics.map(m=>`<a class="energy-metric${m.id===current.id?' selected':''}" href="#energy?metric=${esc(m.id)}" ${m.id===current.id?'aria-current="true"':''}><span class="section-no">${esc(m.label)}</span><strong>${Number(m.current).toFixed(3)}</strong><span class="meta">million barrels · week ${esc(date(m.current_week))}</span><span class="energy-deltas"><b>${signed(m.weekly_change)}</b> vs prior week<br><b>${signed(m.year_change_pct,'%')}</b> vs year-ago week</span></a>`).join('')}</div>
    <section class="section energy-detail" id="energy-${esc(current.id)}"><div class="section-head"><h2>${esc(current.label)}</h2><span class="meta">${source(current.url,'EIA stock table CSV')}</span></div>
    <p>${Number(current.current).toFixed(3)} million barrels on ${esc(date(current.current_week))}, ${signed(current.weekly_change)} million barrels from ${esc(date(current.prior_week))}. ${signed(current.year_change_pct,'%')} from ${esc(date(current.year_ago_week))}.</p>
    ${current.id==='crude'?`<div class="energy-chart" id="energy-chart"></div><p class="chart-caption">Weekly commercial crude, excluding the Strategic Petroleum Reserve · million barrels · current EIA rolling edition.</p><details><summary>View ${e.crude_history.length} observations</summary><div class="table-wrap"><table><thead><tr><th>Week ended</th><th class="numeric">Million barrels</th></tr></thead><tbody>${e.crude_history.slice().reverse().map(([d,v])=>`<tr><td>${esc(d)}</td><td class="numeric">${(v/1000).toFixed(3)}</td></tr>`).join('')}</tbody></table></div></details>`:''}
    <div class="energy-method"><h3>Reading this release</h3><p>Table 4 reports stock levels. A weekly inventory change is not production, consumption, or a price signal by itself. The year-ago comparison uses EIA’s published comparable week, which may not be exactly 52 weeks apart. The crude chart is the latest rolling JSON edition; it does not reconstruct what earlier reports originally published.</p><p>${source(e.json_url,'Crude history JSON')} · ${source(e.table_url,'Stock table CSV')} · ${source(e.schedule_url,'Official release schedule')}</p></div></section>`;
}

export function bindEnergy(root, data) {
  const holder=root.querySelector('#energy-chart'), history=data.energy?.crude_history;
  if(!holder||!history?.length)return;
  const points=history.map(([d,v])=>[d,v/1000]);
  let selection, width=0;
  const paint=()=>{
    const next=Math.max(280,Math.round(holder.getBoundingClientRect().width));
    if(next===width)return;
    width=next;
    holder.innerHTML=chartMarkup(points,{width:next,label:'Commercial crude, excluding SPR',unit:'million barrels',
      esc,nf:(n,d)=>Number(n).toFixed(d),tick:d=>new Intl.DateTimeFormat('en-US',{month:'short',year:'2-digit',timeZone:'UTC'}).format(new Date(d+'T12:00:00Z')),idPrefix:'energy-crude'});
    selection=bindChart(holder,points,{label:date,unit:'million barrels',nf:(n,d)=>Number(n).toFixed(d),selection:selection?.()});
  };
  paint();
  const observer=new ResizeObserver(()=>{if(holder.isConnected)paint();else observer.disconnect();});
  observer.observe(holder);
}
