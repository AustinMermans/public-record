import {recordExplanation, easternDay} from './editorial.mjs';
import {financialProfile} from './financials.mjs';
import {metricLink} from './metric-links.mjs';
import {changeEdition} from './changes.mjs';
import {fiscalTeaser} from './fiscal.mjs';
import {businessPage, filingDetail} from './business.mjs';
const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ext = (u,t) => /^https?:\/\//.test(u||'') ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t)} ↗</a>` : esc(t);
const date = d => d ? easternDay(String(d)) : 'Date not supplied';
export const normalize = v => String(v||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const contains = (text, term) => (' '+normalize(text)+' ').includes(' '+normalize(term)+' ');
const profileUrl = c => '#company?cik='+encodeURIComponent(c.cik);
const companies = d => d.corporate?.companies || [];
const status = (d,id) => {const s=d.sources.find(s=>s.id===id);return s?.status&&s.status!=='ok'?' · '+s.status:'';};
const heading = (label,title,description='') => `<div class="page-title"><div><div class="section-no">${esc(label)}</div><h1>${esc(title)}</h1>${description?`<p>${esc(description)}</p>`:''}</div></div>`;
const jump = (url,title,description) => `<a class="desk-jump" href="${esc(url)}"><h3>${esc(title)} <span aria-hidden="true">→</span></h3><p>${esc(description)}</p></a>`;
const section = (name,href,body,label='Explore') => `<section class="section"><div class="section-head"><h2>${esc(name)}</h2>${href?`<a href="${esc(href)}">${esc(label)} →</a>`:''}</div>${body}</section>`;
const recordCard = (r,d) => `<article class="news-item"><div class="section-no">${esc(r.domain)} / ${esc(r.kind)}</div><h3><button class="headline-button" data-record="${esc(r.id)}">${esc(r.title)}</button></h3>${recordExplanation(r)&&recordExplanation(r).text!==r.title?`<p>${esc(recordExplanation(r).text.slice(0,330))}</p>`:''}<div class="meta">${esc(date(r.date))} · ${esc(r.publisher)}${esc(status(d,r.source_id))} · ${ext(r.url,'Source')}</div></article>`;
const cards = (rows,d) => rows.length?rows.map(r=>recordCard(r,d)).join(''):'<p class="meta">No matching records in this capture.</p>';
const filingCard = (f,c) => `<article class="news-item"><div class="meta">${esc(date(f.filed))} · ${esc(f.form)}${f.amendment?' · amendment':''}</div><h3>${ext(f.url,c.name+' · '+(f.item_descriptions?.[0]||f.description))}</h3><p>${esc(f.item_descriptions?.slice(1).join(' · ')||f.description)}</p><div class="meta"><a href="${profileUrl(c)}">${esc(c.name)}</a>${f.report_period?' · Report period '+esc(f.report_period):''}${c.status!=='ok'?' · '+esc(c.status):''}</div></article>`;
const recentOperating = d => companies(d).flatMap(c=>c.filings.filter(f=>/^(10-[KQ]|8-K)(\/A)?$/.test(f.form)).slice(0,1).map(f=>({f,c}))).sort((a,b)=>(b.f.accepted_at||b.f.filed).localeCompare(a.f.accepted_at||a.f.filed));
const moreTools = `<div class="desk-links"><a href="#calendar">Release calendar →</a><a href="#search">Search the record →</a><a href="#sources">Sources & coverage →</a></div>`;

export const deskFor = {overview:'overview','economy-home':'economy-home',economy:'economy-home',business:'business',corporate:'business',company:'business','disclosures-home':'disclosures-home',disclosures:'disclosures-home','outlook-home':'outlook-home',outlook:'outlook-home','changes-home':'changes-home',changes:'changes-home',government:'government',news:'news',search:'search',calendar:'calendar'};
export const deskNames = {'economy-home':'Economy',business:'Business','disclosures-home':'Disclosures','outlook-home':'Outlook','changes-home':'Changes',government:'Government & Politics',news:'News & announcements'};

export function publicationHome(d,{kpi,agenda,nextEvents}) {
  const operating=recentOperating(d), rule=d.records.find(r=>r.source_id==='register'), news=d.records.filter(r=>r.kind==='Press release');
  return heading('The front page','The public record')+
    `<div class="publication-lead"><section><div class="section-head"><h2>From the desks</h2><span class="meta">Latest captured item in each selection</span></div><div class="lead-pair"><div><div class="desk-label"><a href="#business">Business →</a></div>${operating[0]?filingCard(operating[0].f,operating[0].c):'<p>No company filings available.</p>'}</div><div><div class="desk-label"><a href="#disclosures-home">Law & regulation →</a></div>${rule?recordCard(rule,d):'<p>No regulatory records available.</p>'}</div></div></section><aside class="publication-aside"><div class="section-head"><h2>Up next</h2><a href="#calendar">Calendar →</a></div>${nextEvents(3).map(agenda).join('')||'<p>No upcoming events captured.</p>'}</aside></div>`+changeEdition(d,{compact:true})+
    `<div class="desk-directory">${jump('#economy-home','Economy','Inflation, employment, activity and rates. Explore the data and its history.')}${jump('#funding','Funding & credit','Overnight rates, financial stress and bank loan performance.')}${jump('#business','Business','Company profiles, operating reports and ownership disclosures.')}${jump('#disclosures-home','Disclosures','Court activity, proposed rules, official decisions and policy statements.')}${jump('#outlook-home','Outlook','Official projections, nowcasts and historical information sets.')}${jump('#changes-home','Changes','Newly captured documents, revised values and altered schedules.')}${jump('#government','Government & politics','Institutions, policy and the public record of decisions.')}${jump('#news','News & announcements','Direct-source announcements. Reporting and wider news coverage are next.')}</div>`+
    `<div class="publication-bottom"><section>${section('Official announcements','#news',cards(news.slice(0,3),d),'All announcements')}</section><aside>${section('Economic backdrop','#economy-home',`<div class="compact-kpis">${['UNRATE','CPIAUCSL'].map(kpi).join('')}</div>`,'Economy')}${fiscalTeaser(d)}</aside></div>`;
}

export function deskPage(d,route,{kpi,brief,agenda,nextEvents},options={}) {
  if(route==='government')return heading('Government & politics desk','Public finances, policy & decisions')+fiscalTeaser(d)+`<div class="desk-directory">${jump('#fiscal','Federal fiscal conditions','Receipts, spending, net interest and the deficit, with matched fiscal-year comparisons.')}${jump('#disclosures?domain=Policy','Monetary policy & oversight','Official Federal Reserve announcements and decisions.')}${jump('#disclosures?domain=Regulation','Rulemaking & agencies','Published rules, proposals and notices from the Federal Register.')}${jump('#calendar','Public deadlines','Official release schedules and expected regulatory publications.')}</div><div class="story-grid">${['Policy','Regulation'].map(domain=>section(domain,'#disclosures?domain='+domain,cards(d.records.filter(r=>r.domain===domain).slice(0,3),d),'Browse')).join('')}</div><section class="section coverage-boundary"><h2>People & political disclosures</h2><p>Politician profiles, votes, campaign finance and officials’ financial disclosures are not yet collected. Those will be separate, identity-checked records—not inferred from name mentions in this feed.</p></section>`;
  if(route==='economy-home')return heading('Economy desk','The economic picture')+`<div class="kpis">${['CPIAUCSL','UNRATE','GDPC1','DGS10'].map(kpi).join('')}</div><div class="publication-lead"><section>${section('In brief','#economy',brief('PCEPILFE','Inflation','')+brief('PAYEMS','Employment','')+brief('GDPC1','Activity',''),'Explore the charts')}</section><aside>${section('Next releases & auctions','#calendar',nextEvents(4).map(agenda).join(''),'Calendar')}</aside></div><div class="desk-directory">${jump('#economy?series=CPIAUCSL','Prices & inflation','Consumer prices, core inflation and PCE.')}${jump('#economy?series=PAYEMS','Work & income','Payrolls, unemployment and initial claims.')}${jump('#economy?series=GDPC1','Activity & housing','GDP, production, retail sales and housing starts.')}${jump('#economy?series=DFF','Rates & financial conditions','Policy rates, Treasury yields and the yield curve.')}</div>`;
  if(route==='business')return businessPage(d,options);
  if(route==='disclosures-home')return heading('Disclosures desk','Decisions, proposals & proceedings')+`<div class="desk-directory">${jump('#disclosures?domain=Legal','Courts & proceedings','Recent docket activity from three US district courts.')}${jump('#disclosures?domain=Regulation','Rules & regulation','Federal Register notices, rules and public inspection.')}${jump('#disclosures?domain=Policy','Policy statements','Federal Reserve announcements and decisions.')}</div><div class="story-grid">${['Legal','Regulation','Policy'].map(domain=>`<section>${section(domain,'#disclosures?domain='+domain,cards(d.records.filter(r=>r.domain===domain).slice(0,2),d),'Full record')}</section>`).join('')}</div>${moreTools}`;
  if(route==='outlook-home')return heading('Outlook desk','The forward-looking picture')+`<div class="story-grid">${(d.research?.forecasts||[]).map(f=>{const href='#outlook?forecast='+encodeURIComponent(f.id);return `<article class="forecast-teaser"><div class="section-no">${f.id==='sep'?'Policy projections':'Model nowcast'}</div><h2><a href="${href}">${esc(f.title)}</a></h2>${f.value!==undefined?`<div class="forecast-number">${metricLink(href,f.title,f.value,'%')}</div><p>${esc(f.target)} · ${esc(f.unit)}</p>`:`<p><a href="${href}">${f.rows?.length||0} indicators across ${f.horizons?.length||0} projection horizons</a>.</p>`}<p class="meta">Published ${esc(f.published_at)} · ${esc(f.status)}<br>${esc(f.basis)}</p>${ext(f.url,'Source')} · <a href="${href}">Read the forecasts →</a></article>`;}).join('')}</div><div class="desk-directory">${jump('#outlook','Forecast tables & research','Compare the extracted projections; explore further research sources.')}${jump('#economy?series=GDPC1&vintage=2020-07-30','What was known then?','Explore a sampled ALFRED history alongside revised observations.')}${jump('#calendar','The next information','Upcoming releases and official schedules.')}</div>`;
  if(route==='changes-home')return heading('Changes desk','The change edition')+changeEdition(d,{compact:true});
  if(route==='news')return heading('News & announcements','From the source','Federal Reserve press releases in the current capture. Official communications, not independent news reporting.')+`<div class="story-grid">${cards(d.records.filter(r=>r.kind==='Press release'),d)}</div>${moreTools}`;
  return '';
}

// Identity-bound SEC filings and lexical mentions are deliberately separate layers.
export function companyMentions(d,c) {
  const legal=normalize(c.name), short=legal.replace(/\s+(inc|corp|corporation|co)(\s.*)?$/,'');
  const names=[legal,...(short.length>=5?[short]:[])];
  return d.records.filter(r=>names.some(n=>contains(`${r.title} ${r.summary||''}`,n)));
}

export function companyPage(d,cik,accession='') {
  const c=companies(d).find(c=>c.cik===cik);
  if(!c)return heading('Business / Company','Company not in current coverage','Try a company name, ticker or CIK in search.')+'<a href="#business">Browse covered companies →</a>';
  const mentions=companyMentions(d,c), operating=c.filings.filter(f=>/^(10-[KQ]|8-K)(\/A)?$/.test(f.form)), ownership=c.filings.filter(f=>/^[345](\/A)?$/.test(f.form));
  return heading('Business / Company profile',c.name,`${c.tickers?.join(' · ')||'No ticker supplied'} · CIK ${c.cik} · ${c.industry||'Industry not supplied'}`)+`<div class="profile-meta">${ext(c.url,'SEC company submissions')}<span class="meta">Captured ${esc(c.captured_at||'unavailable')} · ${esc(c.status)}</span></div><div class="desk-links"><a href="#corporate?company=${esc(c.cik)}">All captured filings & filters →</a><a href="#search?q=${encodeURIComponent(c.name)}">Search this name across the record →</a></div>${filingDetail(d,c,accession)}${financialProfile(d,cik)}<div class="change-counts"><div><strong>${operating.length}</strong><span>Operating reports captured</span></div><div><strong>${ownership.length}</strong><span>Ownership forms captured</span></div><div><strong>${c.filings.length}</strong><span>Total selected filings captured</span></div></div>${section('Operating reports','#corporate?company='+c.cik,`<div class="story-grid">${operating.slice(0,6).map(f=>filingCard(f,c)).join('')||'<p>No operating reports captured.</p>'}</div>`,'All filings')}<p class="meta">These filings are linked by SEC CIK. Captured categories are bounded; this is not the company’s complete filing history.</p>${section('Name matches in the wider record','',`<p class="meta">${mentions.length} lexical matches in this capture; these are research leads, not verified entity links or established legal exposure.</p><div class="story-grid">${cards(mentions.slice(0,6),d)}</div>`)}${mentions.length>6?`<p><a href="#search?mentions=${encodeURIComponent(c.cik)}">Search more name matches →</a></p>`:''}`;
}

export function buildSearchIndex(d) {
  const index=[], seen=new Set();
  // Different docket entries may share one case URL. Preserve each record ID.
  function add(row,fields) {if(row.kind!=='record'&&row.url&&seen.has(row.url))return;if(row.url)seen.add(row.url);index.push({...row,text:normalize(fields)});}
  for(const c of companies(d)){
    const identity=[c.name,...(c.tickers||[]),c.cik,String(Number(c.cik))].join(' ');
    add({kind:'company',title:c.name,url:profileUrl(c),summary:`${c.tickers?.join(' · ')||''} · CIK ${c.cik} · ${c.industry||''} · ${c.status}`,date:c.captured_at,exact:[c.cik,String(Number(c.cik)),...(c.tickers||[])].map(normalize)},identity+' '+c.industry);
    for(const f of c.filings)add({kind:'filing',title:`${c.name} · ${f.form}`,url:f.url,summary:[f.description,...(f.item_descriptions||[])].join(' · '),date:f.filed,profile:profileUrl(c),publisher:'SEC · CIK '+c.cik+' · '+c.status},[identity,f.form,f.id,f.description,...(f.item_descriptions||[])].join(' '));
  }
  for(const r of d.records)add({kind:'record',title:r.title,url:r.url,summary:recordExplanation(r)?.text||r.summary||'',date:r.date,publisher:r.publisher+status(d,r.source_id),recordId:r.id},[r.title,r.summary,r.kind,r.publisher,...(r.agencies||[])].join(' '));
  for(const s of d.series)add({kind:'indicator',title:s.name,url:'#economy?series='+encodeURIComponent(s.id),summary:s.domain+' · '+s.unit,date:s.observations.at(-1)?.[0],publisher:s.publisher+status(d,s.source_id)},[s.id,s.name,s.domain,s.publisher,s.unit].join(' '));
  // Event URLs may be shared calendars, so preserve individual event entries.
  for(const e of d.events)index.push({kind:'event',title:e.title,url:e.url,summary:e.kind,date:e.date,publisher:e.publisher+status(d,e.source_id),text:normalize([e.title,e.publisher,e.kind,e.summary].join(' '))});
  for(const f of d.research?.forecasts||[])add({kind:'research',title:f.title,url:f.url,summary:f.basis,date:f.published_at,publisher:f.status},[f.title,f.basis,f.target,...(f.rows||[]).map(r=>r.name)].join(' '));
  if(d.fiscal?.metrics?.length)for(const m of d.fiscal.metrics)add({kind:'indicator',title:'Federal '+m.label,url:'#fiscal?view=fytd&metric='+encodeURIComponent(m.id),summary:'Fiscal-year-to-date · USD · '+(d.fiscal.status||'unavailable'),date:d.fiscal.edition,publisher:'US Treasury'},['fiscal','Treasury','federal budget',m.id,m.label,m.id==='balance'?'deficit surplus':''].join(' '));
  if(d.banking?.metrics?.length)for(const m of [...d.banking.metrics,...(d.banking.context||[])])add({kind:'indicator',title:'Banking: '+m.label,url:'#funding?view=banking&metric='+encodeURIComponent(m.id),summary:'FDIC-reported all-insured aggregate · '+m.unit+(m.annualized?' · annualized':'')+' · '+(d.banking.status||'unavailable'),date:d.banking.quarter_end,publisher:'FDIC'},['banking','credit','FDIC',m.id,m.label,m.definition].join(' '));
  return index;
}

export function searchIndex(index,query,kind='') {
  const q=normalize(String(query).slice(0,160)), tokens=q.split(' ').filter(Boolean);
  if(!tokens.length)return [];
  return index.filter(r=>(!kind||r.kind===kind)&&tokens.every(t=>contains(r.text,t))).map(r=>({...r,score:r.kind==='company'?100+(r.exact?.includes(q)?100:0):contains(r.title,q)?30:10})).sort((a,b)=>b.score-a.score||String(b.date||'').localeCompare(String(a.date||''))||a.title.localeCompare(b.title));
}

export function searchPage() {
  return heading('Search','Search the public record','Companies, filings, disclosures, indicators, events and research in this snapshot.')+`<form id="record-search" class="filters"><label class="search">Name, ticker, CIK or subject<input id="q" type="search" maxlength="160" placeholder="AAPL, Microsoft, inflation, stablecoin…"></label><label>Results<select id="search-kind"><option value="">Everything</option><option value="company">Company profiles</option><option value="filing">Company filings</option><option value="record">Public disclosures</option><option value="indicator">Economic indicators</option><option value="event">Calendar events</option><option value="research">Research</option></select></label><button type="submit">Search</button></form><p id="search-status" class="meta" role="status"></p><div id="search-results"></div>`;
}

export function searchResults(rows,offset=0) {
  const labels={company:'Company profile',filing:'Company filing',record:'Public disclosure',indicator:'Economic indicator',event:'Calendar event',research:'Research'};
  return rows.slice(offset,offset+30).map(r=>`<article class="search-result"><div class="section-no">${labels[r.kind]}</div><h2>${r.url.startsWith('#')?`<a href="${esc(r.url)}">${esc(r.title)}</a>`:ext(r.url,r.title)}</h2><p>${esc(r.summary?.slice(0,350))}</p><div class="meta">${esc(date(r.date))}${r.publisher?' · '+esc(r.publisher):''}${r.profile?` · <a href="${esc(r.profile)}">Company profile</a>`:''}${r.recordId?` · <button class="text-button" data-record="${esc(r.recordId)}">Record details</button>`:''}</div></article>`).join('');
}
