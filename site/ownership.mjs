import {escapeText as esc, easternDay} from './editorial.mjs';

const source = (url,label='SEC filing') => /^https:\/\/www\.sec\.gov\//.test(url||'')
  ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>` : 'Source unavailable';
const day = value => value ? easternDay(value) : 'Date unavailable';
const formList = d => d.ownership?.forms || [];
const companies = d => d.corporate?.companies || [];
const kindOf = row => row.code==='P' && row.direction==='A' ? 'purchase'
  : row.code==='S' && row.direction==='D' ? 'sale'
  : ['A','D','F','M'].includes(row.code) ? 'compensation' : 'other';
const labelOf = row => ({P:'Purchase-coded transaction',S:'Sale-coded transaction',A:'Award or grant',
  C:'Conversion of derivative security',
  D:'Disposition to issuer',F:'Shares delivered or withheld for exercise price or tax',
  M:'Exercise or conversion',G:'Gift',J:'Other transaction (see filing)'}[row.code] ||
  (row.code ? `SEC transaction code ${row.code}` : 'Unclassified transaction'));
const num = value => {
  if(value == null || value==='')return 'Not reported';
  const literal=String(value);
  if(!/^-?\d+(?:\.\d+)?$/.test(literal))return esc(literal);
  const [whole,fraction]=literal.split('.');
  return esc(whole.replace(/\B(?=(\d{3})+(?!\d))/g,',')+(fraction==null?'':'.'+fraction));
};
const who = form => form.document?.owners?.map(owner=>owner.name).join(' · ') || 'Owner unavailable';
const profile = cik => '#company?cik='+encodeURIComponent(cik);
const filing = form => profile(form.cik)+'&filing='+encodeURIComponent(form.accession);
const url = ({cik='',kind='all',page=1}={}) => {
  const params=new URLSearchParams();if(cik)params.set('cik',cik);if(kind!=='all')params.set('kind',kind);
  if(page>1)params.set('page',String(page));return '#ownership'+(params.size?'?'+params:'');
};

export function ownershipRows(d) {
  return formList(d).filter(form=>form.status==='ok').flatMap(form=>form.document.rows.map(row=>({form,row,kind:kindOf(row)})))
    .sort((a,b)=>String(b.form.accepted_at||b.form.filed).localeCompare(String(a.form.accepted_at||a.form.filed))
      ||b.form.accession.localeCompare(a.form.accession)||a.row.id.localeCompare(b.row.id));
}

export function ownershipSelection(d,options={}) {
  const cik=companies(d).some(c=>c.cik===options.cik)?options.cik:'';
  const kind=['all','purchase','sale','compensation','other'].includes(options.kind)?options.kind:'all';
  const rows=ownershipRows(d).filter(item=>(!cik||item.form.cik===cik)&&(kind==='all'||item.kind===kind));
  const pages=Math.max(1,Math.ceil(rows.length/20));
  const wanted=Number(options.page);const page=Number.isSafeInteger(wanted)&&wanted>0?Math.min(wanted,pages):1;
  return {cik,kind,rows,page,pages};
}

export function ownershipCard(item,{compact=false}={}) {
  const {form,row}=item,ownership=row.ownership==='D'?'Direct':row.ownership==='I'?'Indirect':'Ownership type not reported';
  const notes=row.footnotes||[];
  return `<article class="ownership-row"${compact?'':` id="ownership-${esc(row.id.replaceAll(':','-'))}"`}><div class="meta">${esc(day(form.filed))} filed · ${esc(form.form)} · ${esc(form.tickers?.[0]||'CIK '+form.cik)}${form.form==='4/A'?' · Amendment':''}</div>`+
    `<h3><a href="${esc(filing(form))}">${esc(form.company)} — ${esc(labelOf(row))}</a></h3>`+
    `<p>${esc(row.security||'Security not specified')}${row.underlying_security?' · Underlying '+esc(row.underlying_security):''} · ${esc(row.table==='derivative'?'Derivative table':'Non-derivative table')} · `+
    `${esc(row.direction==='A'?'Acquired':row.direction==='D'?'Disposed':'Direction not reported')} · `+
    `${esc(ownership)} · Transaction ${esc(day(row.transaction_date))}</p>`+
    `<p class="ownership-figures"><span>Shares <strong>${num(row.shares)}</strong></span><span>Price/share <strong>${num(row.price_per_share)}</strong></span>`+
    `${row.owned_after!=null?`<span>Owned after <strong>${num(row.owned_after)}</strong></span>`:''}</p>`+
    `<p class="meta">Reporting owner${form.document.owners.length===1?'':'s'}: ${esc(who(form))}${row.ownership_nature?' · '+esc(row.ownership_nature):''}</p>`+
    `${form.document.filing_plan_indicated===true?'<p class="meta">Filing-level Rule 10b5-1 indicator marked; not assigned to an individual row.</p>':''}`+
    `${notes.length?`<details><summary>${notes.length} filing footnote${notes.length===1?'':'s'}</summary>${notes.map(note=>`<p class="meta"><strong>${esc(note.id)}</strong> ${esc(note.text)}</p>`).join('')}</details>`:''}`+
    `<p class="meta">${source(form.xml_url,'Raw SEC XML')} · ${source(form.filing_url,'SEC filing')} · <a href="${esc(profile(form.cik))}">Company profile</a>${form.cached?' · Cached verified filing':''}</p>`+
    `${compact?'':`<p class="meta">Code ${esc(row.code||'not reported')} · Row ${esc(String(row.ordinal))} · ${esc(form.accession)}.${row.code==='P'?' Purchase code P can be open-market or private; venue and investment merit are not inferred.':''}</p>`}</article>`;
}

export function ownershipTeaser(d) {
  const forms=formList(d);if(!forms.length)return '';
  const seen=new Set();
  const rows=ownershipRows(d).filter(item=>{if(seen.has(item.form.cik))return false;seen.add(item.form.cik);return true;}).slice(0,3);
  const excluded=forms.filter(f=>f.status==='other_issuer').length;
  const stale=companies(d).filter(c=>c.status!=='ok').length;
  return `<section class="section ownership-teaser"><div class="section-head"><h2>Reported ownership transactions</h2><a href="#ownership">Explore all rows →</a></div>`+
    `<p class="meta">Selected recent filings from distinct issuers · ${forms.filter(f=>f.status==='ok').length} issuer-matched Forms 4/4-A${excluded?' · '+excluded+' other-issuer filings excluded':''}${stale?' · '+stale+' company submissions stale/unavailable':''}. Not a market-wide screen.</p>`+
    `<div class="ownership-teaser-grid">${rows.map(({form,row})=>`<article class="ownership-teaser-item"><div class="meta">${esc(day(form.filed))} filed · ${esc(form.tickers?.[0]||'CIK '+form.cik)}</div><h3><a href="${esc(filing(form))}">${esc(form.company)}</a></h3><p>${esc(labelOf(row))} · ${esc(row.table==='derivative'?'Derivative':'Non-derivative')} · ${esc(row.security||'Security not specified')}</p><p class="meta">${esc(who(form))} · ${source(form.xml_url,'SEC XML')}</p></article>`).join('')||'<p>Transaction details are not yet available from the selected SEC XML files.</p>'}</div></section>`;
}

export function ownershipOverview(d) {
  const seen=new Set();
  const latest=formList(d).filter(form=>form.status==='ok'&&form.document?.rows?.length)
    .sort((a,b)=>String(b.accepted_at||b.filed).localeCompare(String(a.accepted_at||a.filed))||b.accession.localeCompare(a.accession))
    .filter(form=>{if(seen.has(form.cik))return false;seen.add(form.cik);return true;}).slice(0,6);
  if(!latest.length)return '';
  return `<section class="ownership-overview"><div class="section-head"><h2>Latest across issuers</h2></div>`+
    `<p class="meta">One latest selected filing per issuer; filed date, not a ranking of investment significance.</p>`+
    `<div class="ownership-overview-grid">${latest.map(form=>{
      const rows=form.document.rows,codeLabels=[...new Set(rows.map(row=>labelOf(row)))].slice(0,2);
      return `<article class="ownership-overview-item"><div class="meta">${esc(day(form.filed))} filed · ${esc(form.form)}${form.form==='4/A'?' · Amendment':''}</div>`+
        `<h3><a href="${esc(filing(form))}">${esc(form.company)}</a></h3>`+
        `<p>${rows.length} reported row${rows.length===1?'':'s'} · ${esc(codeLabels.join(' · '))}${[...new Set(rows.map(row=>labelOf(row)))].length>2?' · More codes in filing':''}</p>`+
        `<p class="meta">${esc(who(form))} · ${source(form.xml_url,'SEC XML')}</p></article>`;
    }).join('')}</div></section>`;
}

export function companyOwnership(d,cik) {
  const forms=formList(d).filter(f=>f.cik===cik);
  if(!forms.length)return '';
  const rows=ownershipRows(d).filter(item=>item.form.cik===cik).slice(0,5);
  const excluded=forms.filter(f=>f.status==='other_issuer').length;
  const discovery=companies(d).find(c=>c.cik===cik)?.status;
  return `<section class="section company-ownership"><div class="section-head"><h2>Reported ownership transactions</h2><a href="${esc(url({cik}))}">All selected rows →</a></div>`+
    `<p class="meta">${forms.filter(f=>f.status==='ok').length} issuer-matched of ${forms.length} selected Forms 4/4-A${excluded?'; '+excluded+' concern other issuers and are excluded':''}${discovery&&discovery!=='ok'?'; SEC submissions discovery '+esc(discovery):''}. Filings can contain multiple rows and owners. Amendments remain separate.</p>`+
    `${rows.map(item=>ownershipCard(item,{compact:true})).join('')||'<p>No transaction rows could be verified for this company.</p>'}</section>`;
}

export function filingOwnership(d,cik,accession) {
  const form=formList(d).find(item=>item.cik===cik&&item.accession===accession);
  if(!form||form.status!=='ok')return form?'<p class="meta">Transaction-level XML is unavailable for this selected filing; use the SEC source.</p>':'';
  return `<div class="ownership-filing-rows"><p class="meta">${form.document.rows.length} transaction row${form.document.rows.length===1?'':'s'} in this filing; multiple owners are listed at filing level and rows are not multiplied by owner.</p>`+
    `${form.document.rows.map(row=>ownershipCard({form,row,kind:kindOf(row)})).join('')||'<p class="meta">No transaction rows in the Form 4 XML.</p>'}</div>`;
}

export function ownershipPage(d,options={}) {
  const state=ownershipSelection(d,options),forms=formList(d),parsed=forms.filter(f=>f.status==='ok').length;
  const excluded=forms.filter(f=>f.status==='other_issuer').length;
  const discoveryGaps=companies(d).filter(c=>c.status!=='ok').length;
  return `<div class="page-title"><div><div class="section-no">Business / SEC ownership</div><h1>Reported ownership transactions</h1></div></div>`+
    `<form id="ownership-filters" class="filters" role="search"><label>Company<select id="ownership-company"><option value="">All covered companies</option>${companies(d).map(c=>`<option value="${esc(c.cik)}"${c.cik===state.cik?' selected':''}>${esc(c.name)}</option>`).join('')}</select></label>`+
    `<label>Transaction<select id="ownership-kind">${[['all','All reported rows'],['purchase','Purchase-coded acquisitions'],['sale','Sale-coded dispositions'],['compensation','Awards, exercises & issuer dispositions'],['other','Other or unclassified']].map(([id,label])=>`<option value="${id}"${id===state.kind?' selected':''}>${esc(label)}</option>`).join('')}</select></label><button type="submit">Apply</button></form>`+
    `<p class="meta" role="status">${state.rows.length} matching rows · ${parsed} issuer-matched filings${excluded?' · '+excluded+' other-issuer filings excluded':''} · Page ${state.page} of ${state.pages}</p>`+
    `<p class="meta ownership-scope">Selected SEC Forms 4/4-A from ${companies(d).length} registrants; ${forms.length-parsed-excluded} XML unavailable${discoveryGaps?'; submissions discovery stale/unavailable for '+discoveryGaps+' companies':''}. Code P can be private; amendments are not netted. Not market-wide.</p>`+
    `${!state.cik&&state.kind==='all'&&state.page===1?ownershipOverview(d):''}`+
    `<div class="section-head ownership-ledger-head"><h2>Transaction rows</h2></div>`+
    `<div class="ownership-list">${state.rows.slice((state.page-1)*20,state.page*20).map(item=>ownershipCard(item)).join('')||'<p class="empty-day">No verified rows match this selection.</p>'}</div>`+
    `${state.pages>1?`<nav class="business-pagination" aria-label="Ownership pages">${state.page>1?`<a href="${esc(url({...state,page:state.page-1}))}">← Previous</a>`:'<span>← Previous</span>'}<span>${state.page} / ${state.pages}</span>${state.page<state.pages?`<a href="${esc(url({...state,page:state.page+1}))}">Next →</a>`:'<span>Next →</span>'}</nav>`:''}`+
    `<details class="ownership-method"><summary>Coverage and method</summary><p>Each record is a row in one SEC Form 4 XML filing, identified by issuer CIK, accession, table and row position. Several reporting owners can share a filing; a row is not copied to each person. The purchase filter includes derivative and non-derivative P/A rows, but P can describe open-market or private purchases; venue is not established. Form 4/A rows may amend earlier reports and are not deduplicated or summed. Shares and price are displayed as filed, without inferred dollar value or cash flow. Footnotes can change interpretation. Filing-level Rule 10b5-1 indicators are not assigned to individual rows. This is not an investment recommendation.</p><p>${source('https://www.sec.gov/edgar/searchedgar/ownershipformcodes.html','SEC transaction-code definitions')} · ${source('https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data','SEC EDGAR access')}</p></details>`;
}

export function bindOwnership(root) {
  const form=root.querySelector('#ownership-filters');if(!form)return;
  form.addEventListener('submit',event=>{event.preventDefault();location.hash=url({
    cik:form.querySelector('#ownership-company').value,kind:form.querySelector('#ownership-kind').value,
  });});
}
