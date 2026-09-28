import {escapeText as esc} from './editorial.mjs';
import {chartMarkup, bindChart} from './chart.mjs';
import {indicatorHref, metricLink} from './metric-links.mjs';

const nf=(v,n=2)=>Number(v).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n});
const link=(u,t)=>`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t)} ↗</a>`;
const find=(d,id)=>d.series.find(s=>s.id===id);
const explore=s=>s?`<a href="#economy?series=${encodeURIComponent(s.id)}&period=all">${s.id.startsWith('NYFED-')?esc(s.id.slice(6))+' history':'History'} & export →</a>`:'';
const last=s=>s?.observations.at(-1);

export function alignedSpread(sofr,effr){
  const other=new Map(effr?.observations||[]);
  return (sofr?.observations||[]).filter(([day])=>other.has(day)).map(([day,v])=>[day,(v-other.get(day))*100]);
}

export function sourceNotice(s){
  if(!s?.attribution)return '';
  return `<div class="source-notice meta"><p>${esc(s.attribution)} ${link(s.terms_url,'Source terms')}</p>${s.affiliation_notice?`<p>${esc(s.affiliation_notice)}</p>`:''}${s.third_party_notice?`<p>${esc(s.third_party_notice)}</p>`:''}</div>`;
}

export function sourceLabel(s){return s.publisher+(s.as_of?' via ALFRED':s.source_id?.startsWith('fred-')?' / FRED':'');}

export function observationCsv(s,points,unit){
  const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  return 'observation_date,value,unit,source_url,captured_at,vintage_as_of,attribution,terms_url,affiliation_notice,third_party_notice\n'+points.map(([day,value])=>[day,value,unit,s.url,s.captured_at,s.as_of||'latest-revised',s.attribution,s.terms_url,s.affiliation_notice,s.third_party_notice].map(quote).join(',')).join('\n');
}

export function receipt(d,s,now=new Date()){
  if(!s)return '<p class="warning">Source unavailable in this capture.</p>';
  const source=d.sources.find(x=>x.id===s.source_id),age=now-Date.parse(s.captured_at);
  const warn=source?.status!=='ok'||!Number.isFinite(age)||age>36*3600000;
  return `<p class="meta ${warn?'warning':''}">Observation ${esc(last(s)?.[0]||'unavailable')} · Retrieved ${esc(s.captured_at)}${warn?' · '+esc(source?.status!=='ok'?(source?.status||'unavailable'):'retrieval older than 36 hours'):''}<br>${link(s.url,s.publisher)} · ${explore(s)}</p>`;
}

const metric=(label,value,unit,description,href)=>`<div class="kpi"><div class="kpi-label">${esc(label)}</div><div class="kpi-value">${metricLink(href,label,value===undefined?'—':nf(value),unit)}</div><p class="kpi-meta">${esc(description)}</p></div>`;

export function fundingPage(d){
  const sofr=find(d,'NYFED-SOFR'),effr=find(d,'NYFED-EFFR'),fsi=find(d,'OFR-FSI');
  const spread=alignedSpread(sofr,effr),p=spread.at(-1),prior=spread.at(-2),point=last(fsi);
  const day=p?.[0],sd=sofr?.details.find(x=>x.date===day),ed=effr?.details.find(x=>x.date===day);
  const delta=prior?Math.round((p[1]-prior[1])*1e8)/1e8:null,previousStress=fsi?.observations.at(-2);
  const rates=[['SOFR',sofr,sd],['EFFR',effr,ed]];
  const components=(ids)=>ids.map(id=>{
    const s=find(d,id),value=s?.observations.find(x=>x[0]===point?.[0]);
    return `<tr><td>${s?`<a href="#economy?series=${s.id}&period=all">${esc(s.name.replace(' contribution to global stress',''))}</a>`:esc(id)}</td><td class="numeric">${value?nf(value[1],3):'—'}</td></tr>`;
  }).join('');
  return `<div class="page-title"><div><div class="section-no">Funding & credit desk</div><h1>The cost of overnight money</h1><p>Money-market pricing and global financial stress. Not a corporate-bond spread or default-risk model.</p></div></div>
  <div class="kpis">${metric('SOFR',sd?.rate,'%',day?'Secured overnight funding · '+day:'No common effective date',indicatorHref('NYFED-SOFR'))}${metric('EFFR',ed?.rate,'%',day?'Unsecured federal funds · '+day:'No common effective date',indicatorHref('NYFED-EFFR'))}${metric('SOFR − EFFR',p?.[1],' bp',day?'Same-date comparison · '+day:'No aligned observations','#funding?view=spread')}${metric('Global financial stress',point?.[1],'',point?'Index points · '+point[0]:'Unavailable',indicatorHref('OFR-FSI'))}</div>
  <section class="section" id="funding-comparison"><div class="section-head"><h2>Secured versus unsecured funding</h2>${explore(sofr)}</div>
  ${p?`<p>The secured rate was <strong>${nf(Math.abs(p[1]))} basis points ${p[1]>=0?'above':'below'}</strong> the effective federal funds rate on ${esc(day)}.${delta===null?'':` The spread ${delta===0?'was unchanged':delta>0?'increased by '+nf(delta)+' bp':'decreased by '+nf(-delta)+' bp'} from the previous common observation (${esc(prior[0])}).`}</p>`:'<p class="warning">A same-date comparison is unavailable.</p>'}
  <p class="meta">Public Record calculation: (SOFR − EFFR) × 100. Effective dates must match; holidays and missing observations are not filled. These are realized overnight rates, not forecasts of policy.</p>
  <div id="funding-spread-chart" class="chart-container"></div>
  <div class="table-wrap"><table><caption>Latest common effective date: ${esc(day||'unavailable')}</caption><thead><tr><th>Rate</th><th class="numeric">Median, %</th><th class="numeric">1st–99th percentile, %</th><th class="numeric">Volume, $bn</th><th>Revision flag</th></tr></thead><tbody>${rates.map(([name,s,x])=>`<tr><td>${s?link(s.url,name):name}</td><td class="numeric">${x?nf(x.rate):'—'}</td><td class="numeric">${x?nf(x.p1)+'–'+nf(x.p99):'—'}</td><td class="numeric">${x?nf(x.volume_billions,0):'—'}</td><td>${x?(esc(x.revision_indicator)||'None supplied'):'—'}</td></tr>`).join('')}</tbody></table></div>
  <p class="meta">Different transaction markets: volumes are not combined. Rate dispersion is not a confidence interval. History is bounded to the latest 400 published effective dates per rate.</p>${receipt(d,sofr)}${receipt(d,effr)}${sourceNotice(sofr)}${sourceNotice(effr)}</section>
  <section class="section"><div class="section-head"><h2>Global financial stress</h2>${explore(fsi)}</div>
  ${point?`<p><strong>${nf(point[1],3)} index points</strong>: stress is ${point[1]>0?'above':point[1]<0?'below':'at'} the historical-average reference.${previousStress?` Change from ${esc(previousStress[0])}: <strong>${point[1]-previousStress[1]>=0?'+':''}${nf(point[1]-previousStress[1],3)} points</strong>.`:''} This is a global measure; a negative reading does not mean zero risk.</p>`:'<p class="warning">The global index is unavailable.</p>'}
  <div id="funding-stress-chart" class="chart-container"></div>
  <div class="story-grid"><div class="table-wrap"><table><caption>By market · index-point contributions</caption><thead><tr><th>Component</th><th class="numeric">${esc(point?.[0]||'No data')}</th></tr></thead><tbody>${components(['OFR-CREDIT','OFR-EQUITY','OFR-SAFE','OFR-FUNDING','OFR-VOLATILITY'])}</tbody></table></div><div class="table-wrap"><table><caption>By region · alternative decomposition</caption><thead><tr><th>Region</th><th class="numeric">${esc(point?.[0]||'No data')}</th></tr></thead><tbody>${components(['OFR-US','OFR-ADVANCED','OFR-EMERGING'])}</tbody></table></div></div>
  <p class="meta">The two decompositions each describe the same total; do not add them together. Components are signed contributions, not standalone stress indices or credit spreads. Rounding can prevent exact summation. OFR normally publishes with a two-business-day lag and may revise history.</p>${fsi?.quality_notes?.length?`<details><summary>${fsi.quality_notes.length} historical source-reconciliation exceptions</summary><p class="meta">Contributions differ from the total by more than 0.005 points on these source observations. Values remain as published; residual = component sum − total.</p><ul>${fsi.quality_notes.map(x=>`<li>${esc(x.date)} · ${esc(x.decomposition)} · ${nf(x.residual,3)} points</li>`).join('')}</ul></details>`:''}${receipt(d,fsi)}${sourceNotice(fsi)}</section>`;
}

const selections=new Map();
export function bindFunding(root,d,preserve=false){
  const spread=alignedSpread(find(d,'NYFED-SOFR'),find(d,'NYFED-EFFR'));
  const stress=find(d,'OFR-FSI')?.observations.slice(-260)||[];
  for(const [id,points,unit] of [['funding-spread-chart',spread,'Basis points'],['funding-stress-chart',stress,'Index points']]){
    const el=root.querySelector('#'+id);if(!el)continue;
    const width=Math.max(260,Math.round(el.clientWidth||700));
    if(preserve&&el.querySelector('svg.chart')?.viewBox.baseVal.width===width)continue;
    const selection=preserve?selections.get(id)?.():null;
    const active=document.activeElement,focus=el.contains(active)?active?.id|| (active?.dataset.chartStep?'[data-chart-step="'+active.dataset.chartStep+'"]':null):null;
    const label=day=>day;
    el.innerHTML=chartMarkup(points,{width,label:id==='funding-spread-chart'?'SOFR minus EFFR, common effective dates':'Global financial stress, latest 260 observations',unit,esc,nf,tick:day=>day.slice(0,7),idPrefix:id});
    selections.set(id,bindChart(el,points,{label,unit,nf,selection}));
    if(focus)el.querySelector(focus.startsWith('[')?focus:'#'+focus)?.focus({preventScroll:true});
    el.insertAdjacentHTML('beforeend',`<p class="meta">${points.length} observations${points.length?' · '+points[0][0]+'–'+points.at(-1)[0]:''}. Hover, tap or use the observation slider.</p>`);
  }
}
