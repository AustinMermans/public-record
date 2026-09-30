// Cleveland Fed model estimates; never substitute them for agency releases.
import {chartMarkup, bindChart} from './chart.mjs';

const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const URL = 'https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting';
const metrics = [['cpi','CPI'],['core_cpi','Core CPI'],['pce','PCE'],['core_pce','Core PCE']];
const bases = [['mom','Monthly change · nonannualized'],['yoy','Year-over-year change'],['quarterly_saar','Quarterly change · annualized']];
const shortMonth = value => /^\d{4}-\d{2}$/.test(value||'') ? new Intl.DateTimeFormat('en-US',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(value+'-01T12:00:00Z')) : String(value||'');
const targetLabel = value => /^\d{4}Q[1-4]$/.test(value||'') ? value.slice(0,4)+' Q'+value.at(-1) : shortMonth(value);
const label = metric => metrics.find(([id])=>id===metric)?.[1]||metric;
const basisLabel = basis => bases.find(([id])=>id===basis)?.[1]||basis;
const source = `<a href="${URL}" target="_blank" rel="noopener noreferrer">Cleveland Fed source ↗</a>`;
const rowsFor = (bundle,basis) => (bundle?.rows||[]).filter(row=>row.basis===basis);
const pending = (bundle,basis,metric) => rowsFor(bundle,basis).filter(row=>row.values?.[metric]!==null).sort((a,b)=>a.target.localeCompare(b.target));
const selectRow = (bundle,basis,metric,target) => {
  const rows=rowsFor(bundle,basis).sort((a,b)=>b.target.localeCompare(a.target));
  return rows.find(row=>row.target===target)||pending(bundle,basis,metric)[0]||rows[0]||null;
};
const pointsFor = (bundle,basis,metric,target) => (bundle?.history||[]).map(snapshot=>{
  const row=snapshot.rows?.find(item=>item.basis===basis&&item.target===target);
  return row?.values?.[metric]===null||!row?.values?.[metric]?null:{day:row.updated_on,value:Number(row.values[metric]),captured_at:snapshot.captured_at};
}).filter(Boolean);
const publisherPoints = (bundle,basis,metric,target) => basis==='mom' ?
  (bundle?.publisher_history?.paths||[]).find(path=>path.target===target)?.series?.[metric]?.map(([day,value])=>({day,value:Number(value)}))||[] : [];
const displayed = value => Math.round((value+Number.EPSILON)*100)/100;
const lastMovement = points => {
  if(points.length<2)return null;
  const latest=points.at(-1),current=displayed(latest.value);
  for(let i=points.length-2;i>=0;i--)if(displayed(points[i].value)!==current)return {from:points[i],to:points[i+1],latest};
  return null;
};

export function inflationState(bundle,{basis='mom',metric='cpi',target}={}) {
  if(!bases.some(([id])=>id===basis))basis='mom';
  if(!metrics.some(([id])=>id===metric))metric='cpi';
  const row=selectRow(bundle,basis,metric,target),points=row?pointsFor(bundle,basis,metric,row.target):[];
  const officialPath=row?publisherPoints(bundle,basis,metric,row.target):[];
  const current=row?.values?.[metric]??null;
  const previous=current!==null&&points.length>1?points.at(-2):null;
  return {basis,metric,target:row?.target||null,row,current,previous,points,officialPath,
    movement:current===null?null:lastMovement(officialPath),
    options:rowsFor(bundle,basis).map(row=>row.target).sort().reverse(),
    status:bundle?.status||'unavailable'};
}

function changeText(state) {
  if(state.current===null)return 'The publisher leaves this forecast cell blank after the corresponding actual is released; no actual value is supplied here.';
  if(state.movement){const {from,to,latest}=state.movement,delta=Math.round((displayed(latest.value)-displayed(from.value))*100)/100;
    return `Last changed ${to.day} at the table's 0.01-point precision: ${displayed(from.value).toFixed(2)}% → ${displayed(latest.value).toFixed(2)}% (${delta>0?'+':''}${delta.toFixed(2)} percentage points).`;}
  if(state.officialPath.length>1)return `Unchanged at the table's 0.01-point precision across the publisher's ${state.officialPath[0].day}–${state.officialPath.at(-1).day} chart path.`;
  if(!state.previous)return 'First retained Public Record capture for this measure and target; no earlier captured comparison.';
  const change=Number(state.current)-state.previous.value;
  if(change===0&&state.previous.day===state.row.updated_on)return 'No earlier model-update day has been captured for this target.';
  if(change===0)return `Unchanged from our prior captured edition (${state.previous.day}).`;
  return `${change>0?'Up':'Down'} ${Math.abs(change).toFixed(2)} percentage point${Math.abs(change)===1?'':'s'} from our prior captured edition (${state.previous.day}).`;
}

function historyMarkup(bundle,state) {
  const fromPublisher=state.basis==='mom'&&state.officialPath.length>0;
  const byDay=new Map((fromPublisher?state.officialPath:state.points).map(point=>[point.day,point]));
  const points=[...byDay.values()].sort((a,b)=>a.day.localeCompare(b.day)).map(point=>[point.day,point.value]);
  const chart=points.length>1?chartMarkup(points,{width:620,label:`${label(state.metric)} nowcast for ${targetLabel(state.target)}`,
    unit:'percent',esc,nf:(n,p)=>Number(n).toFixed(p),axisPrecision:3,tick:d=>d.slice(5),idPrefix:'inflation-chart'}):
    '<p class="meta">A trend needs two distinct publisher update days. The collection-era history begins with our first successful capture.</p>';
  const rows=fromPublisher?state.officialPath:state.points;
  const evidence=fromPublisher?`Current publisher chart edition ${esc(bundle.publisher_history.paths.find(path=>path.target===state.target)?.edition_date||'')} · <a href="${esc(bundle.publisher_history.url)}" target="_blank" rel="noopener noreferrer">Chart data ↗</a>. Earlier plotted dates are not separately archived original daily editions.`:'Our own successful captures only; historical model updates before collection are unavailable.';
  return `<div class="inflation-history"><h3>How this target moved</h3><p class="meta">${evidence}</p><div id="inflation-chart" class="chart-container">${chart}</div><details><summary>View ${rows.length} dated estimate${rows.length===1?'':'s'}</summary><div class="table-wrap"><table><thead><tr><th>Model date</th><th class="numeric">Estimate</th></tr></thead><tbody>${rows.slice().reverse().map(p=>`<tr><td>${esc(p.day)}</td><td class="numeric">${p.value.toFixed(3)}%</td></tr>`).join('')}</tbody></table></div></details><details><summary>Our ${state.points.length} retained capture${state.points.length===1?'':'s'}</summary><div class="table-wrap"><table><thead><tr><th>Model date</th><th>Retrieved</th><th class="numeric">Estimate</th></tr></thead><tbody>${state.points.slice().reverse().map(p=>`<tr><td>${esc(p.day)}</td><td>${esc(p.captured_at)}</td><td class="numeric">${p.value.toFixed(2)}%</td></tr>`).join('')}</tbody></table></div></details></div>`;
}

export function inflationResults(bundle,options={}) {
  const state=inflationState(bundle,options);
  if(!state.row)return '<p class="empty">No verified inflation nowcast is available in this capture.</p>';
  const {row,current,basis,metric}=state;
  const released=current===null;
  return `<div id="inflation-detail" class="inflation-detail" data-basis="${basis}" data-metric="${metric}" data-target="${esc(row.target)}"><div class="section-no">${esc(basisLabel(basis))} · ${esc(targetLabel(row.target))}</div><h2>${esc(label(metric))} inflation</h2><div class="inflation-number">${released?'—':esc(current)+'<small>%</small>'}</div><p class="inflation-reading">${esc(changeText(state))}</p><p class="meta">${released?'No current model estimate in this cell':'Cleveland Fed model update '+esc(row.updated_on)} · Retrieved ${esc(bundle.captured_at||'unavailable')}${bundle.status!=='ok'?' · <span class="warning">Retained from a stale capture</span>':''} · ${source}</p>${historyMarkup(bundle,state)}<p class="meta inflation-method">One model's estimate, not a BLS or BEA release, survey consensus, market-implied rate or trading signal. Monthly changes are seasonally adjusted and nonannualized; quarterly rates are seasonally adjusted annualized. CPI year-over-year uses nonseasonally adjusted data; PCE year-over-year uses seasonally adjusted data. A blank model cell is not zero; we do not substitute an unverified actual. The plotted monthly path is the publisher's current historical edition, not an archive of its original daily publications. Public Record's own captures begin at collection.</p></div>`;
}

function card(bundle,metric) {
  const state=inflationState(bundle,{metric});
  if(!state.row||state.current===null)return '';
  const href=`#inflation-watch?metric=${metric}&basis=mom&target=${state.target}`;
  const move=state.movement,delta=move?Math.round((displayed(move.latest.value)-displayed(move.from.value))*100)/100:null;
  return `<a class="inflation-card" href="${esc(href)}"><span>${esc(label(metric))} · ${esc(targetLabel(state.target))}</span><strong>${esc(state.current)}%</strong><small>Monthly, nonannualized · updated ${esc(state.row.updated_on)}${move?` · last changed ${esc(move.to.day)} (${delta>0?'+':''}${delta.toFixed(2)} pp)`:''}</small></a>`;
}

export function inflationTeaser(bundle) {
  if(!bundle)return '';
  return `<section class="section inflation-teaser"><div class="section-head"><h2><a href="#inflation-watch">Inflation nowcast →</a></h2><span class="meta">Cleveland Fed · ${esc(bundle.status)}</span></div>${bundle.status==='ok'?`<div class="inflation-cards">${card(bundle,'cpi')}${card(bundle,'core_pce')}</div>`:'<p class="warning">Current model retrieval unavailable; inspect the retained edition and source.</p>'}<p class="meta">Each estimate keeps its own target month; these are model forecasts, not official readings. ${source}</p></section>`;
}

export function inflationPage(bundle,options={}) {
  const state=inflationState(bundle,options);
  return `<div class="page-title"><div><div class="section-no">Outlook / Cleveland Fed</div><h1>Inflation nowcast</h1></div></div>${bundle?.status==='stale'?'<p class="warning">The latest retrieval failed. Values below are retained from the last verified capture.</p>':''}<div class="filters inflation-controls"><label>Measure<select id="inflation-metric">${metrics.map(([id,name])=>`<option value="${id}"${state.metric===id?' selected':''}>${name}</option>`).join('')}</select></label><label>Rate basis<select id="inflation-basis">${bases.map(([id,name])=>`<option value="${id}"${state.basis===id?' selected':''}>${name}</option>`).join('')}</select></label><label>Target<select id="inflation-target">${state.options.map(target=>`<option value="${esc(target)}"${state.target===target?' selected':''}>${esc(targetLabel(target))}</option>`).join('')}</select></label></div><div id="inflation-results">${inflationResults(bundle,state)}</div><div class="table-wrap inflation-table"><table><thead><tr><th>Model target</th>${metrics.map(([,name])=>`<th class="numeric">${name}</th>`).join('')}</tr></thead><tbody>${rowsFor(bundle,state.basis).map(row=>`<tr><th>${esc(targetLabel(row.target))}</th>${metrics.map(([id])=>`<td class="numeric">${row.values[id]===null?'—':`<a href="#inflation-watch?metric=${id}&basis=${state.basis}&target=${row.target}">${esc(row.values[id])}%</a>`}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="meta">A dash means this model cell is blank after the corresponding actual's release; it is not zero. ${source}</p>`;
}

export function bindInflation(root,bundle) {
  const metric=root.querySelector('#inflation-metric'),basis=root.querySelector('#inflation-basis'),target=root.querySelector('#inflation-target'),results=root.querySelector('#inflation-results');
  if(!metric||!basis||!target||!results)return;
  const bindHistory=()=>{const state=inflationState(bundle,{metric:metric.value,basis:basis.value,target:target.value});
    const byDay=new Map((state.basis==='mom'&&state.officialPath.length?state.officialPath:state.points).map(point=>[point.day,point]));
    const points=[...byDay.values()].sort((a,b)=>a.day.localeCompare(b.day)).map(point=>[point.day,point.value]);
    bindChart(results.querySelector('#inflation-chart'),points,{label:d=>d,unit:'percent',nf:(n,p)=>Number(n).toFixed(p)});
  };
  const update=changed=>{
    const next=inflationState(bundle,{metric:metric.value,basis:basis.value,target:changed==='target'?target.value:null});
    target.innerHTML=next.options.map(value=>`<option value="${esc(value)}"${next.target===value?' selected':''}>${esc(targetLabel(value))}</option>`).join('');
    results.innerHTML=inflationResults(bundle,next);
    root.querySelectorAll('.inflation-table tbody').forEach(body=>{body.innerHTML=rowsFor(bundle,next.basis).map(row=>`<tr><th>${esc(targetLabel(row.target))}</th>${metrics.map(([id])=>`<td class="numeric">${row.values[id]===null?'—':`<a href="#inflation-watch?metric=${id}&basis=${next.basis}&target=${row.target}">${esc(row.values[id])}%</a>`}</td>`).join('')}</tr>`).join('');});
    history.replaceState(null,'',`#inflation-watch?metric=${next.metric}&basis=${next.basis}&target=${next.target||''}`);
    bindHistory();
  };
  for(const [control,kind] of [[metric,'metric'],[basis,'basis'],[target,'target']])control.addEventListener('change',event=>{event.stopPropagation();update(kind);control.focus({preventScroll:true});});
  bindHistory();
}
