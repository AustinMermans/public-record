import {escapeText as esc} from './editorial.mjs';

export const spfMeasures = [
  ['RGDP','Real GDP growth'],['UNEMP','Unemployment'],['CPI','Headline CPI inflation'],
  ['CORECPI','Core CPI inflation'],['PCE','Headline PCE inflation'],['COREPCE','Core PCE inflation']
];
const label = id => spfMeasures.find(([key])=>key===id)?.[1] || id;
const fmt = value => Number.isFinite(value) ? value.toFixed(2)+'%' : '—';
const quarter = value => String(value||'').replace(/^(\d{4})Q([1-4])$/,'$1 Q$2');
const official = url => /^https:\/\/www\.philadelphiafed\.org\//.test(url||'');
const source = (url,text) => official(url) ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)} ↗</a>` : 'Source unavailable';
const series = (spf,id) => spf?.series?.[id]?.points || [];
const byRelease = (a,b) => a.released.localeCompare(b.released)||a.survey.localeCompare(b.survey);
const targets = (spf,id) => [...new Set(series(spf,id).map(p=>p.target))].sort().reverse();
const deltaText = (now,then) => {
  if(!then)return 'First forecast for this target';
  const change=now.value-then.value;
  if(change===0)return `Unchanged since ${quarter(then.survey)}`;
  if(Math.abs(change)<0.05)return `${change>0?'Up':'Down'} less than 0.1 percentage point since ${quarter(then.survey)}`;
  return `${change>0?'+':''}${change.toFixed(1)} percentage points since ${quarter(then.survey)}`;
};
const shortDelta = (now,then) => {
  if(!then)return 'New target';
  const change=now.value-then.value;
  const movement=change===0?'unchanged':Math.abs(change)<0.05?`${change>0?'up':'down'} <0.1 pp`:`${change>0?'+':''}${change.toFixed(1)} pp`;
  return `${movement} vs ${quarter(then.survey)}`;
};

export function spfState(spf,{metric='RGDP',target}={}) {
  if(!spf?.series)return null;
  metric=spfMeasures.some(([id])=>id===metric)?metric:'RGDP';
  const points=series(spf,metric).slice().sort(byRelease),available=targets(spf,metric);
  if(!points.length)return {metric,target:null,points:[],available,latestSurvey:null};
  const latestSurvey=points.at(-1).survey;
  const latestTargets=points.filter(p=>p.survey===latestSurvey).map(p=>p.target).sort();
  const preferred=latestTargets[1]||latestTargets[0];
  target=available.includes(target)?target:preferred;
  return {metric,target,available,latestSurvey,points:points.filter(p=>p.target===target)};
}

function trendSvg(points) {
  if(!points.length)return '';
  const values=points.map(p=>p.value),minimum=Math.min(...values),maximum=Math.max(...values),pad=Math.max(.15,(maximum-minimum)*.18),lo=minimum-pad,hi=maximum+pad;
  const coords=points.map((p,i)=>({x:48+(points.length===1?272:i*544/(points.length-1)),y:153-(p.value-lo)*114/(hi-lo)}));
  const path=coords.map((p,i)=>(i?'L':'M')+p.x.toFixed(1)+' '+p.y.toFixed(1)).join(' ');
  return `<svg class="spf-chart" viewBox="0 0 640 205" role="img" aria-label="Forecast for the same target across survey releases; exact values listed below"><line x1="48" y1="153" x2="592" y2="153" class="spf-axis"/><line x1="48" y1="39" x2="592" y2="39" class="spf-grid"/><text x="4" y="43">${esc(hi.toFixed(1))}%</text><text x="4" y="157">${esc(lo.toFixed(1))}%</text>${points.length>1?`<path d="${path}" class="spf-trace"/>`:''}${coords.map((p,i)=>`<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="6" data-spf-point="${i}" role="button" tabindex="0" aria-label="${esc(quarter(points[i].survey))}, ${esc(fmt(points[i].value))}"/><text x="${p.x.toFixed(1)}" y="185" text-anchor="middle">${esc(quarter(points[i].survey))}</text>`).join('')}</svg>`;
}

export function spfResults(spf,options={}) {
  const state=spfState(spf,options);if(!state?.target)return '<p class="empty-day">No released SPF forecasts in this capture.</p>';
  const {metric,target,latestSurvey,points}=state,latest=points.at(-1),previous=points.length>1?points.at(-2):null;
  const latestTargets=targets(spf,metric).filter(t=>series(spf,metric).some(p=>p.survey===latestSurvey&&p.target===t)).sort();
  const sourceName=metric==='RGDP'?'medianGrowth':'medianLevel',book=spf.sources?.[sourceName];
  return `<div class="spf-current"><div><div class="section-no">${esc(label(metric))} · ${esc(quarter(target))}</div><div class="spf-value">${esc(fmt(latest.value))}</div><p class="meta">${esc(metric==='UNEMP'?'Quarterly average rate':'Quarter-over-quarter annualized rate')} · ${esc(quarter(latest.survey))} survey, released ${esc(latest.released)}</p></div><div class="spf-delta">${esc(deltaText(latest,previous))}<p class="meta">Same calendar target and measure. A new target has no prior-survey revision.</p></div></div><div class="spf-reading"><div><h3>How this target moved</h3>${trendSvg(points)}<p id="spf-readout" class="meta" role="status" aria-atomic="true">${esc(quarter(latest.survey))} survey · released ${esc(latest.released)} · ${esc(fmt(latest.value))} · ${esc(latest.cell)}</p><div class="spf-point-list">${points.map((p,i)=>`<button type="button" data-spf-point="${i}"${i===points.length-1?' aria-pressed="true"':''}>${esc(quarter(p.survey))}<strong>${esc(fmt(p.value))}</strong></button>`).join('')}</div></div><div><h3>Latest five-quarter path</h3><div class="table-wrap"><table class="spf-path"><thead><tr><th>Target</th><th class="numeric">Forecast</th></tr></thead><tbody>${latestTargets.map(t=>{const p=series(spf,metric).find(x=>x.survey===latestSurvey&&x.target===t);const href='#outlook?forecast=spf&metric='+encodeURIComponent(metric)+'&target='+encodeURIComponent(t);return `<tr${t===target?' class="selected"':''}><td><a href="${esc(href)}">${esc(quarter(t))}</a></td><td class="numeric">${esc(fmt(p?.value))}</td></tr>`;}).join('')}</tbody></table></div><p class="meta">Latest survey: ${esc(quarter(latestSurvey))}. Earlier target quarters remain selectable above.</p></div></div><p class="meta spf-provenance">${source(book?.url,'Median forecast workbook')} · ${source(spf.sources?.release_dates?.url,'Release dates')} · ${source('https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/survey-of-professional-forecasters/spf-documentation.pdf','Documentation')} · Latest forecast cell ${esc(latest.cell)} · Retrieved ${esc(spf.captured_at||'unavailable')}${spf.status==='stale'?' · <span class="warning">Stale capture</span>':''}</p><p class="meta">These are survey medians, not FOMC projections or GDPNow. Real GDP growth is derived from median forecast levels; inflation is the median submitted rate. Values shown to two decimals from workbook cells; the release summary may round differently. Historical values are from the current workbook edition, not reconstructed files as published on each old release date.</p>`;
}

export function spfPanel(spf,options={}) {
  if(!spf)return `<section id="forecast-spf" class="section"><div class="section-head"><h2>Professional forecasters</h2></div><p class="meta">SPF collection has not run in this capture.</p></section>`;
  const state=spfState(spf,options);
  return `<section id="forecast-spf" class="section spf-panel"><div class="section-head"><h2>Professional forecasters</h2><span class="meta">Philadelphia Fed · quarterly survey medians</span></div><div class="filters spf-controls"><label>Measure<select id="spf-metric">${spfMeasures.map(([id,name])=>`<option value="${id}"${state?.metric===id?' selected':''}>${esc(name)}</option>`).join('')}</select></label><label>Target quarter<select id="spf-target">${(state?.available||[]).map(t=>`<option value="${esc(t)}"${state?.target===t?' selected':''}>${esc(quarter(t))}</option>`).join('')}</select></label></div><div id="spf-results">${spfResults(spf,state||{})}</div></section>`;
}

export function spfTeaser(spf) {
  const state=spfState(spf);if(!state?.target)return '';
  const rows=['RGDP','UNEMP','COREPCE'].map(metric=>{
    const current=spfState(spf,{metric,target:state.target}),p=current?.points.at(-1),prior=current?.points.length>1?current.points.at(-2):null;
    return p?`<div><span>${esc(label(metric))}</span><a class="metric-link" href="${esc('#outlook?forecast=spf&metric='+metric+'&target='+encodeURIComponent(state.target))}">${esc(fmt(p.value))}</a><small>${esc(shortDelta(p,prior))}</small></div>`:'';
  }).join('');
  return `<article class="forecast-teaser spf-teaser"><div class="section-no">Survey medians · ${esc(quarter(state.latestSurvey))}</div><h2><a href="#outlook?forecast=spf">Professional forecasters</a></h2><p class="meta">${esc(quarter(state.target))} target · released ${esc(state.points.at(-1).released)}${spf.status==='stale'?' · stale capture':''}</p><div class="spf-teaser-values">${rows}</div><p class="meta">Real GDP growth and core PCE: quarterly annualized; unemployment: quarterly average. ${source('https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/median-forecasts','Source')}</p></article>`;
}

export function bindSPF(root,spf) {
  const metric=root.querySelector('#spf-metric'),target=root.querySelector('#spf-target'),results=root.querySelector('#spf-results');
  if(!metric||!target||!results)return;
  const refresh=metricChanged=>{
    const next=spfState(spf,{metric:metric.value,target:target.value});
    if(metricChanged)target.innerHTML=next.available.map(t=>`<option value="${esc(t)}"${next.target===t?' selected':''}>${esc(quarter(t))}</option>`).join('');
    results.innerHTML=spfResults(spf,next);
    const params=new URLSearchParams({forecast:'spf',metric:next.metric,target:next.target});
    history.replaceState(null,'','#outlook?'+params);
  };
  metric.addEventListener('change',event=>{event.stopPropagation();refresh(true);});
  target.addEventListener('change',event=>{event.stopPropagation();refresh(false);});
  results.addEventListener('click',event=>{const item=event.target.closest('[data-spf-point]');if(item)inspect(Number(item.dataset.spfPoint));});
  results.addEventListener('keydown',event=>{const item=event.target.closest('circle[data-spf-point]');if(item&&['Enter',' '].includes(event.key)){event.preventDefault();inspect(Number(item.dataset.spfPoint));}});
  function inspect(index){
    const state=spfState(spf,{metric:metric.value,target:target.value}),p=state?.points[index];if(!p)return;
    results.querySelector('#spf-readout').textContent=`${quarter(p.survey)} survey · released ${p.released} · ${fmt(p.value)} · ${p.cell}`;
    results.querySelectorAll('[data-spf-point]').forEach(el=>{const active=Number(el.dataset.spfPoint)===index;el.classList.toggle('active',active);if(el.tagName==='BUTTON')el.setAttribute('aria-pressed',String(active));});
  }
}
