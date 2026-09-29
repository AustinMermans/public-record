import {escapeText as esc} from './editorial.mjs';
import {sourceNotice} from './funding.mjs';

const FRONTS=['Economic data','Companies','Funding','Outlook','Disclosures','Calendar'];
const DOMAINS=FRONTS;
const COURT_SOURCES=new Set(['cand','cacd','nysd']);
const PAGE_SIZE=100;
const external=u=>typeof u==='string'&&/^https?:\/\//.test(u);
const internal=u=>typeof u==='string'&&/^#[a-z]/i.test(u);
const href=(u,t)=>external(u)?`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>`:internal(u)?`<a href="${esc(u)}">${esc(t)}</a>`:esc(t);
const itemsOf=d=>Array.isArray(d)?d:d?.changes?.items||d?.items||[];
const order=(a,b)=>String(b.to_capture||'').localeCompare(String(a.to_capture||''))||String(b.date||'').localeCompare(String(a.date||''))||String(a.title||'').localeCompare(String(b.title||''))||String(a.id||'').localeCompare(String(b.id||''));
const shown=v=>v!==undefined&&v!==null&&v!=='';
const print=v=>typeof v==='object'?JSON.stringify(v):String(v);
function value(v,unit){
  if(v===null||v===undefined)return 'Not present';
  if(typeof v==='string'&&['USD','USD millions','Percent','Count'].includes(unit)&&/^-?\d+(?:\.\d+)?$/.test(v)){const [whole,fraction]=v.split('.');return whole.replace(/\B(?=(\d{3})+(?!\d))/g,',')+(fraction===undefined?'':'.'+fraction)+(unit==='Percent'?'%':unit==='Count'?' institutions':' '+unit);}
  if(typeof v!=='number')return print(v);
  if(!Number.isFinite(v))return 'Unavailable';
  const n=new Intl.NumberFormat('en-US',{maximumFractionDigits:6}).format(v);
  return unit==='USD'?`${n} USD`:unit==='USD/shares'?`${n} USD / share`:unit==='Percent'||unit==='%'?`${n}%`:unit?`${n} ${unit}`:n;
}
const windowLabel=x=>`${x.from_capture||'No prior successful capture'} → ${x.to_capture||'Capture unavailable'}`;
function shortWindow(x){
  const from=new Date(x.from_capture||''),to=new Date(x.to_capture||'');
  if(!Number.isFinite(from.valueOf())||!Number.isFinite(to.valueOf()))return windowLabel(x);
  const opts={timeZone:'America/New_York'},dateFmt=new Intl.DateTimeFormat('en-US',{...opts,month:'short',day:'numeric'}),timeFmt=new Intl.DateTimeFormat('en-US',{...opts,hour:'numeric',minute:'2-digit'}),zoneFmt=new Intl.DateTimeFormat('en-US',{...opts,timeZoneName:'short'});
  const zone=d=>zoneFmt.formatToParts(d).find(p=>p.type==='timeZoneName')?.value||'ET';
  return dateFmt.format(from)===dateFmt.format(to)&&zone(from)===zone(to)?`${dateFmt.format(from)} · ${timeFmt.format(from)}–${timeFmt.format(to)} ${zone(to)}`:`${dateFmt.format(from)} ${timeFmt.format(from)} ${zone(from)} → ${dateFmt.format(to)} ${timeFmt.format(to)} ${zone(to)}`;
}
function periodLabel(x){
  const report=x.start&&x.date?`${x.start} → ${x.date}`:x.date||'';
  const target=x.target_period||x.forecast_period||x.target||x.period_label;
  return [x.form,report,target&&target!==report?`${x.source_id==='bea-gdp-releases'?'Target quarter':'Forecast / target'}: ${print(target)}`:'',x.report_period?`Report end ${x.report_period}`:'',x.filed?`Filed ${x.filed}`:'',x.accepted_at?`Accepted ${x.accepted_at}`:'',x.published_at?`Published ${x.published_at}`:'',x.previous_published_at?`Prior publication ${x.previous_published_at}`:''].filter(Boolean).join(' · ');
}
function changeValues(x){
  if(x.before===undefined&&x.after===undefined)return '<span class="meta">New or changed record metadata</span>';
  return `<span class="change-before">${shown(x.before)?href(x.before_url||x.previous_url||x.url,value(x.before,x.unit)):'Not present'}</span> → <span class="change-after">${shown(x.after)?href(x.after_url||x.url,value(x.after,x.unit)):'Not present'}</span>`;
}
function contextLink(x){return x.detail_url?href(x.detail_url,x.cik?'Company profile →':x.source_id==='bea-gdp-releases'?'GDP record →':x.domain==='Outlook'?'Forecast →':x.series_id?'Chart →':'Explore →'):'';}
function route(filters={},page=1){
  const p=new URLSearchParams();for(const k of ['company','domain','source','kind'])if(filters[k])p.set(k,filters[k]);if(page>1)p.set('page',String(page));
  return '#changes'+(p.size?'?'+p.toString():'');
}

export function filterChanges(data,filters={}){
  return itemsOf(data).filter(x=>(!filters.company||x.cik===filters.company)&&(!filters.domain||x.domain===filters.domain)&&(!filters.source||x.source_id===filters.source)&&(!filters.kind||x.kind===filters.kind)).sort(order);
}

function groups(items){
  const result=[],verified=new Map();
  for(const x of items.filter(x=>x.development_id||x.kind!=='Recalculated financial metric')){
    const key=x.development_id||(x.series_id&&JSON.stringify([x.series_id,x.source_id,x.kind,x.from_capture,x.to_capture]));
    const existing=key&&verified.get(key);
    if(existing){existing.items.push(x);continue;}
    const g={lead:x,items:[x]};result.push(g);if(key)verified.set(key,g);
  }
  for(const x of items.filter(x=>!x.development_id&&x.kind==='Recalculated financial metric')){
    const g=result.find(g=>g.lead.domain==='Companies'&&g.lead.cik&&g.lead.cik===x.cik&&g.lead.date===x.date&&g.lead.start===x.start&&g.lead.accession&&g.lead.accession===x.accession&&g.lead.from_capture===x.from_capture&&g.lead.to_capture===x.to_capture&&/financial/i.test(g.lead.kind));
    if(g)g.items.push(x);else result.push({lead:x,items:[x]});
  }
  return result.sort((a,b)=>order(a.lead,b.lead));
}
function noChanges(channels){
  const compared=channels.filter(c=>c.status==='compared').length,baseline=channels.filter(c=>c.status==='baseline').length,unavailable=channels.filter(c=>c.status==='unavailable').length;
  const rest=` ${baseline} baseline; ${unavailable} unavailable.`;
  return compared?`No comparable changes in ${compared} compared channel${compared===1?'':'s'}.${rest}`:`Not compared: no successful capture pair.${rest}`;
}
function story(g,domain){
  const x=g.lead;
  const related=g.items.length>1?`<details><summary>${g.items.length-1} related ledger ${g.items.length===2?'entry':'entries'}</summary><ul>${g.items.slice(1).map(y=>`<li>${esc(y.kind)} · ${esc(y.title)}: ${changeValues(y)}<div class="meta">${esc(periodLabel(y))}</div><div class="meta">${esc(windowLabel(y))} · ${href(y.url,'Source')}</div></li>`).join('')}</ul></details>`:'';
  return `<li><p><strong>${href(x.detail_url||x.url,x.title)}</strong></p><div class="meta">${esc(x.kind)}${periodLabel(x)?' · '+esc(periodLabel(x)):''}</div><p class="change-values">${changeValues(x)}</p>${x.summary?`<p class="meta">${esc(x.summary)}</p>`:''}${related}<div class="meta">${esc(windowLabel(x))}</div><p class="meta">${href(x.url,'Source')} · ${contextLink(x)||href(route({domain,source:x.source_id||'',company:x.cik||''}),'Ledger →')}</p></li>`;
}
function disclosureDesk(d,rows,channels){
  const official=rows.filter(x=>!COURT_SOURCES.has(x.source_id)),selected=groups(official).slice(0,3);
  const court=rows.filter(x=>COURT_SOURCES.has(x.source_id));
  const newly=court.filter(x=>x.kind==='Newly captured document').length,metadata=court.filter(x=>x.kind==='Record metadata changed').length,other=court.length-newly-metadata;
  const docketCount=new Set(court.filter(x=>external(x.url)).map(x=>x.source_id+'|'+x.url)).size;
  const courtSources=[...new Set(court.map(x=>x.source_id))].sort();
  const courtList=courtSources.map(id=>{
    const entries=court.filter(x=>x.source_id===id),distinct=new Set(entries.map(x=>x.url).filter(Boolean)).size;
    const source=d.sources?.find(s=>s.id===id),channel=channels.find(c=>c.id===id),label=channel?.label||source?.name||id;
    const comparison=channel||entries[0];
    return `<li><strong>${href(route({domain:'Disclosures',source:id}),label)}</strong><span>${entries.length} ledger ${entries.length===1?'entry':'entries'} · ${distinct} distinct docket ${distinct===1?'link':'links'}</span><span class="meta"><span title="${esc(windowLabel(comparison))}">${esc(shortWindow(comparison))}</span>${source?.url?' · '+href(source.url,'Court feed ↗'):''}</span></li>`;
  }).join('');
  return `<section class="change-desk change-desk-disclosures"><h3>${href(route({domain:'Disclosures'}),'Disclosures')}</h3>${selected.length?`<ol class="change-stories">${selected.map(g=>story(g,'Disclosures')).join('')}</ol><p class="meta">${official.length} non-court disclosure ledger ${official.length===1?'item':'items'}. ${href(route({domain:'Disclosures'}),'All disclosure changes →')}</p>`:''}${court.length?`<div class="court-change-summary"><h4>Court-feed activity</h4><p class="meta">${court.length} ledger ${court.length===1?'difference':'differences'}: ${newly} newly captured ${newly===1?'entry':'entries'}, ${metadata} metadata ${metadata===1?'change':'changes'}${other?`, ${other} other differences`:''}; ${docketCount} distinct docket ${docketCount===1?'link':'links'}. Newly observed in these partial rolling feeds, not all filings or rulings.</p><ul>${courtList}</ul><p class="meta">${href(route({domain:'Disclosures'}),'Browse the disclosure ledger →')}</p></div>`:''}</section>`;
}
function front(d,items){
  const channels=d.changes?.channels||[],active=FRONTS.filter(domain=>items.some(x=>x.domain===domain)),quiet=FRONTS.filter(domain=>!active.includes(domain));
  const desks=active.map(domain=>{
    const rows=items.filter(x=>x.domain===domain);
    if(domain==='Disclosures')return disclosureDesk(d,rows,channels);
    const allGroups=groups(rows),selected=allGroups.slice(0,3),represented=selected.reduce((n,g)=>n+g.items.length,0);
    return `<section class="change-desk"><h3>${href(route({domain}),domain)}</h3><ol class="change-stories">${selected.map(g=>story(g,domain)).join('')}</ol><p class="meta">Showing ${selected.length} of ${allGroups.length} developments · ${represented} of ${rows.length} ledger items. ${href(route({domain}),'All '+rows.length+' items →')}</p></section>`;
  }).join('');
  const quietSummary=quiet.length?`<details class="change-quiet"><summary>${quiet.length} other ${quiet.length===1?'desk':'desks'} without ledger entries · check comparison coverage</summary><ul>${quiet.map(domain=>`<li>${href(route({domain}),domain)} · ${esc(noChanges(channels.filter(c=>c.domain===domain)))}</li>`).join('')}</ul></details>`:'';
  return `<section class="section change-front" aria-label="Change edition"><div class="section-head"><h2>Since the prior successful captures</h2>${href('#changes','Complete change ledger →')}</div><details class="change-selection"><summary>Selection & comparison method</summary><p class="meta">Active desks first; latest capture, then latest affected period, then title; at most three selected developments per desk. Court-feed entries are counted by source and distinct docket link, not ranked as important cases. Same-filing entries, associated recalculations and same-series changes are grouped, not independent corroboration. Collection dates are not publication dates.</p></details>${active.length?`<div class="change-front-grid">${desks}</div>`:`<p class="meta">${esc(noChanges(channels))}</p>`}${quietSummary}</section>`;
}
function coverage(channels){
  const counts=['compared','baseline','unavailable'].map(s=>`${channels.filter(c=>c.status===s).length} ${s}`).join(' · ');
  return `<details class="section change-coverage"><summary>Comparison coverage · ${esc(counts)}</summary><p class="meta">Each channel uses its own previous successful capture. Baseline means no prior comparable capture; unavailable or stale channels are not evidence of no change. Feed disappearance is not treated as withdrawal.</p>${channels.length?`<ul>${channels.map(c=>`<li><strong>${esc(c.label||c.id)}</strong> · ${esc(c.domain)} · ${esc(c.status)}<div class="meta">${esc(windowLabel(c))}${(c.reason||c.error)?' · '+esc(c.reason||c.error):''}</div></li>`).join('')}</ul>`:'<p class="warning">Channel comparison coverage unavailable.</p>'}</details>`;
}
function filterForm(d,items,filters){
  const companies=new Map((d.financials?.companies||d.corporate?.companies||[]).map(c=>[c.cik,c.name]));
  for(const x of items)if(x.cik&&!companies.has(x.cik))companies.set(x.cik,x.company_name||x.company||x.cik);
  const options=(pairs,current)=>pairs.map(([v,label])=>`<option value="${esc(v)}"${v===current?' selected':''}>${esc(label)}</option>`).join('');
  const sourceNames=new Map((d.changes?.channels||[]).map(c=>[c.id,c.label||c.id]));
  return `<form class="filters change-filters" id="change-filters"><label for="change-company">Company<select id="change-company" name="company"><option value="">All companies & other records</option>${options([...companies].sort((a,b)=>a[1].localeCompare(b[1])),filters.company)}</select></label><label for="change-domain">Desk<select id="change-domain" name="domain"><option value="">All desks</option>${options(DOMAINS.map(v=>[v,v]),filters.domain)}</select></label><label for="change-source">Source<select id="change-source" name="source"><option value="">All sources</option>${options([...new Set(items.map(x=>x.source_id).filter(Boolean))].sort((a,b)=>(sourceNames.get(a)||a).localeCompare(sourceNames.get(b)||b)).map(id=>[id,sourceNames.get(id)||id]),filters.source)}</select></label><label for="change-kind">Change type<select id="change-kind" name="kind"><option value="">All change types</option>${options([...new Set(items.map(x=>x.kind))].sort().map(v=>[v,v]),filters.kind)}</select></label><a href="#changes">Reset filters</a></form>`;
}
export function changeEdition(d,{compact=false,filters={},page=1}={}){
  const c=d.changes||{},all=filterChanges(d),channels=c.channels||[];
  if(compact)return front(d,all);
  const matched=filterChanges(all,filters),pages=Math.max(1,Math.ceil(matched.length/PAGE_SIZE)),active=Math.min(pages,Math.max(1,Number.isFinite(Number(page))?Math.floor(Number(page)):1)),offset=(active-1)*PAGE_SIZE,visible=matched.slice(offset,offset+PAGE_SIZE);
  const hasFilters=['company','domain','source','kind'].some(k=>filters[k]);
  const companyName=(d.financials?.companies||d.corporate?.companies||[]).find(x=>x.cik===filters.company)?.name||all.find(x=>x.cik===filters.company)?.company_name||filters.company;
  const sourceName=channels.find(x=>x.id===filters.source)?.label||filters.source;
  const filterContext=[filters.domain,sourceName,filters.company?companyName:'',filters.kind].filter(Boolean).map(esc).join(' · ');
  const resultStatus=(filterContext?filterContext+' · ':'')+(matched.length?`Showing ${offset+1}–${offset+visible.length} of ${matched.length} matching items · ${all.length} total.`:hasFilters?'No items match these filters.':esc(noChanges(channels)));
  const navigation=`<nav class="pagination change-pagination" aria-label="Change ledger pages">${active>1?`<a href="${esc(route(filters,active-1))}" data-change-page="${active-1}">Previous</a>`:'<span aria-disabled="true">Previous</span>'}<span>Page ${active} of ${pages}</span>${active<pages?`<a href="${esc(route(filters,active+1))}" data-change-page="${active+1}">Next</a>`:'<span aria-disabled="true">Next</span>'}</nav>`;
  return `<div class="page-title"><div><div class="section-no">The change edition</div><h1>What changed?</h1><p>Observed differences between each channel’s successful captures.</p></div></div>${front(d,all)}${coverage(channels)}<section class="section change-ledger"><div class="section-head"><h2>Complete change ledger</h2><span class="meta">${all.length} items</span></div>${filterForm(d,all,filters)}<p class="meta" id="change-results-status" role="status">${resultStatus}</p>${visible.length?`${navigation}<div class="table-wrap" tabindex="0" role="region" aria-label="Change ledger"><table class="change-table"><thead><tr><th scope="col">Change / period</th><th scope="col">Before → after</th><th scope="col">Capture window / evidence</th></tr></thead><tbody>${visible.map(x=>`<tr id="change-${esc(x.id)}"><th scope="row"><div class="meta">${esc(x.domain)} · ${esc(x.kind)}</div>${esc(x.title)}${periodLabel(x)?`<div class="meta">${esc(periodLabel(x))}</div>`:''}${x.accession?`<div class="meta">Accession ${esc(x.accession)}</div>`:''}${x.summary?`<p class="meta">${esc(x.summary)}</p>`:''}</th><td data-label="Before → after" class="change-values">${changeValues(x)}${x.comparison_boundary?'<p class="warning">Comparison boundary; not a numerical revision.</p>':''}</td><td data-label="Capture window / evidence"><div class="meta">${esc(windowLabel(x))}</div><p>${href(x.url,'Source')}${x.previous_url&&x.previous_url!==x.url?' · '+href(x.previous_url,'Prior source'):''}</p>${contextLink(x)}</td></tr>`).join('')}</tbody></table></div>${navigation}`:''}</section>${(d.series||[]).filter(s=>s.source_id?.startsWith('nyfed-')&&all.some(x=>x.source_id===s.source_id)).map(sourceNotice).join('')}`;
}
