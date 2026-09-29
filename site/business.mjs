import {escapeText as esc, easternDay} from './editorial.mjs';

const normalize = value => String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const safe = url => /^https?:\/\//.test(url || '');
const sourceLink = (url,text='SEC source') => safe(url) ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)} ↗</a>` : 'Source unavailable';
const profile = c => '#company?cik='+encodeURIComponent(c.cik);
const detail = (c,f) => profile(c)+'&filing='+encodeURIComponent(f.id);
const baseForm = f => String(f.form || '').replace(/\/A$/,'');
const date = value => value ? easternDay(value) : 'Date unavailable';
const universe = d => d.corporate?.companies || [];
const nf = (value,digits=1) => value.toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits});
export const businessTopics = [['reports','Business disclosures'],['results','Earnings & financial reports'],['events','Agreements & other events'],['governance','Leadership & governance'],['ownership','Insider ownership forms'],['all','All selected filings']];
const items = {
  '1.01':['events','Reports a material agreement','A material agreement is identified in Item 1.01.'],
  '1.02':['events','Reports termination of an agreement','An agreement termination is identified in Item 1.02.'],
  '1.03':['events','Reports bankruptcy or receivership','Bankruptcy or receivership is identified in Item 1.03.'],
  '1.04':['events','Reports a mine-safety disclosure','Mine-safety shutdown or violation matters are identified in Item 1.04.'],
  '1.05':['events','Reports a material cybersecurity incident','A material cybersecurity incident is identified in Item 1.05.'],
  '2.01':['events','Reports an acquisition or asset disposal','An acquisition or disposal is identified in Item 2.01.'],
  '2.02':['results','Reports financial results','Operating results and financial condition are identified in Item 2.02.'],
  '2.03':['events','Reports a new financial obligation','A financial obligation is identified in Item 2.03.'],
  '2.04':['events','Reports an accelerated financial obligation','An event accelerating or increasing a financial obligation is identified in Item 2.04.'],
  '2.05':['events','Reports exit or disposal costs','Exit or disposal costs are identified in Item 2.05.'],
  '2.06':['events','Reports a material impairment','A material impairment is identified in Item 2.06.'],
  '3.01':['events','Reports a listing or delisting notice','A listing or delisting notice is identified in Item 3.01.'],
  '3.02':['events','Reports an unregistered equity sale','An unregistered equity sale is identified in Item 3.02.'],
  '3.03':['governance','Reports changes to security-holder rights','Changes to security-holder rights are identified in Item 3.03.'],
  '4.01':['governance','Reports an auditor change','An auditor change is identified in Item 4.01.'],
  '4.02':['governance','Reports that prior financial statements should not be relied on','Non-reliance on prior financial statements is identified in Item 4.02.'],
  '5.01':['governance','Reports a change of control','A change of control is identified in Item 5.01.'],
  '5.02':['governance','Reports a leadership or compensation disclosure','Director, executive or compensation matters are identified in Item 5.02.'],
  '5.03':['governance','Reports charter, bylaw or fiscal-year changes','Charter, bylaw or fiscal-year changes are identified in Item 5.03.'],
  '5.04':['governance','Reports an employee-plan trading suspension','An employee-benefit-plan trading suspension is identified in Item 5.04.'],
  '5.05':['governance','Reports a code-of-ethics amendment or waiver','A code-of-ethics amendment or waiver is identified in Item 5.05.'],
  '5.06':['governance','Reports a change in shell-company status','A change in shell-company status is identified in Item 5.06.'],
  '5.07':['governance','Reports a shareholder vote','Shareholder voting results are identified in Item 5.07.'],
  '5.08':['governance','Reports a shareholder nomination deadline','Shareholder director-nomination timing is identified in Item 5.08; this does not establish that a nomination occurred.'],
  '6.01':['events','Reports asset-backed securities information','Asset-backed securities informational material is identified in Item 6.01.'],
  '6.02':['events','Reports a servicer or trustee change','A servicer or trustee change is identified in Item 6.02.'],
  '6.03':['events','Reports credit-enhancement or support changes','Credit-enhancement or external-support changes are identified in Item 6.03.'],
  '6.04':['events','Reports a missed required distribution','A failure to make a required distribution is identified in Item 6.04.'],
  '6.05':['events','Reports updated securities disclosure','Updated securities disclosure is identified in Item 6.05.'],
  '6.06':['events','Reports static-pool information','Static-pool information is identified in Item 6.06.'],
  '7.01':['events','Reports a Regulation FD disclosure','A Regulation FD disclosure is identified in Item 7.01.'],
  '8.01':['events','Files an other-events disclosure','Item 8.01 covers other events; the filing supplies the specific announcement.'],
  '9.01':['events','Files financial statements or exhibits','Financial statements or exhibits are identified in Item 9.01.']
};

export function filingStory(c,f) {
  const form=baseForm(f), codes=f.items || [], known=codes.filter(code=>items[code]);
  // Preserve every item as a topic; choose one bounded title without inferring the event's outcome.
  const primary=known.find(code=>!['7.01','8.01','9.01'].includes(code)) || known[0];
  let title,summary,topics;
  if(form==='10-Q'||form==='10-K') {
    title=form==='10-Q'?'Files a quarterly financial report':'Files an annual financial report';
    summary=(form==='10-Q'?'Quarterly':'Annual')+' report'+(f.report_period?' for the period ended '+f.report_period:'')+'.'; topics=['results'];
  } else if(form==='8-K') {
    title=primary?items[primary][1]:'Files a current-event report';
    summary=codes.map(code=>items[code]?.[2] || 'Reported Item '+code+'; consult the filing for its meaning.').join(' ') || 'Current-event report; item-level detail is unavailable in the submissions feed.';
    topics=[...new Set(known.map(code=>items[code][0]))]; if(!topics.length)topics=['events'];
  } else if(['3','4','5'].includes(form)) {
    title={3:'Files an initial insider ownership report',4:'Files an insider transaction report',5:'Files an annual insider ownership report'}[form];
    summary='Ownership form '+form+'. Transaction direction and economic exposure require the reported transaction details.';topics=['ownership'];
  } else if(form==='144') {
    title='Reports a proposed securities sale';summary='Notice of a proposed sale; this does not establish that a sale occurred.';topics=['ownership'];
  } else if(form==='S-3'||form==='S-8') {
    title=form==='S-3'?'Files a securities registration':'Files an employee-plan securities registration';summary=f.description || 'Securities registration; an actual issuance is not established by this form alone.';topics=['events'];
  } else if(form==='DEF 14A') {
    title='Files a proxy statement';summary='Voting, governance and compensation disclosures.';topics=['governance'];
  } else {
    title='Files '+form;summary=f.description || 'Selected SEC filing.';topics=['events'];
  }
  return {c,f,title:c.name+' — '+title+(f.amendment?' (amendment)':''),summary,topics,url:detail(c,f)};
}

function matches(text,query) {
  const tokens=normalize(query).split(' ').filter(Boolean);
  const words=normalize(text).split(' ');
  return tokens.every(token=>words.some(word=>word.startsWith(token)));
}
const identity = c => [c.name,c.cik,String(Number(c.cik)),...(c.tickers||[]),c.industry].join(' ');
function queryMatcher(d,query) {
  const q=query.trim(), tickers=universe(d).filter(c=>(c.tickers||[]).some(t=>t.toLowerCase()===q.toLowerCase()));
  if(tickers.length)return {company:c=>tickers.includes(c),story:s=>tickers.includes(s.c)};
  if(/^(?:[345]|144)$/i.test(q))return {company:()=>false,story:s=>s.f.form===q};
  if(/^(?:CIK\s+)?\d{1,10}$/i.test(q))return {company:c=>Number(c.cik)===Number(q.replace(/^CIK\s+/i,'')),story:s=>Number(s.c.cik)===Number(q.replace(/^CIK\s+/i,''))};
  if(/^(?:item\s+)?\d\.\d{2}$/i.test(q))return {company:()=>false,story:s=>(s.f.items||[]).includes(q.replace(/^item\s+/i,''))};
  if(/^(?:10-[KQ]|8-K|DEF 14A|[345]|S-[38]|144)(?:\/A)?$/i.test(q))return {company:()=>false,story:s=>s.f.form.toUpperCase()===q.toUpperCase()};
  if(/^\d{10}-\d{2}-\d{6}$/.test(q))return {company:()=>false,story:s=>s.f.id===q};
  return {company:c=>matches(identity(c),q),story:s=>matches([identity(s.c),s.title,s.summary,s.brief?.headline,s.brief?.excerpt,s.f.form,s.f.id,...(s.f.item_descriptions||[]),...businessTopics.filter(([id])=>s.topics.includes(id)).map(([,label])=>label)].join(' '),q)};
}
export function briefFor(d,c,f) {
  if(!f.items?.includes('2.02')||!/^8-K(?:\/A)?$/.test(f.form))return null;
  const base=`https://www.sec.gov/Archives/edgar/data/${Number(c.cik)}/${f.id.replaceAll('-','')}/`;
  const brief=d.business_briefs?.briefs?.find(b=>b.cik===c.cik&&b.accession===f.id&&b.filing_url===f.url);
  if(!brief||!['ok','stale'].includes(brief.status)||typeof brief.headline!=='string'||!brief.headline.trim()||typeof brief.excerpt!=='string'||!brief.excerpt.trim()||typeof brief.source?.url!=='string'||!brief.source.url.startsWith(base))return null;
  return brief;
}
const storyHeadline=s=>s.brief?.headline||s.title;
export function businessSelection(d,{q='',topic='reports',page=1}={}) {
  q=String(q).slice(0,160);topic=businessTopics.some(([id])=>id===topic)?topic:'reports';
  const query=queryMatcher(d,q),companies=universe(d).filter(query.company);
  const stories=universe(d).flatMap(c=>(c.filings||[]).map(f=>({...filingStory(c,f),brief:briefFor(d,c,f)})))
    .filter(s=>(topic==='all'||(topic==='reports'?!s.topics.includes('ownership'):s.topics.includes(topic))) && query.story(s))
    .sort((a,b)=>String(b.f.accepted_at||b.f.filed).localeCompare(String(a.f.accepted_at||a.f.filed))||b.f.id.localeCompare(a.f.id)||a.c.cik.localeCompare(b.c.cik));
  const pages=Math.max(1,Math.ceil(stories.length/12));page=Number.isSafeInteger(Number(page))&&Number(page)>0?Math.min(Number(page),pages):1;
  return {q,topic,page,pages,companies,stories};
}

function pointSupported(p,anchor) {
  return p && typeof p.value==='number' && Number.isFinite(p.value) && p.unit==='USD' && p.evidence_label==='fact_source_reported' && p.accession===anchor.accession && p.url===anchor.url && safe(p.url);
}
export function financialBrief(d,c,filing=null) {
  const financial=d.financials?.companies?.find(x=>x.cik===c.cik),anchor=financial?.anchor;
  if(!anchor||!['ok','stale'].includes(financial.status)||filing&&anchor.accession!==filing.id)return '';
  const section=(financial.sections||[]).find(s=>s.id==='operating'&&['quarter','annual'].includes(s.period_type));
  if(!section)return '';
  const rows=section.rows.filter(r=>['revenue','net_income'].includes(r.id)&&pointSupported(r.current,anchor));
  if(!rows.length)return '';
  const figures=rows.map(r=>{
    const p=r.current,prior=r.prior,divisor=Math.abs(p.value)>=1e9?1e9:1e6,unit=divisor===1e9?'USD bn':'USD mn';
    let change='';
    if(r.comparison_status==='comparable'&&pointSupported(prior,anchor)&&p.concept===prior.concept&&p.unit===prior.unit&&prior.value>0) {
      const delta=(p.value-prior.value)/prior.value*100;
      change=` <span class="meta">(${delta>0?'+':''}${esc(nf(delta))}% vs prior-year period)</span>`;
    }
    return `<div><span>${esc(r.label)}</span> <a class="metric-link" href="${profile(c)}">${esc(nf(p.value/divisor,2)+' '+unit)}</a>${change}</div>`;
  }).join('');
  const specialist=financial.profile_type&&financial.profile_type!=='operating_company'&&typeof financial.boundary==='string';
  const boundary=specialist?`<p class="meta business-identity-boundary">${esc(financial.boundary)}${financial.profile_type==='successor_registrant'?' Year-over-year values compare periods within the linked current report, not a spliced CIK history.':''}${c.cik==='0002115436'&&universe(d).some(x=>x.cik==='0000034088')?` <a href="#company?cik=0000034088">Prior Exxon registrant →</a>`:''}</p>`:'';
  return `<div class="business-financial-brief"><p class="meta">${section.period_type==='quarter'?'Reported quarter':'Reported year'} · ${esc(section.start)} → ${esc(section.end)}${financial.status==='stale'?' · Stale financial capture':''}</p>${figures}${boundary}<p class="meta">${sourceLink(anchor.url,'Financial report')} · Filed ${esc(anchor.filed)} · Financial capture ${esc(financial.last_success||financial.captured_at||'unavailable')}</p></div>`;
}

function storyCard(d,s) {
  const brief=s.brief;
  return `<article class="business-story"><div class="meta">${esc(date(s.f.filed))} · ${esc(s.f.form)} · ${esc(s.c.tickers?.[0]||'CIK '+s.c.cik)}${brief?' · Issuer Item 2.02 exhibit':''}</div><h3><a href="${esc(s.url)}">${esc(storyHeadline(s))}</a></h3>${brief?`<p>${esc(brief.excerpt)}</p><p class="meta">Issuer excerpt · ${sourceLink(brief.source.url,'Exhibit 99.1')} · Retrieved ${esc(brief.captured_at||'unavailable')}${brief.status==='stale'?' · Stale document capture':''}</p>`:`<p>${esc(s.summary)}</p>`}${financialBrief(d,s.c,s.f)}<div class="meta"><a href="${profile(s.c)}">Company profile</a> · ${sourceLink(s.f.url,baseForm(s.f)==='8-K'?'Primary 8-K':'SEC source')}${s.c.status!=='ok'?' · '+esc(s.c.status):''}</div></article>`;
}
function companyCard(c) {
  return `<a class="business-company" href="${profile(c)}"><strong>${esc(c.tickers?.join(' / ')||'CIK '+c.cik)}</strong><span>${esc(c.name)}</span><small>${esc(c.industry||'Industry unavailable')}${c.status!=='ok'?' · '+esc(c.status):''}</small></a>`;
}
function viewUrl(state,page) {
  const params=new URLSearchParams();if(state.q)params.set('q',state.q);if(state.topic!=='reports')params.set('topic',state.topic);params.set('page',page);
  return '#business?'+params;
}
const statusText=state=>`${state.stories.length} matching filings · ${state.companies.length} matching companies · Page ${state.page} of ${state.pages}`;
function companySpotlight(d,state) {
  if(!state.q.trim()||state.companies.length!==1)return '';
  const c=state.companies[0],headlines=state.stories.filter(s=>s.c.cik===c.cik).slice(0,3);
  return `<section class="business-spotlight" aria-label="Matching company"><div><div class="section-no">Company match · ${esc(c.tickers?.join(' / ')||'CIK '+c.cik)}</div><h2><a href="${profile(c)}">${esc(c.name)}</a></h2><p class="meta">${esc(c.industry||'Industry unavailable')} · CIK ${esc(c.cik)} · ${esc(c.status)} · ${sourceLink(c.url,'SEC submissions')}</p>${financialBrief(d,c)}</div><div><h3>Recent matching filings</h3>${headlines.length?`<ul>${headlines.map(s=>`<li><a href="${esc(s.url)}">${esc(storyHeadline(s))}</a><small>${esc(date(s.f.filed))} · ${esc(s.f.form)}</small></li>`).join('')}</ul>`:'<p class="meta">No filings match this topic. The company profile remains available.</p>'}<p><a href="${profile(c)}">Full company profile →</a></p></div></section>`;
}
function issuerLead(state) {
  if(state.q.trim()||state.topic!=='reports'||state.page!==1)return '';
  const featured=state.stories.filter(s=>s.brief?.status==='ok').slice(0,3);
  if(!featured.length)return '';
  return `<section class="business-issuer-lead" aria-label="Recent verified issuer reports"><div class="section-head"><h2>From issuer results</h2><span class="meta">Recent verified Item 2.02 exhibits</span></div><div class="business-issuer-grid">${featured.map(s=>`<article><div class="meta">${esc(date(s.f.filed))} · ${esc(s.c.tickers?.[0]||s.c.name)}</div><h3><a href="${esc(s.url)}">${esc(s.brief.headline)}</a></h3><p>${esc(s.brief.excerpt)}</p><div class="meta">${sourceLink(s.brief.source.url,'Original exhibit')} · <a href="${profile(s.c)}">Company profile</a></div></article>`).join('')}</div></section>`;
}
export function businessResults(d,options={}) {
  const state=businessSelection(d,options),offset=(state.page-1)*12;
  const financialCompanies=(state.q.trim()&&state.companies.length===1?[]:state.companies.filter(c=>financialBrief(d,c))).sort((a,b)=>{
    const anchors=d.financials.companies;return String(anchors.find(c=>c.cik===b.cik)?.anchor?.filed).localeCompare(String(anchors.find(c=>c.cik===a.cik)?.anchor?.filed));
  }).slice(0,6);
  const sidebarCompanies=state.q.trim()&&state.companies.length===1?[]:state.companies;
  const briefCount=d.business_briefs?.briefs?.filter(b=>['ok','stale'].includes(b.status)).length||0;
  return `${companySpotlight(d,state)}${issuerLead(state)}<div class="business-layout"><section id="business-headlines" tabindex="-1"><div class="section-head"><h2>${state.q?'Matching headlines':'Latest selected filings'}</h2><a href="#corporate">Filing browser →</a></div>${state.stories.slice(offset,offset+12).map(s=>storyCard(d,s)).join('')||'<p class="empty-day">No captured filings match. Try a company name, ticker, CIK or disclosure topic.</p>'}${state.pages>1?`<div class="business-pagination">${state.page>1?`<a href="${esc(viewUrl(state,state.page-1))}">← Previous</a>`:'<span>← Previous</span>'}<span>${state.page} / ${state.pages}</span>${state.page<state.pages?`<a href="${esc(viewUrl(state,state.page+1))}">Next →</a>`:'<span>Next →</span>'}</div>`:''}</section><aside>${sidebarCompanies.length?`<div class="section-head"><h2>${state.q?'Matching companies':'Company profiles'}</h2></div>${sidebarCompanies.slice(0,6).map(companyCard).join('')}${sidebarCompanies.length>6?`<details class="business-directory"><summary>All ${sidebarCompanies.length} matching companies</summary>${sidebarCompanies.slice(6).map(companyCard).join('')}</details>`:''}`:state.companies.length?'':`<p class="meta">No company identity matches this query. Headlines may still match a disclosure topic.</p>`}<p class="meta business-scope">${universe(d).length} selected SEC registrants. ${briefCount?`${briefCount} recent Item 2.02 exhibits have issuer-text headlines and excerpts; other headlines describe filing metadata.`:'Headlines describe filing forms and reported items.'} Independent news coverage is not yet collected.</p></aside></div>${financialCompanies.length?`<section class="section"><div class="section-head"><h2>Reported financials</h2><span class="meta">Most recently filed reports among matching companies</span></div><div class="business-financial-grid">${financialCompanies.map(c=>`<article><h3><a href="${profile(c)}">${esc(c.name)}</a></h3>${financialBrief(d,c)}</article>`).join('')}</div></section>`:''}`;
}

export function businessPage(d,options={}) {
  const state=businessSelection(d,options);
  return `<div class="page-title"><div><div class="section-no">Business desk</div><h1>Companies & disclosures</h1></div></div><form id="business-search" class="filters business-search" role="search"><label class="search">Company or disclosure<input id="business-q" type="search" maxlength="160" value="${esc(state.q)}" placeholder="AAPL, Microsoft, acquisition, earnings…"></label><label>Headlines<select id="business-topic">${businessTopics.map(([id,label])=>`<option value="${id}"${state.topic===id?' selected':''}>${label}</option>`).join('')}</select></label><button type="submit">Search</button></form><p id="business-status" class="meta" role="status" aria-atomic="true">${esc(statusText(state))}</p><p class="meta business-front-scope">Selected filings from ${universe(d).length} SEC registrants; issuer exhibit text appears only where its source could be verified. Not a complete filings or news feed.</p><div id="business-results" data-page="${state.page}">${businessResults(d,state)}</div>`;
}

export function bindBusiness(root,d) {
  const form=root.querySelector('#business-search'),results=root.querySelector('#business-results');if(!form||!results)return;
  let timer;
  function update() {
    if(!form.isConnected)return;
    const q=form.querySelector('#business-q').value,topic=form.querySelector('#business-topic').value;
    const state=businessSelection(d,{q,topic});results.innerHTML=businessResults(d,state);results.dataset.page=state.page;
    root.querySelector('#business-status').textContent=statusText(state);
    const params=new URLSearchParams();if(q)params.set('q',q);if(topic!=='reports')params.set('topic',topic);
    history.replaceState(null,'','#business'+(params.size?'?'+params:''));
  }
  form.addEventListener('submit',event=>{event.preventDefault();event.stopPropagation();clearTimeout(timer);update();});
  form.addEventListener('input',event=>{event.stopPropagation();clearTimeout(timer);timer=setTimeout(update,150);});
  form.addEventListener('change',event=>{event.stopPropagation();if(event.target.id==='business-topic'){clearTimeout(timer);update();}});
}

export function filingDetail(d,c,accession) {
  if(!accession)return '';
  const f=c.filings.find(f=>f.id===accession);
  if(!f)return '<section id="company-filing-detail" class="section"><h2>Filing outside this capture</h2><p>The requested accession is not in this company’s selected filings.</p></section>';
  const s=filingStory(c,f);
  const brief=briefFor(d,c,f);
  return `<section id="company-filing-detail" class="section business-filing-detail"><div class="section-no">Selected disclosure · ${esc(f.form)}${f.amendment?' · Amendment':''}</div><h2>${esc(storyHeadline({...s,brief}))}</h2>${brief?`<p>${esc(brief.excerpt)}</p><p class="meta">Issuer text from Exhibit 99.1 · ${sourceLink(brief.source.url,'Original exhibit')} · Retrieved ${esc(brief.captured_at||'unavailable')}${brief.status==='stale'?' · Stale document capture':''}</p>`:`<p>${esc(s.summary)}</p>`}<p class="meta">Filed ${esc(f.filed)}${f.report_period?' · Report date '+esc(f.report_period):''} · Accession ${esc(f.id)} · ${sourceLink(f.url,'Primary filing')}</p>${(f.items||[]).length?`<p class="meta">Reported items: ${esc(f.items.join(', '))}</p>`:''}${financialBrief(d,c,f)}<p class="meta">${brief?'Headline and excerpt reproduced from the linked issuer exhibit; filing identity from SEC submissions.':'Based on SEC submission metadata.'} ${f.amendment?'Read the amendment with the original filing. ':''}Captured ${esc(c.captured_at||'unavailable')}${c.status!=='ok'?' · '+esc(c.status):''}</p></section>`;
}
