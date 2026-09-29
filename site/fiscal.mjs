import {escapeText as esc} from './editorial.mjs';
import {chartMarkup,bindChart} from './chart.mjs';

const labels={receipts:'Receipts',outlays:'Total outlays',net_interest:'Net interest',balance:'Surplus / deficit'};
const monthlyIds=['balance','receipts','outlays'];
const monetary=v=>typeof v==='string'&&/^-?\d+(?:\.\d+)?$/.test(v)&&Number.isFinite(Number(v));
const safe=u=>typeof u==='string'&&/^https?:\/\//.test(u);
const external=(u,t)=>safe(u)?`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>`:esc(t);
const nf=(v,n=2)=>Number(v).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n});
const span=p=>p?.start&&p?.end?`${p.start} → ${p.end}`:'Period unavailable';
const available=f=>f&&['ok','stale','partial'].includes(f.status)&&f.validation?.status==='reconciled';
const metric=(f,id)=>(f?.metrics||[]).find(x=>x.id===id&&x.unit==='USD');
const warning=(f,now=Date.now())=>{
  if(!available(f))return 'Fiscal data unavailable';
  if(f.status==='stale')return 'Stale · last successful fiscal capture';
  const age=now-Date.parse(f.captured_at),retrieval=!Number.isFinite(age)?'Capture time unavailable':age>36*3600000?'Retrieval older than 36 hours':'';
  return [f.status==='partial'?'Partial fiscal coverage':'',retrieval].filter(Boolean).join(' · ');
};
const route=(view,metric='balance')=>'#fiscal?view='+view+'&metric='+metric;
const isoDate=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s))&&new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
const matched=f=>{
  const a=f.periods?.current_fytd,b=f.periods?.prior_fytd;
  return a&&b&&/^\d{4}-10-01$/.test(a.start||'')&&/^\d{4}-10-01$/.test(b.start||'')&&Number(a.start.slice(0,4))-Number(b.start.slice(0,4))===1&&isoDate(a.end)&&isoDate(b.end)&&Number(a.end.slice(0,4))-Number(b.end.slice(0,4))===1&&a.end.slice(5,7)===b.end.slice(5,7);
};
function amount(v,{balance=false,signed=false}={}){
  if(!monetary(v))return 'Unavailable';
  const n=Number(v),text=nf((balance?Math.abs(n):n)/1e9,2)+' USD bn';
  return balance?text+(n<0?' deficit':n>0?' surplus':' balanced'):(signed&&n>0?'+':'')+text;
}
function numberLink(v,url,options={}){
  if(!monetary(v))return '<span class="meta">Unavailable</span>';
  if(!safe(url))return '<span class="meta">Source link unavailable</span>';
  return `<span title="${esc(v)} USD">${external(url,amount(v,options))}</span>`;
}
// Exact decimal subtraction for display; reconciliation belongs to the collector.
function difference(a,b){
  if(!monetary(a)||!monetary(b))return null;
  const places=Math.max(a.split('.')[1]?.length||0,b.split('.')[1]?.length||0),scale=10n**BigInt(places);
  const integer=s=>{const neg=s.startsWith('-'),[whole,fraction='']=s.replace(/^-/,'').split('.');return (neg?-1n:1n)*(BigInt(whole)*scale+BigInt(fraction.padEnd(places,'0')||'0'));};
  const delta=integer(a)-integer(b),abs=delta<0n?-delta:delta,digits=abs.toString().padStart(places+1,'0');
  return (delta<0n?'-':'')+(places?digits.slice(0,-places)+'.'+digits.slice(-places):digits);
}
function freshness(f,now){
  return `${warning(f,now)?`<p class="warning">${esc(warning(f,now))}${f.error?' · '+esc(f.error):''}</p>`:''}<p class="meta">MTS edition ${esc(f?.edition||'unavailable')} · ${f?.status==='stale'?'Last successful capture':'Captured'} ${esc(f?.captured_at||'unavailable')}</p>`;
}
function sourceLine(f){return `<p class="meta">Source: ${external(f.url,'U.S. Treasury · Monthly Treasury Statement')}${f.attribution?' · '+esc(f.attribution):''}</p>`;}
function summary(f,now){
  const good=matched(f),rows=['receipts','outlays','net_interest','balance'].map(id=>metric(f,id)).filter(x=>x&&monetary(x.current_fytd));
  return `<section class="section" id="fiscal-fytd"><div class="section-head"><h2>Fiscal year to date</h2><span class="meta">Actual amounts · USD billions</span></div><p class="meta">Current ${esc(span(f.periods?.current_fytd))}<br>Prior ${esc(span(f.periods?.prior_fytd))}</p>${!good?'<p class="warning">Matched prior fiscal period unavailable; comparisons suppressed.</p>':''}<div class="kpis fiscal-kpis">${rows.map(x=>`<div class="kpi"><div class="kpi-label">${esc(x.id==='balance'?(Number(x.current_fytd)<0?'Deficit':Number(x.current_fytd)>0?'Surplus':'Balanced budget'):labels[x.id])}</div><div class="kpi-value">${numberLink(x.current_fytd,x.url,{balance:x.id==='balance'})}</div>${warning(f,now)?`<p class="meta warning">${esc(warning(f,now))}</p>`:''}</div>`).join('')}</div><div class="table-wrap" tabindex="0" role="region" aria-label="Fiscal year-to-date comparison"><table class="fiscal-table"><thead><tr><th scope="col">Measure</th><th scope="col">Current FYTD</th><th scope="col">Prior FYTD</th><th scope="col">Change</th></tr></thead><tbody>${rows.map(x=>`<tr><th scope="row">${esc(labels[x.id])}${x.id==='balance'?'<div class="meta">Positive balance = surplus; negative = deficit</div>':''}</th><td data-label="Current FYTD">${numberLink(x.current_fytd,x.url,{balance:x.id==='balance'})}</td><td data-label="Prior FYTD">${good?numberLink(x.prior_fytd,x.url,{balance:x.id==='balance'}):'Not comparable'}</td><td data-label="Change">${good?numberLink(difference(x.current_fytd,x.prior_fytd),x.url,{signed:true}):'Not comparable'}${x.id==='balance'?'<div class="meta">Change in signed balance</div>':''}</td></tr>`).join('')}</tbody></table></div>${sourceLine(f)}</section>`;
}
function accountingBridge(f){
  const b=f.bridge;
  if(!matched(f)||b?.status!=='reconciled'||b.unit!=='USD'||!['current_deficit','prior_deficit','deficit_change','net_interest_change','other_outlays_change','receipts_contribution'].every(k=>monetary(b[k])))return '<section class="section"><h2>What changed in the deficit?</h2><p class="warning">A reconciled accounting bridge is unavailable.</p></section>';
  const rows=[['Net interest',b.net_interest_change],['Other outlays',b.other_outlays_change],['Receipts (sign reversed)',b.receipts_contribution]],max=Math.max(...rows.map(([,v])=>Math.abs(Number(v))),1),x0=340,scale=110/max;
  const sources=Array.isArray(b.sources)?b.sources.map(s=>typeof s==='string'?s:s.url).filter(safe):Object.values(b.sources||{}).map(s=>typeof s==='string'?s:s.url).filter(safe);
  const source=metric(f,'balance')?.url||sources[0]||f.url,interestSource=metric(f,'net_interest')?.url||sources.find(u=>u.includes('mts_table_9'));
  const change=Number(b.deficit_change),bothDeficits=Number(b.current_deficit)>0&&Number(b.prior_deficit)>0;
  const direction=change===0?'The FYTD budget balance was unchanged from the same fiscal span a year earlier.':`${bothDeficits?'The FYTD deficit was':'The FYTD budget balance was'} ${amount(b.deficit_change.replace(/^-/,''))} ${bothDeficits?(change<0?'smaller':'larger'):(change<0?'stronger':'weaker')} than in the same fiscal span a year earlier.`;
  const graphic=`<p>${esc(direction)}</p><svg class="fiscal-bridge-chart" viewBox="0 0 660 160" aria-hidden="true" focusable="false"><line x1="${x0}" x2="${x0}" y1="10" y2="150" stroke="currentColor"/>${rows.map(([label,v],i)=>{const n=Number(v),w=Math.abs(n)*scale,y=18+i*46;return `<text x="0" y="${y+17}">${esc(label)}</text><rect class="${n<0?'fiscal-reducing':'fiscal-increasing'}" x="${n<0?x0-w:x0}" y="${y}" width="${w}" height="24"/><text x="470" y="${y+17}">${esc(amount(v,{signed:true}))}</text>`;}).join('')}</svg>`;
  return `<section class="section fiscal-bridge"><div class="section-head"><h2>What changed in the deficit?</h2><span class="meta">FYTD accounting contributions</span></div><p>Deficit change: <strong>${numberLink(b.deficit_change,source,{signed:true})}</strong>. Positive contributions increase the deficit; negative contributions reduce it.</p>${graphic}<div class="table-wrap" tabindex="0" role="region" aria-label="Deficit accounting bridge"><table class="fiscal-table"><thead><tr><th scope="col">Component</th><th scope="col">Contribution to deficit change</th></tr></thead><tbody>${rows.map(([label,v])=>`<tr><th scope="row">${esc(label)}</th><td data-label="Contribution">${numberLink(v,label==='Net interest'?interestSource:source,{signed:true})}</td></tr>`).join('')}<tr><th scope="row">Total deficit change</th><td data-label="Total">${numberLink(b.deficit_change,source,{signed:true})}</td></tr></tbody></table></div><p class="meta">Change in interest + change in other outlays − change in receipts. An accounting decomposition, not policy causality. Deficit is not the change in debt.</p></section>`;
}
const monthlyRows=(f,id)=>(f.monthly||[]).filter(r=>isoDate(r.date)&&monetary(r[id])&&safe(r.url)).sort((a,b)=>a.date.localeCompare(b.date));
function monthly(f,id,now){
  const rows=f.monthly_status==='ok'?monthlyRows(f,id):[];
  return `<section class="section" id="fiscal-monthly"><div class="section-head"><h2>Monthly ${esc(id==='balance'?'surplus / deficit':labels[id].toLowerCase())}</h2></div><div class="filters"><label for="fiscal-metric">Measure<select id="fiscal-metric">${monthlyIds.map(k=>`<option value="${k}"${k===id?' selected':''}>${esc(labels[k])}</option>`).join('')}</select></label></div><p class="meta" id="fiscal-monthly-basis">Monthly actuals · USD billions. Positive balance = surplus; negative = deficit.</p>${warning(f,now)?`<p class="warning">${esc(warning(f,now))}</p>`:''}${rows.length?'<div id="fiscal-monthly-chart" class="chart-container"></div>':'<p class="warning">Validated monthly history is unavailable for this measure.</p>'}<p class="meta">History ${esc(f.monthly_coverage?.start||'unavailable')} → ${esc(f.monthly_coverage?.end||'unavailable')} · Edition ${esc(f.monthly_coverage?.edition||f.edition)}${f.monthly_coverage?.note?' · '+esc(f.monthly_coverage.note):''}</p><details><summary>Monthly values & sources</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Monthly fiscal values"><table class="fiscal-table"><thead><tr><th scope="col">Month end</th><th scope="col">Fiscal year</th><th scope="col">${esc(labels[id])}, USD bn</th></tr></thead><tbody>${rows.map(r=>`<tr><th scope="row">${esc(r.date)}</th><td data-label="Fiscal year">${esc(r.fiscal_year)}</td><td data-label="Amount">${numberLink(r[id],r.url)}</td></tr>`).join('')}</tbody></table></div></details>${sourceLine(f)}</section>`;
}
export function fiscalPage(d,{view='fytd',metric:requested='balance',now=Date.now()}={}){
  const f=d.fiscal||{},id=monthlyIds.includes(requested)?requested:'balance',selected=view==='monthly'?'monthly':'fytd';
  return `<div class="page-title"><div><div class="section-no">Government · Federal finances</div><h1>Receipts, outlays & the deficit</h1></div></div><div id="fiscal-panel" data-view="${selected}" data-metric="${id}">${freshness(f,now)}${available(f)?`<div class="history-ranges fiscal-views" aria-label="Fiscal view"><a href="${route('fytd',id)}"${selected==='fytd'?' aria-current="page"':''}>Fiscal year to date</a><a href="${route('monthly',id)}"${selected==='monthly'?' aria-current="page"':''}>Monthly history</a></div>${selected==='monthly'?monthly(f,id,now):summary(f,now)+accountingBridge(f)}<details class="section"><summary>Method & source basis</summary><p class="meta">Treasury actual amounts, converted from USD to USD billions for display. Fiscal years begin October 1. FYTD comparisons use matched fiscal spans from one MTS edition, not accumulated monthly vintages. Modified-cash reporting includes accrued interest on the public debt; these are not pure cash-flow measures. Payment shifts limit single-month inference. Reporting period, MTS edition and capture time are distinct; a precise publication timestamp is not supplied.</p><p class="meta">Treasury source data may be reused commercially or noncommercially; Public Record’s license covers its original work. ${external('https://fiscaldata.treasury.gov/about-us/','Treasury source-data terms')}</p></details>`:'<p class="empty">No validated fiscal amounts are available. Values are not substituted.</p>'}</div>`;
}
export function fiscalTeaser(d,{now=Date.now()}={}){
  const f=d.fiscal,m=metric(f,'balance');
  if(!available(f)||!m||!monetary(m.current_fytd))return '<section class="section fiscal-teaser"><h3><a href="#fiscal">Federal finances →</a></h3><p class="meta">Validated fiscal data unavailable.</p></section>';
  return `<section class="section fiscal-teaser"><h3><a href="#fiscal">Federal finances →</a></h3><p><a class="metric-link" href="${route('fytd')}">${esc(amount(m.current_fytd,{balance:true}))}</a></p><p class="meta">FYTD ${esc(span(f.periods?.current_fytd))} · Edition ${esc(f.edition)}</p>${warning(f,now)?`<p class="warning">${esc(warning(f,now))}</p>`:''}</section>`;
}

const selections=new Map();
export function bindFiscal(root,d,preserve=false){
  const panel=root.querySelector('#fiscal-panel'),f=d.fiscal;
  if(!panel||panel.dataset.view!=='monthly'||!available(f)||f.monthly_status!=='ok')return;
  const select=panel.querySelector('#fiscal-metric');
  if(select&&!select.dataset.bound){select.dataset.bound='true';select.addEventListener('change',e=>{
    e.stopPropagation();const x=window.scrollX,y=window.scrollY,id=monthlyIds.includes(select.value)?select.value:'balance';panel.dataset.metric=id;
    const params=new URLSearchParams({view:'monthly',metric:id});history.replaceState(null,'','#fiscal?'+params);
    for(const a of panel.querySelectorAll('.fiscal-views a')){const view=new URLSearchParams(a.getAttribute('href').split('?')[1]).get('view');a.setAttribute('href',route(view,id));}
    panel.querySelector('#fiscal-monthly').outerHTML=monthly(f,id);bindFiscal(root,d);panel.querySelector('#fiscal-metric')?.focus({preventScroll:true});window.scrollTo(x,y);
  });}
  const id=panel.dataset.metric,el=panel.querySelector('#fiscal-monthly-chart');if(!el)return;
  const rows=monthlyRows(f,id),points=rows.map(r=>[r.date,Number(r[id])/1e9]),width=Math.max(260,Math.round(el.clientWidth||700));
  if(preserve&&el.querySelector('svg.chart')?.viewBox.baseVal.width===width)return;
  const selection=preserve?selections.get(id)?.():null,active=document.activeElement,focus=el.contains(active)?active.id||(active.dataset.chartStep?'[data-chart-step="'+active.dataset.chartStep+'"]':null):null;
  el.innerHTML=chartMarkup(points,{width,label:'Monthly '+labels[id],unit:'USD bn'+(id==='balance'?' · surplus positive / deficit negative':''),esc,nf,tick:date=>date.slice(0,7),idPrefix:'fiscal-monthly'});
  selections.set(id,bindChart(el,points,{label:date=>date,unit:'USD bn',nf,selection}));
  if(focus)el.querySelector(focus.startsWith('[')?focus:'#'+focus)?.focus({preventScroll:true});
}
