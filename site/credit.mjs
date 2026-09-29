import {escapeText as esc} from './editorial.mjs';

const safe=u=>typeof u==='string'&&/^https?:\/\//.test(u);
const link=(u,label)=>safe(u)?`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`:esc(label);
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const decimal=v=>(typeof v==='number'||typeof v==='string')&&/^-?\d+(?:\.\d+)?$/.test(String(v))&&Number.isFinite(Number(v));
const day=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v+'T00:00:00Z'))&&new Date(v+'T00:00:00Z').toISOString().slice(0,10)===v;
const fmt=(v,n=2)=>Number(v).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n});
const signed=(v,n=2)=>(v>0?'+':'')+fmt(v,n);
const movement=v=>v>0?'rose':v<0?'fell':'was unchanged';
const dateLabel=v=>day(v)?new Intl.DateTimeFormat('en-US',{timeZone:'UTC',year:'numeric',month:'short',day:'numeric'}).format(new Date(v+'T00:00:00Z')):v;
const clockLabel=v=>Number.isFinite(Date.parse(v||''))?new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(v)):v;
const expected=(s,id,source,unit)=>s?.id===id&&s.source_id===source&&s.unit===unit&&s.frequency==='Daily · not seasonally adjusted'&&safe(s.url)?s:null;
function dailyAge(date,now){
  const age=day(date)?(now-Date.parse(date+'T00:00:00Z'))/86400000:NaN;
  return {fresh:Number.isFinite(age)&&age>=0&&age<=7,label:Number.isFinite(age)&&age>=0&&age<=7?'':'daily observation older than 7 days or future-dated'};
}
const observed=s=>s?.observations;
function receipt(d,id,clock,now){
  const source=d.sources?.find(x=>x.id===id),time=source?.last_success||clock,age=now-Date.parse(time||'');
  const state=source?.status||'unavailable',fresh=state==='ok'&&Number.isFinite(age)&&age>=-5*60*1000&&age<=36*3600000;
  return {fresh,label:fresh?'':state!=='ok'?state:'retrieval older than 36 hours',time:time||'unavailable'};
}
function point(s,index){
  const p=observed(s)?.at(index);
  return p&&day(p[0])&&finite(p[1])?p:null;
}
function priorQuarter(q){
  if(!day(q)||!['03-31','06-30','09-30','12-31'].includes(q.slice(5)))return null;
  const d=new Date(Date.UTC(Number(q.slice(0,4)),Number(q.slice(5,7))-3,0));
  return d.toISOString().slice(0,10);
}
function bankPoint(b,id){
  if(!b||!['ok','partial','stale'].includes(b.status)||b.validation?.status!=='reconciled')return null;
  const m=b.metrics?.find(x=>x.id===id),quarter=b.quarter_end,prior=priorQuarter(quarter);
  if(!m||m.unit!=='Percent'||m.frequency!=='Quarterly'||(id==='nco'&&m.annualized!==true)||(id==='noncurrent'&&m.annualized!==false)||!prior)return null;
  const a=m.current,z=m.prior;
  return a?.date===quarter&&z?.date===prior&&decimal(a.value)&&decimal(z.value)&&safe(a.url)&&safe(z.url)?{current:Number(a.value),previous:Number(z.value),date:quarter,prior,url:a.url,priorUrl:z.url,definition:m.definition,annualized:m.annualized===true}:null;
}
function spreadPoints(sofr,effr){
  if(!Array.isArray(observed(sofr))||!Array.isArray(observed(effr)))return [];
  const byDate=new Map(effr.observations.filter(p=>day(p?.[0])&&finite(p?.[1])));
  return sofr.observations.filter(p=>day(p?.[0])&&finite(p?.[1])&&byDate.has(p[0])).map(([date,value])=>[date,Math.round((value-byDate.get(date))*1e8)/1e6]);
}
const row=(name,value,change,period,basis,sources,readiness,detail)=>`<tr><th scope="row">${esc(name)}<span class="meta">${esc(basis)}</span></th><td data-label="Latest">${value==='Unavailable'?value:`<a href="${esc(detail)}">${value}</a>`}</td><td data-label="Versus prior">${change}</td><td data-label="Period & evidence"><span class="meta">${esc(period)}${readiness.label?' · '+esc(readiness.label):''}<br>Retrieved <span title="${esc(readiness.time)}">${esc(clockLabel(readiness.time))}</span></span><br>${sources}</td></tr>`;

export function creditRead(d,{now=Date.now()}={}){
  const series=d.series||[],sofr=expected(series.find(s=>s.id==='NYFED-SOFR'),'NYFED-SOFR','nyfed-sofr','Percent'),effr=expected(series.find(s=>s.id==='NYFED-EFFR'),'NYFED-EFFR','nyfed-effr','Percent'),fsi=expected(series.find(s=>s.id==='OFR-FSI'),'OFR-FSI','ofr-fsi','Index points'),credit=expected(series.find(s=>s.id==='OFR-CREDIT'),'OFR-CREDIT','ofr-fsi','Index points');
  const spreads=spreadPoints(sofr,effr),sp=spreads.at(-1),spPrior=spreads.at(-2),fsiNow=point(fsi,-1),fsiPrior=point(fsi,-2),creditNow=point(credit,-1),creditPrior=point(credit,-2);
  const component=creditNow&&creditPrior&&fsiNow&&credit?.source_id===fsi?.source_id&&creditNow[0]===fsiNow[0]&&creditPrior[0]===fsiPrior?.[0]?{current:creditNow,prior:creditPrior}:null;
  const b=d.banking,non=bankPoint(b,'noncurrent'),nco=bankPoint(b,'nco');
  const rateReceipt=receipt(d,'nyfed-sofr',sofr?.captured_at,now),effrReceipt=receipt(d,'nyfed-effr',effr?.captured_at,now),fsiReceipt=receipt(d,'ofr-fsi',fsi?.captured_at,now),bankReceipt=receipt(d,'fdic-qbp',b?.last_success||b?.captured_at,now);
  const rateAge=dailyAge(sp?.[0],now),fsiAge=dailyAge(fsiNow?.[0],now);
  const rateState={fresh:rateReceipt.fresh&&effrReceipt.fresh&&rateAge.fresh,label:[rateReceipt.label,effrReceipt.label,rateAge.label].filter(Boolean).join(' / '),time:rateReceipt.time===effrReceipt.time?rateReceipt.time:rateReceipt.time+' / '+effrReceipt.time};
  const fsiState={fresh:fsiReceipt.fresh&&fsiAge.fresh,label:[fsiReceipt.label,fsiAge.label].filter(Boolean).join(' / '),time:fsiReceipt.time};
  const bankState={fresh:bankReceipt.fresh&&b?.status==='ok',label:b?.status&&b.status!=='ok'?b.status:bankReceipt.label,time:bankReceipt.time};
  const rows=[
    row('SOFR − EFFR',sp?fmt(sp[1])+' bp':'Unavailable',sp&&spPrior?signed(sp[1]-spPrior[1])+' bp':'Unavailable',sp?`Effective ${sp[0]} · prior common ${spPrior?.[0]||'unavailable'}`:'No common effective date','Same-date overnight rate spread',`${link(sofr?.url,'SOFR')} · ${link(effr?.url,'EFFR')}`,rateState,'#funding?view=spread'),
    row('Global financial stress',fsiNow?fmt(fsiNow[1],3)+' points':'Unavailable',fsiNow&&fsiPrior?signed(fsiNow[1]-fsiPrior[1],3)+' points':'Unavailable',fsiNow?`Observed ${fsiNow[0]} · prior ${fsiPrior?.[0]||'unavailable'}`:'Observation unavailable','OFR global index; zero is historical average',link(fsi?.url,'OFR index'),fsiState,'#economy?series=OFR-FSI'),
    row('OFR credit contribution',component?fmt(component.current[1],3)+' points':'Unavailable',component?signed(component.current[1]-component.prior[1],3)+' points':'Unavailable',component?`Observed ${component.current[0]} · prior ${component.prior[0]}`:'Aligned component unavailable','Signed contribution, not a credit spread',link(credit?.url,'OFR components'),fsiState,'#economy?series=OFR-CREDIT'),
    row('Noncurrent loans / loans',non?fmt(non.current)+'%':'Unavailable',non?signed(non.current-non.previous)+' pp':'Unavailable',non?`Quarter ended ${non.date} · prior ${non.prior}`:'Quarterly comparison unavailable','FDIC all-insured aggregate; quarter-end stock',link(non?.url||b?.url,'FDIC workbook'),bankState,'#funding?view=banking&metric=noncurrent'),
    row('Net charge-off rate',nco?fmt(nco.current)+'%':'Unavailable',nco?signed(nco.current-nco.previous)+' pp':'Unavailable',nco?`Quarter ended ${nco.date} · prior ${nco.prior}`:'Quarterly comparison unavailable','FDIC all-insured aggregate; annualized quarterly flow',link(nco?.url||b?.url,'FDIC workbook'),bankState,'#funding?view=banking&metric=nco')
  ];
  const complete=sp&&spPrior&&fsiNow&&fsiPrior&&component&&non&&nco&&rateState.fresh&&fsiState.fresh&&bankState.fresh;
  const read=complete?`The overnight spread ${movement(sp[1]-spPrior[1])} on ${dateLabel(sp[0])}; global stress ${movement(fsiNow[1]-fsiPrior[1])} on ${dateLabel(fsiNow[0])}, while its credit contribution ${movement(component.current[1]-component.prior[1])}. In the latest FDIC quarter (${dateLabel(non.date)}), noncurrent loans ${movement(non.current-non.previous)} and the annualized charge-off rate ${movement(nco.current-nco.previous)} versus the prior quarter.`:'A combined read is withheld where a comparison is missing, stale or not validated; individual observations remain separately sourced below.';
  return `<section class="section credit-read" id="credit-read"><div class="section-head"><h2>Credit conditions · latest evidence</h2></div><p>${esc(read)}</p><p class="meta">These are separate clocks and populations: daily US overnight funding, a lagged global stress index, and quarterly US insured-bank aggregates. Their directions do not establish a common cause or a synchronized credit trend. FDIC quarter comparisons use the current QBP workbook edition${b?.edition?' ('+esc(b.edition)+')':''}, not reconstructed original-release vintages; a new capture is not a new quarterly observation.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Dated credit conditions evidence"><table class="credit-table"><thead><tr><th scope="col">Measure</th><th scope="col">Latest</th><th scope="col">Versus prior</th><th scope="col">Period & evidence</th></tr></thead><tbody>${rows.join('')}</tbody></table></div></section>`;
}
