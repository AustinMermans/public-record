// A target-quarter reading across distinct public information sets, not consensus.
import {spfResults} from './spf.mjs';
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const quarter = value => /^20\d{2}Q[1-4]$/.test(value || '') ? value : '';
const label = value => quarter(value) ? `${value.slice(0,4)} Q${value.slice(-1)}` : '';
const date = value => /^20\d{2}-\d{2}-\d{2}$/.test(value || '') && !Number.isNaN(Date.parse(value+'T12:00:00Z')) && new Date(value+'T12:00:00Z').toISOString().slice(0,10)===value ? value : '';
const capture = value => /^20\d{2}-\d{2}-\d{2}T/.test(value || '') && !Number.isNaN(Date.parse(value)) ? value : '';
const days = (later,earlier) => Math.round((Date.parse(later+'T12:00:00Z')-Date.parse(earlier+'T12:00:00Z'))/86400000);
const source = (url,host,text) => typeof url==='string' && url.startsWith(`https://${host}/`) ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)} ↗</a>` : 'Source unavailable';
const fixed = (value,places) => Number(value).toFixed(places);
const shortDate = value => new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(new Date((value||'').slice(0,10)+'T12:00:00Z'));

export function gdpWatchState(data,{target,asOf}={}) {
  asOf=date(asOf)||new Date().toISOString().slice(0,10);
  const bea=data?.bea_releases,spf=data?.spf,forecast=(data?.research?.forecasts||[]).filter(f=>f.id==='gdpnow');
  const model=forecast.length===1?forecast[0]:null;
  const modelTarget=/^(20\d{2}) Q([1-4])$/.exec(model?.target||'');
  const modelQuarter=modelTarget?`${modelTarget[1]}Q${modelTarget[2]}`:'';
  const modelValid=modelQuarter && ['ok','stale'].includes(model.status) && Number.isFinite(model.value) && Math.abs(model.value)<=50 && model.value===Number(model.value.toFixed(1)) && model.unit==='Percent · quarterly annualized' && date(model.published_at) && date(model.published_at)<=asOf && capture(model.captured_at) && model.captured_at.slice(0,10)>=model.published_at && model.url==='https://www.atlantafed.org/research-and-data/data/gdpnow';
  const spfSeries=spf?.series?.RGDP;
  const spfValid=['ok','stale'].includes(spf?.status) && spfSeries?.unit==='percent, quarter-over-quarter annualized growth' && spf?.sources?.medianGrowth?.url?.startsWith('https://www.philadelphiafed.org/') && capture(spf?.captured_at);
  const spfPoints=spfValid?(spfSeries.points||[]).filter(p=>quarter(p.target)&&quarter(p.survey)&&date(p.released)&&p.released<=asOf&&spf.captured_at.slice(0,10)>=p.released&&Number.isFinite(p.value)&&Math.abs(p.value)<=50&&/^RGDP![A-Z]+\d+$/.test(p.cell||'')):[];
  const beaReleases=(['ok','stale'].includes(bea?.status)?bea.releases||[]:[]).filter(r=>quarter(r.quarter)&&r.stage==='advance'&&r.unit==='percent'&&r.basis==='quarterly seasonally adjusted annual rate'&&Number.isFinite(r.value)&&/^-?\d+(?:\.\d+)?$/.test(r.display_value||'')&&Number(r.display_value)===r.value&&date(r.published_at)&&r.published_at<=asOf&&capture(r.captured_at)&&r.captured_at.slice(0,10)>=r.published_at&&/^https:\/\/www\.bea\.gov\/news\/20\d{2}\//.test(r.url||''));
  const latestSurvey=[...spfPoints].sort((a,b)=>b.released.localeCompare(a.released)||b.survey.localeCompare(a.survey))[0]?.survey;
  const currentTargets=spfPoints.filter(p=>p.survey===latestSurvey).map(p=>p.target);
  const options=[...new Set([...beaReleases.map(r=>r.quarter),...currentTargets,modelValid?modelQuarter:''])].filter(Boolean).sort().reverse();
  const selected=options.includes(target)?target:(modelValid&&options.includes(modelQuarter)?modelQuarter:options.find(q=>!beaReleases.some(r=>r.quarter===q))||options[0]||null);
  if(!selected)return {asOf,target:null,options:[],model:null,spf:null,bea:null,scheduled:null,contrast:null};
  const nowcast=modelValid&&modelQuarter===selected?{...model,target:selected,age:days(asOf,model.published_at),stale:model.status!=='ok'}:null;
  const survey=[...spfPoints].filter(p=>p.target===selected).sort((a,b)=>b.released.localeCompare(a.released)||b.survey.localeCompare(a.survey))[0];
  const surveyValue=survey?{...survey,age:days(asOf,survey.released),captured_at:spf.captured_at,status:spf.status,url:spf.sources.medianGrowth.url,stale:spf.status!=='ok'}:null;
  const published=beaReleases.find(r=>r.quarter===selected)||null;
  const planned=(bea?.scheduled||[]).find(r=>r.quarter===selected&&r.stage==='advance'&&date(r.date))||null;
  const current=nowcast&&surveyValue&&!published&&bea?.status==='ok'&&planned?.date>asOf&&!nowcast.stale&&!surveyValue.stale&&nowcast.age>=0&&nowcast.age<=14&&surveyValue.age>=0&&surveyValue.age<=100;
  return {asOf,target:selected,options,model:nowcast,spf:surveyValue,bea:published,beaStatus:bea?.status,scheduled:published?null:planned,contrast:current?nowcast.value-surveyValue.value:null};
}

function row(name,value,detail,meta,links,cls='') {
  return `<article class="gdp-watch-row ${cls}"><div class="section-no">${esc(name)}</div><div class="gdp-watch-number">${value===null?'—':esc(value)+'<small>%</small>'}</div><p>${esc(detail)}</p><div class="meta">${esc(meta)}${links?' · '+links:''}</div></article>`;
}

export function gdpWatchResults(data,options={}) {
  const state=gdpWatchState(data,options),{target,model,spf,bea,scheduled,contrast}=state;
  if(!target)return '<p class="empty">No same-target GDP evidence is available in this capture.</p>';
  const modelRow=model?row('Model nowcast',fixed(model.value,1),`GDPNow for ${label(target)} · quarterly annualized`,`${shortDate(model.published_at)} model update · retrieved ${shortDate(model.captured_at)}${model.stale?' · stale capture':''}${model.age>14?' · older than 14 days':''}`,source(model.url,'www.atlantafed.org','Atlanta Fed'),'model'):
    row('Model nowcast',null,`No retained GDPNow estimate for ${label(target)}. Historical model updates are not reconstructed.`, '', '', 'missing');
  const spfRow=spf?row('Survey-derived forecast',fixed(spf.value,2),`SPF real GDP growth for ${label(target)} · from median forecast levels`,`${label(spf.survey)} survey · released ${shortDate(spf.released)} · workbook retrieved ${shortDate(spf.captured_at)}${spf.stale?' · stale capture':''}${spf.age>100&&!bea?' · older than 100 days':''}`,source(spf.url,'www.philadelphiafed.org','Workbook')+` · <a href="#outlook?forecast=spf&amp;metric=RGDP&amp;target=${target}">Target history →</a>`,'survey'):
    row('Survey-derived forecast',null,`No verified SPF RGDP value for ${label(target)}.`, '', '', 'missing');
  const beaRow=bea?row('First official estimate',bea.display_value,`BEA advance estimate for ${label(target)} · later stages may differ`,`${shortDate(bea.published_at)} publication · retrieved ${shortDate(bea.captured_at)}${state.beaStatus!=='ok'?' · retained from stale capture':''}`,source(bea.url,'www.bea.gov','BEA release')+` · <a href="#gdp-releases?quarter=${target}">Release stages →</a>`,'actual'):
    row('First official estimate',null,scheduled?`BEA advance estimate scheduled ${scheduled.date}; no published value verified.`:`No BEA advance release or official date verified for ${label(target)}.`,scheduled?`${scheduled.date>state.asOf?'Future calendar entry':'Scheduled date passed without a verified release'} · ${state.beaStatus||'unavailable'} capture`:`${state.beaStatus||'unavailable'} capture`,source(data?.bea_releases?.schedule?.url,'www.bea.gov','BEA schedule'),'pending');
  let reading='';
  if(contrast!==null){const direction=contrast>0?'above':'below',movement=contrast===0?'at the same numerical rate as':Math.abs(contrast)<0.05?`less than 0.1 percentage point ${direction}`:`about ${fixed(Math.abs(contrast),1)} percentage points ${direction}`;reading=`<p class="gdp-watch-reading"><strong>Dated contrast:</strong> GDPNow (${esc(model.published_at)}) is ${movement} the SPF-derived estimate (${esc(spf.released)}) for ${label(target)}. These are different methods and information dates, not a release surprise or simultaneous consensus.</p>`;}
  else if(model&&spf&&!bea)reading='<p class="meta">A current numerical contrast is withheld until both forecasts are recent and the official advance release is still ahead on a verified BEA schedule.</p>';
  const clock=[model?`GDPNow retrieved ${esc(model.captured_at)}`:'',spf?`SPF workbook retrieved ${esc(spf.captured_at)} · cell ${esc(spf.cell)}`:'',bea?`BEA release retrieved ${esc(bea.captured_at)}`:''].filter(Boolean).join(' · ');
  return `<div class="gdp-watch-target"><strong>${label(target)} · real GDP growth</strong><span>Quarter-over-quarter annualized rates; one target, three distinct information sets.</span></div><div class="gdp-watch-grid">${spfRow}${modelRow}${beaRow}</div>${reading}<p class="meta gdp-watch-method">SPF real GDP growth is calculated from median forecast GDP levels, not a median of individual growth forecasts. Its historical cells come from the workbook edition retrieved now, not preserved original survey files. GDPNow is a model estimate, not an official Atlanta Fed forecast. No forecast-error or market-surprise claim is made.</p>${clock?`<details class="gdp-watch-evidence"><summary>Exact capture clocks</summary><p class="meta">${clock}</p></details>`:''}`;
}

export function gdpWatchPanel(data,options={}) {
  const state=gdpWatchState(data,options);
  return `<section class="section gdp-watch" id="forecast-gdp-watch"><div class="section-head"><h2>One-quarter GDP watch</h2><a href="https://www.bea.gov/news/schedule/full" target="_blank" rel="noopener noreferrer">BEA schedule ↗</a></div>${state.target?`<div class="filters"><label>Target quarter<select id="gdp-watch-quarter" aria-controls="gdp-watch-results">${state.options.map(q=>`<option value="${q}"${q===state.target?' selected':''}>${label(q)}</option>`).join('')}</select></label></div>`:''}<span class="sr-only" id="gdp-watch-announcement" role="status" aria-live="polite" aria-atomic="true"></span><div id="gdp-watch-results">${gdpWatchResults(data,{target:state.target,asOf:state.asOf})}</div></section>`;
}

export function gdpWatchAnnouncement(state) {
  if(!state.target)return 'No same-target GDP evidence is available.';
  return `${label(state.target)} selected. GDPNow ${state.model?fixed(state.model.value,1)+' percent':'unavailable'}. SPF ${state.spf?fixed(state.spf.value,2)+' percent':'unavailable'}. BEA advance ${state.bea?state.bea.display_value+' percent':'not yet verified'}.`;
}

export function bindGDPWatch(root,data) {
  const select=root.querySelector('#gdp-watch-quarter'),results=root.querySelector('#gdp-watch-results');
  if(!select||!results)return;
  select.addEventListener('change',event=>{event.stopPropagation();results.innerHTML=gdpWatchResults(data,{target:select.value});const announcement=root.querySelector('#gdp-watch-announcement');if(announcement)announcement.textContent=gdpWatchAnnouncement(gdpWatchState(data,{target:select.value}));const spfTarget=root.querySelector('#spf-target'),spfMetric=root.querySelector('#spf-metric');if(spfMetric?.value==='RGDP'&&[...(spfTarget?.options||[])].some(o=>o.value===select.value)){spfTarget.value=select.value;root.querySelector('#spf-results').innerHTML=spfResults(data.spf,{metric:'RGDP',target:select.value});}history.replaceState(null,'','#outlook?forecast=gdp-watch&quarter='+encodeURIComponent(select.value));select.focus({preventScroll:true});});
}

export function gdpWatchTeaser(data,options={}) {
  const state=gdpWatchState(data,options);
  if(!state.target||state.contrast===null)return '';
  const link='#outlook?forecast=gdp-watch&quarter='+state.target;
  return `<article class="gdp-watch-teaser"><div class="section-no">Outlook / ${label(state.target)}</div><h2><a href="${link}">One-quarter GDP watch →</a></h2><p><a href="${link}">GDPNow ${fixed(state.model.value,1)}% · ${esc(state.model.published_at)} versus SPF ${fixed(state.spf.value,2)}% · ${esc(state.spf.released)}</a></p><div class="meta">Different-date, different-method estimates for the same quarterly annualized target. ${source(state.model.url,'www.atlantafed.org','GDPNow')} · ${source(state.spf.url,'www.philadelphiafed.org','SPF workbook')}</div></article>`;
}
