import {chartMarkup, bindChart} from './chart.mjs';

const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const source = (url, label) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`;
const signed = (v, unit='') => `${Number(v)>0?'+':''}${Number(v).toFixed(unit==='%'?1:3)}${unit}`;
const date = v => new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(new Date(v+'T12:00:00Z'));
const monthDay = v => new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',timeZone:'UTC'}).format(new Date(v+'T12:00:00Z'));
const captureTime = v => new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit',timeZone:'America/New_York',timeZoneName:'short'}).format(new Date(v));
const historyOf=(e,id)=>id==='crude'?e.crude_history:e.product_history?.[id];
const historyUrl=(e,id)=>id==='crude'?e.json_url:e.history_urls?.[id];
const inRange=(history,period)=>{
  if(period==='all')return history;
  const last=new Date(history.at(-1)[0]+'T12:00:00Z');
  last.setUTCFullYear(last.getUTCFullYear()-Number(period));
  const cutoff=last.toISOString().slice(0,10);
  return history.filter(([d])=>d>=cutoff);
};
export function sameSeason(history,week,current){
  if(!history?.length)return null;
  const target=new Date(week+'T12:00:00Z'), years=[];
  for(let age=5;age>=1;age--){
    const year=target.getUTCFullYear()-age;
    const lastDay=new Date(Date.UTC(year,target.getUTCMonth()+1,0)).getUTCDate();
    const anchor=Date.UTC(year,target.getUTCMonth(),Math.min(target.getUTCDate(),lastDay),12);
    const nearby=history.map(([day,value])=>({day,value,gap:Math.abs(Date.parse(day+'T12:00:00Z')-anchor)}))
      .sort((a,b)=>a.gap-b.gap)[0];
    if(!nearby||nearby.gap>3*86400000)return null;
    years.push(nearby);
  }
  const values=years.map(row=>row.value/1000), min=Math.min(...values),max=Math.max(...values);
  return {min,max,first:target.getUTCFullYear()-5,last:target.getUTCFullYear()-1,
    position:current<min?'below':current>max?'above':'within',
    observations:years.map(row=>[row.day,row.value/1000])};
}

export function energyPage(data, selected='crude', period='5') {
  const e=data.energy;
  if(!e?.metrics?.length)return `<div class="page-title"><div><div class="section-no">Economy / Energy</div><h1>Petroleum inventories</h1></div></div><p>The EIA stock capture is unavailable. ${source('https://www.eia.gov/petroleum/supply/weekly/','Weekly Petroleum Status Report')}</p>`;
  const metrics=e.metrics, current=metrics.find(m=>m.id===selected)||metrics[0];
  period=['1','5','10','all'].includes(period)?period:'5';
  const history=historyOf(e,current.id), plotted=history?.length?inRange(history,period):null;
  const historySource=historyUrl(e,current.id);
  const season=sameSeason(history,current.current_week,Number(current.current));
  const stale=e.status!=='ok';
  const crude=metrics.find(m=>m.id==='crude'),gas=metrics.find(m=>m.id==='gasoline'),dist=metrics.find(m=>m.id==='distillate');
  const read=`Commercial crude ${Number(crude.weekly_change)>=0?'rose':'fell'} ${Math.abs(Number(crude.weekly_change)).toFixed(3)} million barrels in the reported week; gasoline ${Number(gas.weekly_change)>=0?'rose':'fell'} ${Math.abs(Number(gas.weekly_change)).toFixed(3)} and distillate ${Number(dist.weekly_change)>=0?'rose':'fell'} ${Math.abs(Number(dist.weekly_change)).toFixed(3)}. Distillate stocks were ${Math.abs(Number(dist.year_change_pct)).toFixed(1)}% ${Number(dist.year_change_pct)<0?'below':'above'} the comparable week a year earlier. These are inventories, not demand or price forecasts.`;
  return `<div class="page-title"><div><div class="section-no">Economy / EIA</div><h1>Petroleum inventories</h1></div></div>
    <div class="energy-edition meta">Week ended ${esc(date(e.week_end))} · Published ${esc(date(e.published_at))} · Captured ${esc(captureTime(e.captured_at))}${stale?` · <strong class="warning">Stale; last attempted ${esc(captureTime(e.attempted_at))}</strong>`:''} · ${source(e.table_url,'EIA Table 4')}</div>
    <p class="energy-lead">${esc(read)}</p>
    <div class="energy-metrics" role="group" aria-label="Petroleum stock measures">${metrics.map(m=>`<a class="energy-metric${m.id===current.id?' selected':''}" href="#energy?metric=${esc(m.id)}&range=${period}" ${m.id===current.id?'aria-current="true"':''}><span class="section-no">${esc(m.label)}</span><strong>${Number(m.current).toFixed(3)}</strong><span class="meta">million barrels · week ${esc(date(m.current_week))}</span><span class="energy-deltas"><b>${signed(m.weekly_change)}</b> vs prior week<br><b>${signed(m.year_change_pct,'%')}</b> vs year-ago week</span></a>`).join('')}</div>
    <section class="section energy-detail" id="energy-${esc(current.id)}"><div class="section-head"><h2>${esc(current.label)}</h2><span class="meta">${source(current.url,'EIA stock table CSV')}</span></div>
    <p>${Number(current.current).toFixed(3)} million barrels on ${esc(date(current.current_week))}, ${signed(current.weekly_change)} million barrels from ${esc(date(current.prior_week))}. ${signed(current.year_change_pct,'%')} from ${esc(date(current.year_ago_week))}.</p>
    ${season?`<p class="energy-season"><strong>Same-season reference:</strong> ${Number(current.current).toFixed(3)} million barrels is ${season.position} the ${season.min.toFixed(3)}–${season.max.toFixed(3)} million-barrel range around the five prior ${esc(monthDay(current.current_week))} anniversaries (${season.first}–${season.last}). Each anchor uses the nearest reporting Friday within three days, which may fall in an adjacent calendar year${current.current_week.endsWith('02-29')?'; a nonexistent Feb 29 anchor uses Feb 28':''}; five observations, not a demand-normalized benchmark or price signal.</p><details class="energy-season-evidence"><summary>Five reference weeks and values</summary><div class="table-wrap"><table><thead><tr><th>Reporting week</th><th class="numeric">Million barrels</th></tr></thead><tbody>${season.observations.map(([d,v])=>`<tr><td>${esc(d)}</td><td class="numeric">${v.toFixed(3)}</td></tr>`).join('')}</tbody></table></div><p class="meta">${source(historySource,'EIA series source')}</p></details>`:''}
    ${plotted?`<div class="history-ranges" role="group" aria-label="Petroleum history range">${[['1','1Y'],['5','5Y'],['10','10Y'],['all','All']].map(([value,label])=>`<a href="#energy?metric=${esc(current.id)}&range=${value}" aria-current="${period===value}">${label}</a>`).join('')}</div><div class="energy-chart" id="energy-chart"></div><p class="chart-caption">Weekly stocks: ${esc(current.label)} · million barrels · current EIA series edition, not original-release vintages.${current.id==='distillate'&&period==='all'?' The earliest 1982–83 source history has missing weeks.':''}</p><details><summary>View ${plotted.length} observations in this range</summary><div class="table-wrap"><table><thead><tr><th>Week ended</th><th class="numeric">Million barrels</th></tr></thead><tbody>${plotted.slice().reverse().map(([d,v])=>`<tr><td>${esc(d)}</td><td class="numeric">${(v/1000).toFixed(3)}</td></tr>`).join('')}</tbody></table></div></details>`:`<p class="meta warning">Historical chart unavailable in this capture${e.history_errors?.[current.id]?` · ${esc(e.history_errors[current.id])}`:''}. The current stock figure above remains sourced from Table 4.</p>`}
    <div class="energy-method"><h3>Reading this release</h3><p>Table 4 reports stock levels. A weekly inventory change is not production, consumption, or a price signal by itself. The year-ago comparison uses EIA’s published comparable week, which may not be exactly 52 weeks apart. Histories show the current EIA series edition; they do not reconstruct what earlier reports originally published.</p><p>${historySource?source(historySource,'Selected history source')+' · ':''}${source(e.table_url,'Stock table CSV')} · ${source(e.schedule_url,'Official release schedule')}</p></div></section>`;
}

export function bindEnergy(root, data, selected='crude', period='5') {
  const current=data.energy?.metrics?.find(m=>m.id===selected)||data.energy?.metrics?.[0];
  const holder=root.querySelector('#energy-chart'), full=current&&historyOf(data.energy,current.id);
  const history=full?.length?inRange(full,['1','5','10','all'].includes(period)?period:'5'):null;
  if(!holder||!history?.length)return;
  const points=history.map(([d,v])=>[d,v/1000]);
  let selection, width=0;
  const paint=()=>{
    const next=Math.max(280,Math.round(holder.getBoundingClientRect().width));
    if(next===width)return;
    width=next;
    holder.innerHTML=chartMarkup(points,{width:next,label:current.label,unit:'million barrels',
      esc,nf:(n,d)=>Number(n).toFixed(d),tick:d=>new Intl.DateTimeFormat('en-US',{month:'short',year:'2-digit',timeZone:'UTC'}).format(new Date(d+'T12:00:00Z')),idPrefix:'energy-'+current.id,
      connect:(a,b)=>Date.parse(b[0])-Date.parse(a[0])===7*86400000});
    selection=bindChart(holder,points,{label:date,unit:'million barrels',nf:(n,d)=>Number(n).toFixed(d),selection:selection?.()});
  };
  paint();
  const observer=new ResizeObserver(()=>{if(holder.isConnected)paint();else observer.disconnect();});
  observer.observe(holder);
}
