import {escapeText as esc} from './editorial.mjs';
import {chartMarkup,bindChart} from './chart.mjs';

const primaryIds=['noncurrent','nco','coverage','roa','equity_assets','deposits'];
const ids=[...primaryIds,'institutions','assets','net_income'];
const labels={noncurrent:'Noncurrent loans / loans',nco:'Net charge-off rate',coverage:'Allowance / noncurrent loans',roa:'Return on assets',equity_assets:'Bank equity / assets',deposits:'Deposits',institutions:'Reporting institutions',assets:'Total assets',net_income:'Quarterly bank-attributable net income'};
const numeric=v=>typeof v==='string'&&/^-?\d+(?:\.\d+)?$/.test(v)&&Number.isFinite(Number(v));
const safe=u=>typeof u==='string'&&/^https?:\/\//.test(u);
const link=(u,t)=>safe(u)?`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>`:esc(t);
const route=id=>'#funding?view=banking&metric='+encodeURIComponent(id);
const nf=(v,n=2)=>Number(v).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n});
const valid=b=>b&&['ok','stale','partial'].includes(b.status)&&b.validation?.status==='reconciled';
const find=(b,id)=>[...(b?.metrics||[]),...(b?.context||[])].find(m=>m.id===id);
const expectedUnit=id=>id==='deposits'||id==='assets'||id==='net_income'?'USD millions':id==='institutions'?'Count':'Percent';
const supported=m=>m&&m.frequency==='Quarterly'&&m.unit===expectedUnit(m.id)&&(!['nco','roa'].includes(m.id)||m.annualized===true);
const iso=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s))&&new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
const quarter=s=>iso(s)&&['03-31','06-30','09-30','12-31'].includes(s.slice(5));
function shiftQuarter(date,n){
  if(!quarter(date))return null;
  const d=new Date(date+'T00:00:00Z');return new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1+n*3,0)).toISOString().slice(0,10);
}
const point=(m,p,date)=>supported(m)&&p&&p.date===date&&quarter(date)&&numeric(p.value)&&safe(p.url)?p:null;
function warning(b,now){
  if(!valid(b))return 'Validated banking aggregates unavailable';
  if(b.status==='stale')return 'Stale · last successful FDIC capture';
  const age=now-Date.parse(b.last_success||b.captured_at);
  return [b.status==='partial'?'Partial banking coverage':'',!Number.isFinite(age)?'Capture time unavailable':age>36*3600000?'FDIC retrieval older than 36 hours':''].filter(Boolean).join(' · ');
}
const units=m=>m.unit==='USD millions'?'USD bn':m.unit==='Percent'?'%':'institutions';
const formatted=(m,v)=>m.unit==='USD millions'?nf(Number(v)/1000)+' USD bn':m.unit==='Percent'?nf(v)+'%':nf(v,0);
const basis=m=>m.annualized?'Quarterly · annualized':m.id==='net_income'?'Quarterly flow':'Quarter end';
function valueCell(m,p,date){
  const v=point(m,p,date);
  return v?`<a href="${route(m.id)}" class="metric-link" data-banking-metric="${esc(m.id)}" title="${esc(v.value+' '+m.unit+' · '+v.date)}">${esc(formatted(m,v.value))}</a><div class="meta">${link(v.url,'Source')} · ${esc(v.date)}</div>`:'<span class="meta">Unavailable</span>';
}
function direction(m,b){
  const current=point(m,m?.current,b.quarter_end),prior=point(m,m?.prior,shiftQuarter(b.quarter_end,-1));
  if(!current||!prior)return null;
  const delta=Number(current.value)-Number(prior.value);
  return delta>0?'rose':delta<0?'fell':'was unchanged';
}
function movements(b){
  const non=direction(find(b,'noncurrent'),b),nco=direction(find(b,'nco'),b),cov=direction(find(b,'coverage'),b),equity=direction(find(b,'equity_assets'),b);
  const primary=[non?'Noncurrent loan share '+non:'',nco?'the quarterly net charge-off rate '+nco:''].filter(Boolean).join(non&&nco&&non!==nco?' while ':' and ');
  const other=[cov?'Reserve coverage '+cov:'',equity?'bank equity/assets '+equity:''].filter(Boolean).join(' and ');
  return primary||other?`<p class="banking-summary">${esc(primary?primary+'.':'')}${other?' '+esc(other+'.'):''} <span class="meta">Versus the prior quarter.</span></p>`:'<p class="meta">Matched prior-quarter comparisons are unavailable.</p>';
}
function historyPoints(b,m){
  if(!supported(m))return [];
  return (m.observations||[]).filter(p=>quarter(p.date)&&p.date<=b.quarter_end).sort((a,b)=>a.date.localeCompare(b.date));
}
function reconciliationNotes(b,m){
  const notes=(b.quality_notes||[]).filter(n=>n.metric_id===m?.id||(m?.id==='assets'&&n.metric_id==='balance_sheet')||(m?.id==='net_income'&&n.metric_id==='income_bridge'));
  const publishedLabel=m?.id==='net_income'?'Published inclusive income':'Published',calculationLabel=m?.id==='assets'?'Liabilities + inclusive equity':m?.id==='net_income'?'Bank income + noncontrolling interests':'Component calculation';
  return `${b.coverage?.note?`<p class="meta banking-reconciliation-note">${esc(b.coverage.note)}</p>`:''}${notes.length?`<p class="meta warning">${notes.length} historical quarter${notes.length===1?'':'s'} differ from component reconstruction. Published values are retained; current comparison checks do not establish uniform historical reconciliation.</p><details class="banking-quality"><summary>Historical reconciliation exceptions · ${notes.length}</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Historical banking reconciliation exceptions"><table class="banking-table"><thead><tr><th scope="col">Quarter / note</th><th scope="col">${esc(publishedLabel)}</th><th scope="col">${esc(calculationLabel)}</th><th scope="col">Residual</th></tr></thead><tbody>${notes.map(n=>`<tr><th scope="row">${esc(n.date)}<div class="meta">${esc(n.note)}</div></th><td data-label="${esc(publishedLabel)}">${esc(n.published)} ${esc(n.unit||m?.unit)}</td><td data-label="${esc(calculationLabel)}">${esc(n.calculated)} ${esc(n.unit||m?.unit)}</td><td data-label="Residual">${esc(n.residual)} ${(n.unit||m?.unit)==='Percent'?'percentage points':esc(n.unit||m?.unit)}</td></tr>`).join('')}</tbody></table></div></details>`:''}`;
}
function historyMarkup(b,id,now){
  const m=find(b,id),rows=historyPoints(b,m),warn=warning(b,now);
  return `<section class="section banking-history" id="banking-history"><div class="section-head"><h3>${esc(labels[id])}</h3><span class="meta">${supported(m)?esc(basis(m)):'Measure unavailable'}</span></div><div class="filters"><label for="banking-metric">History measure<select id="banking-metric">${ids.map(k=>`<option value="${k}"${k===id?' selected':''}>${esc(labels[k])}</option>`).join('')}</select></label></div>${warn?`<p class="warning">${esc(warn)}</p>`:''}<p class="meta">${esc(m?.definition||'Definition unavailable')}${supported(m)?' · '+esc(units(m)):''}</p>${rows.some(p=>numeric(p.value)&&safe(p.url))?'<div id="banking-history-chart" class="chart-container"></div>':'<p class="meta">No validated history is available for this measure.</p>'}<p class="meta">${rows.filter(p=>numeric(p.value)&&safe(p.url)).length} observed quarters · ${rows.filter(p=>!numeric(p.value)||!safe(p.url)).length} unavailable quarters${rows.length?' · '+esc(rows[0].date)+' → '+esc(rows.at(-1).date):''} · QBP edition ${esc(b.edition)}</p>${reconciliationNotes(b,m)}<details><summary>Historical values & source cells</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Banking historical values"><table class="banking-table"><thead><tr><th scope="col">Quarter end</th><th scope="col">${esc(labels[id])}${supported(m)?', '+esc(units(m)):''}</th><th scope="col">Workbook source</th></tr></thead><tbody>${rows.map(p=>`<tr><th scope="row">${esc(p.date)}</th><td data-label="Value">${numeric(p.value)&&safe(p.url)?esc(formatted(m,p.value)):'Unavailable'+(p.missing_reason?' · '+esc(p.missing_reason):'')}</td><td data-label="Source">${link(p.url,(m.sheet||'Workbook')+' · '+(p.cell||'cell unavailable'))}</td></tr>`).join('')}</tbody></table></div></details></section>`;
}
export function bankingPanel(d,{metric='noncurrent',now=Date.now()}={}){
  const b=d.banking||{},id=ids.includes(metric)?metric:'noncurrent',warn=warning(b,now),current=b.quarter_end,prior=shiftQuarter(current,-1),yearAgo=shiftQuarter(current,-4);
  return `<section class="section banking-panel" id="banking-panel" data-metric="${id}"><div class="section-head"><h2>Banking conditions</h2><span class="meta">FDIC-reported institution aggregates</span></div>${warn?`<p class="warning">${esc(warn)}${b.error?' · '+esc(b.error):''}</p>`:''}${valid(b)?`<p class="meta">Quarter ended ${esc(current)} · QBP edition ${esc(b.edition)}<br>Last successful capture ${esc(b.last_success||b.captured_at||'unavailable')}${b.status==='stale'&&b.attempted_at?' · Last attempt '+esc(b.attempted_at):''}</p>${movements(b)}<div class="banking-context">${(b.context||[]).filter(m=>point(m,m.current,current)).map(m=>`<p><span class="meta">${esc(m.id==='net_income'?labels.net_income:m.label)}${m.id==='assets'?' · quarter end':''}</span><br><strong><a class="metric-link" href="${route(m.id)}" data-banking-metric="${esc(m.id)}">${esc(formatted(m,m.current.value))}</a></strong><br><span class="meta">${link(m.current.url,'Source')}</span></p>`).join('')}</div><div class="table-wrap" tabindex="0" role="region" aria-label="Banking conditions comparison"><table class="banking-table"><thead><tr><th scope="col">Measure</th><th scope="col">Current · ${esc(current)}</th><th scope="col">Prior quarter · ${esc(prior)}</th><th scope="col">Year ago · ${esc(yearAgo)}</th></tr></thead><tbody>${primaryIds.map(k=>{const m=find(b,k);return `<tr><th scope="row">${esc(labels[k])}<div class="meta">${supported(m)?esc(basis(m)+' · '+units(m)):'Basis unavailable'}</div></th><td data-label="Current">${valueCell(m,m?.current,current)}</td><td data-label="Prior quarter">${valueCell(m,m?.prior,prior)}</td><td data-label="Year ago">${valueCell(m,m?.year_ago,yearAgo)}</td></tr>`;}).join('')}</tbody></table></div>${historyMarkup(b,id,now)}<details class="section banking-method"><summary>Population, method & sources</summary><p class="meta">${esc(b.population||'FDIC-insured commercial banks and savings institutions')}. FDIC-reported aggregates may include parent and subsidiary institution reports without a double-counting adjustment; these are not SEC bank-holding-company totals or a fixed cohort of banks.</p><p class="meta">Published aggregate ratios, not unweighted institution averages. Quarterly net charge-off and return-on-assets ratios are annualized as published, with average-period denominators; they are not annual-income observations. Noncurrent loans are 90+ days past due plus nonaccrual. Bank equity and net income exclude noncontrolling interests. Regulatory capital ratios are not shown.</p><p class="meta">Latest-edition history may be revised; original-release vintages are not reconstructed. A daily collection check is not a new quarterly observation. No composite score or policy-causal interpretation is supplied.</p>${b.url?`<p class="meta">${link(b.url,'FDIC QBP workbook')}${b.notes_url?' · '+link(b.notes_url,'FDIC notes to users'):''}</p>`:''}${b.attribution?`<p class="meta">${esc(b.attribution)}${b.terms_url?' · '+link(b.terms_url,'Source terms'):''}</p>`:''}</details>`:'<p class="empty-day">No validated banking measures are available. Values are not substituted.</p>'}</section>`;
}
export function bankingTeaser(d,{now=Date.now()}={}){
  const b=d.banking,m=find(b,'noncurrent'),p=valid(b)?point(m,m?.current,b.quarter_end):null,warn=warning(b,now);
  return `<section class="section banking-teaser"><h3><a href="${route('noncurrent')}">Banking conditions →</a></h3>${p?`<p><a class="metric-link" href="${route('noncurrent')}">${esc(formatted(m,p.value))}</a> noncurrent loans / loans</p><p class="meta">Quarter ended ${esc(p.date)} · FDIC-reported aggregates</p>`:'<p class="meta">Validated banking aggregates unavailable.</p>'}${warn?`<p class="warning">${esc(warn)}</p>`:''}</section>`;
}

const selections=new Map();
export function bindBanking(root,d,preserve=false){
  const panel=root.querySelector('#banking-panel'),b=d.banking;if(!panel||!valid(b))return;
  const select=panel.querySelector('#banking-metric');
  function changeMetric(id,focusSelect){
    if(!ids.includes(id))return;
    const x=window.scrollX,y=window.scrollY;panel.dataset.metric=id;history.replaceState(null,'',route(id));
    panel.querySelector('#banking-history').outerHTML=historyMarkup(b,id,Date.now());bindBanking(root,d);
    const target=panel.querySelector(focusSelect?'#banking-metric':'#banking-history');if(!focusSelect)target.tabIndex=-1;target.focus({preventScroll:true});
    if(focusSelect)window.scrollTo(x,y);else target.scrollIntoView({block:'start'});
  }
  if(select&&!select.dataset.bound){select.dataset.bound='true';select.addEventListener('change',e=>{e.stopPropagation();changeMetric(select.value,true);});}
  if(!panel.dataset.bound){panel.dataset.bound='true';panel.addEventListener('click',e=>{const a=e.target.closest('[data-banking-metric]');if(!a||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||e.button!==0)return;e.preventDefault();e.stopPropagation();changeMetric(a.dataset.bankingMetric,false);});}
  const id=panel.dataset.metric,m=find(b,id),rows=historyPoints(b,m),el=panel.querySelector('#banking-history-chart');if(!el)return;
  const points=rows.filter(p=>numeric(p.value)&&safe(p.url)).map(p=>[p.date,Number(p.value)/(m.unit==='USD millions'?1000:1)]),width=Math.max(260,Math.round(el.clientWidth||700));
  if(preserve&&el.querySelector('svg.chart')?.viewBox.baseVal.width===width)return;
  const selection=preserve?selections.get(id)?.():null,active=document.activeElement,focus=el.contains(active)?active.id||(active.dataset.chartStep?'[data-chart-step="'+active.dataset.chartStep+'"]':null):null;
  const format=(value,digits=2)=>nf(value,m.unit==='Count'?0:digits);
  el.innerHTML=chartMarkup(points,{width,label:labels[id]+' · '+basis(m),unit:units(m),esc,nf:format,tick:date=>date.slice(0,4)+' Q'+Math.ceil(Number(date.slice(5,7))/3),idPrefix:'banking-history',connect:(a,b)=>shiftQuarter(a[0],1)===b[0]});
  selections.set(id,bindChart(el,points,{label:date=>date,unit:units(m),nf:format,selection}));
  if(focus)el.querySelector(focus.startsWith('[')?focus:'#'+focus)?.focus({preventScroll:true});
}
