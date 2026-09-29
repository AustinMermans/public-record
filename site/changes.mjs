import {escapeText as esc} from './editorial.mjs';
import {sourceNotice} from './funding.mjs';

const FRONTS=['Economic data','Companies','Funding','Outlook'];
const DOMAINS=[...FRONTS,'Disclosures','Calendar'];
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
  if(typeof v==='string'&&unit==='USD'&&/^-?\d+(?:\.\d+)?$/.test(v)){const [whole,fraction]=v.split('.');return whole.replace(/\B(?=(\d{3})+(?!\d))/g,',')+(fraction===undefined?'':'.'+fraction)+' USD';}
  if(typeof v!=='number')return print(v);
  if(!Number.isFinite(v))return 'Unavailable';
  const n=new Intl.NumberFormat('en-US',{maximumFractionDigits:6}).format(v);
  return unit==='USD'?`${n} USD`:unit==='USD/shares'?`${n} USD / share`:unit==='Percent'||unit==='%'?`${n}%`:unit?`${n} ${unit}`:n;
}
const windowLabel=x=>`${x.from_capture||'No prior successful capture'} → ${x.to_capture||'Capture unavailable'}`;
function periodLabel(x){
  const report=x.start&&x.date?`${x.start} → ${x.date}`:x.date||'';
  const target=x.target_period||x.forecast_period||x.target||x.period_label;
  return [x.form,report,target&&target!==report?`Forecast / target: ${print(target)}`:'',x.report_period?`Report end ${x.report_period}`:'',x.filed?`Filed ${x.filed}`:'',x.accepted_at?`Accepted ${x.accepted_at}`:'',x.published_at?`Published ${x.published_at}`:'',x.previous_published_at?`Prior publication ${x.previous_published_at}`:''].filter(Boolean).join(' · ');
}
function changeValues(x){
  if(x.before===undefined&&x.after===undefined)return '<span class="meta">New or changed record metadata</span>';
  return `<span class="change-before">${shown(x.before)?href(x.before_url||x.previous_url||x.url,value(x.before,x.unit)):'Not present'}</span> → <span class="change-after">${shown(x.after)?href(x.after_url||x.url,value(x.after,x.unit)):'Not present'}</span>`;
}
function contextLink(x){return x.detail_url?href(x.detail_url,x.cik?'Company profile →':x.domain==='Outlook'?'Forecast →':x.series_id?'Chart →':'Explore →'):'';}
function route(filters={},page=1){
  const p=new URLSearchParams();for(const k of ['company','domain','kind'])if(filters[k])p.set(k,filters[k]);if(page>1)p.set('page',String(page));
  return '#changes'+(p.size?'?'+p.toString():'');
}

export function filterChanges(data,filters={}){
  return itemsOf(data).filter(x=>(!filters.company||x.cik===filters.company)&&(!filters.domain||x.domain===filters.domain)&&(!filters.kind||x.kind===filters.kind)).sort(order);
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
function front(d,items,compact){
  const channels=d.changes?.channels||[];
  return `<section class="section change-front" aria-label="Change edition"><div class="section-head"><h2>Since the prior successful captures</h2>${href('#changes','Complete change ledger →')}</div><details class="change-selection"><summary>Selection & comparison method</summary><p class="meta">Latest capture, then latest affected period, then title; at most three developments per desk. Same-filing entries, associated recalculations and same-series changes are grouped, not independent corroboration. Collection dates are not publication dates.</p></details><div class="change-front-grid">${FRONTS.map(domain=>{
    const rows=items.filter(x=>x.domain===domain),allGroups=groups(rows),selected=allGroups.slice(0,3),represented=selected.reduce((n,g)=>n+g.items.length,0);
    const cards=selected.map(g=>{
      const x=g.lead;
      const related=g.items.length>1?`<details><summary>${g.items.length-1} related ledger ${g.items.length===2?'entry':'entries'}</summary><ul>${g.items.slice(1).map(y=>`<li>${esc(y.kind)} · ${esc(y.title)}: ${changeValues(y)}<div class="meta">${esc(periodLabel(y))}</div><div class="meta">${esc(windowLabel(y))} · ${href(y.url,'Source')}</div></li>`).join('')}</ul></details>`:'';
      return `<li><p><strong>${href(x.detail_url||x.url,x.title)}</strong></p><div class="meta">${esc(x.kind)}${periodLabel(x)?' · '+esc(periodLabel(x)):''}</div><p class="change-values">${changeValues(x)}</p>${x.summary?`<p class="meta">${esc(x.summary)}</p>`:''}${related}<div class="meta">${esc(windowLabel(x))}</div><p class="meta">${href(x.url,'Source')} · ${contextLink(x)||href(route({domain,company:x.cik||''}),'Ledger →')}</p></li>`;
    }).join('');
    return `<section class="change-desk"><h3>${href(route({domain}),domain)}</h3>${selected.length?`<ol class="change-stories">${cards}</ol><p class="meta">Showing ${selected.length} of ${allGroups.length} developments · ${represented} of ${rows.length} ledger items. ${href(route({domain}),'All '+rows.length+' items →')}</p>`:`<p class="meta">${esc(noChanges(channels.filter(c=>c.domain===domain)))}</p>`}</section>`;
  }).join('')}</div>${compact?`<p class="meta">${items.filter(x=>!FRONTS.includes(x.domain)).length} additional disclosure / calendar differences are in the ${href('#changes','complete ledger')}.</p>`:''}</section>`;
}
function coverage(channels){
  const counts=['compared','baseline','unavailable'].map(s=>`${channels.filter(c=>c.status===s).length} ${s}`).join(' · ');
  return `<details class="section change-coverage"><summary>Comparison coverage · ${esc(counts)}</summary><p class="meta">Each channel uses its own previous successful capture. Baseline means no prior comparable capture; unavailable or stale channels are not evidence of no change. Feed disappearance is not treated as withdrawal.</p>${channels.length?`<ul>${channels.map(c=>`<li><strong>${esc(c.label||c.id)}</strong> · ${esc(c.domain)} · ${esc(c.status)}<div class="meta">${esc(windowLabel(c))}${(c.reason||c.error)?' · '+esc(c.reason||c.error):''}</div></li>`).join('')}</ul>`:'<p class="warning">Channel comparison coverage unavailable.</p>'}</details>`;
}
function filterForm(d,items,filters){
  const companies=new Map((d.financials?.companies||d.corporate?.companies||[]).map(c=>[c.cik,c.name]));
  for(const x of items)if(x.cik&&!companies.has(x.cik))companies.set(x.cik,x.company_name||x.company||x.cik);
  const options=(pairs,current)=>pairs.map(([v,label])=>`<option value="${esc(v)}"${v===current?' selected':''}>${esc(label)}</option>`).join('');
  return `<form class="filters change-filters" id="change-filters"><label for="change-company">Company<select id="change-company" name="company"><option value="">All companies & other records</option>${options([...companies].sort((a,b)=>a[1].localeCompare(b[1])),filters.company)}</select></label><label for="change-domain">Desk<select id="change-domain" name="domain"><option value="">All desks</option>${options(DOMAINS.map(v=>[v,v]),filters.domain)}</select></label><label for="change-kind">Change type<select id="change-kind" name="kind"><option value="">All change types</option>${options([...new Set(items.map(x=>x.kind))].sort().map(v=>[v,v]),filters.kind)}</select></label><a href="#changes">Reset filters</a></form>`;
}
export function changeEdition(d,{compact=false,filters={},page=1}={}){
  const c=d.changes||{},all=filterChanges(d),channels=c.channels||[];
  if(compact)return front(d,all,true);
  const matched=filterChanges(all,filters),pages=Math.max(1,Math.ceil(matched.length/PAGE_SIZE)),active=Math.min(pages,Math.max(1,Number.isFinite(Number(page))?Math.floor(Number(page)):1)),offset=(active-1)*PAGE_SIZE,visible=matched.slice(offset,offset+PAGE_SIZE);
  const hasFilters=['company','domain','kind'].some(k=>filters[k]);
  const navigation=`<nav class="pagination change-pagination" aria-label="Change ledger pages">${active>1?`<a href="${esc(route(filters,active-1))}" data-change-page="${active-1}">Previous</a>`:'<span aria-disabled="true">Previous</span>'}<span>Page ${active} of ${pages}</span>${active<pages?`<a href="${esc(route(filters,active+1))}" data-change-page="${active+1}">Next</a>`:'<span aria-disabled="true">Next</span>'}</nav>`;
  return `<div class="page-title"><div><div class="section-no">The change edition</div><h1>What changed?</h1><p>Observed differences between each channel’s successful captures.</p></div></div>${front(d,all,false)}${coverage(channels)}<section class="section change-ledger"><div class="section-head"><h2>Complete change ledger</h2><span class="meta">${all.length} items</span></div>${filterForm(d,all,filters)}<p class="meta" id="change-results-status" role="status">${matched.length?`Showing ${offset+1}–${offset+visible.length} of ${matched.length} matching items · ${all.length} total.`:hasFilters?'No items match these filters.':esc(noChanges(channels))}</p>${visible.length?`${navigation}<div class="table-wrap" tabindex="0" role="region" aria-label="Change ledger"><table class="change-table"><thead><tr><th scope="col">Change / period</th><th scope="col">Before → after</th><th scope="col">Capture window / evidence</th></tr></thead><tbody>${visible.map(x=>`<tr id="change-${esc(x.id)}"><th scope="row"><div class="meta">${esc(x.domain)} · ${esc(x.kind)}</div>${esc(x.title)}${periodLabel(x)?`<div class="meta">${esc(periodLabel(x))}</div>`:''}${x.accession?`<div class="meta">Accession ${esc(x.accession)}</div>`:''}${x.summary?`<p class="meta">${esc(x.summary)}</p>`:''}</th><td data-label="Before → after" class="change-values">${changeValues(x)}${x.comparison_boundary?'<p class="warning">Comparison boundary; not a numerical revision.</p>':''}</td><td data-label="Capture window / evidence"><div class="meta">${esc(windowLabel(x))}</div><p>${href(x.url,'Source')}${x.previous_url&&x.previous_url!==x.url?' · '+href(x.previous_url,'Prior source'):''}</p>${contextLink(x)}</td></tr>`).join('')}</tbody></table></div>${navigation}`:''}</section>${(d.series||[]).filter(s=>s.source_id?.startsWith('nyfed-')&&all.some(x=>x.source_id===s.source_id)).map(sourceNotice).join('')}`;
}
