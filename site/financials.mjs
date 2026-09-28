import {escapeText as esc} from './editorial.mjs';

const numeric = p => p && typeof p.value === 'number' && Number.isFinite(p.value);
const safeUrl = u => typeof u === 'string' && /^https?:\/\//.test(u);
const link = (url, text, cls='') => safeUrl(url) ? `<a class="${cls}" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>` : `<span class="${cls}">${esc(text)}</span>`;
const nf = (value, digits=2) => Number(value).toLocaleString('en-US', {minimumFractionDigits:digits, maximumFractionDigits:digits});
const period = p => p?.start ? `${p.start} → ${p.end}` : p?.end ? `As of ${p.end}` : 'Period unavailable';
const derived = p => p?.evidence_label === 'derived_calculation';
const supported = p => numeric(p) && safeUrl(p.url) && (!derived(p) || (p.inputs?.length && p.inputs.every(input=>numeric(input)&&safeUrl(input.url))));

function scaleFor(unit, points) {
  const magnitude = Math.max(0, ...points.filter(numeric).map(p=>Math.abs(p.value)));
  if (unit === 'USD') return magnitude >= 1e9 ? {unit,divisor:1e9, label:'USD bn'} : magnitude >= 1e6 ? {unit,divisor:1e6, label:'USD mn'} : {unit,divisor:1, label:'USD'};
  return {unit,divisor:1, label:unit === 'USD/shares' ? 'USD / share' : unit === 'Percent' ? '%' : unit || 'Unit unavailable'};
}

function amount(p, scale) {
  return numeric(p) ? `${nf(p.value / scale.divisor)}${scale.label === '%' ? '%' : ' '+scale.label}` : '—';
}

function sourcePoint(p, text) {
  const title = [p.concept, 'Reported value: '+p.value+' '+p.unit, 'Accession '+p.accession, 'Filed '+p.filed].filter(Boolean).join(' · ');
  return `<span title="${esc(title)}">${link(p.url, text, 'financial-value')}</span>`;
}

function factCell(p, scale) {
  if (!numeric(p)) return '<span class="financial-missing">—</span><div class="meta">Not available</div>';
  if (!safeUrl(p.url)) return '<span class="financial-missing">—</span><div class="meta">Source link unavailable</div>';
  if (p.unit !== scale.unit) scale=scaleFor(p.unit,[p]);
  if (!derived(p)) return sourcePoint(p, amount(p,scale))+`<div class="financial-period meta">${esc(period(p))}</div>`;
  const inputs=(p.inputs||[]).filter(numeric);
  if (!inputs.length || inputs.some(input=>!safeUrl(input.url))) return '<span class="financial-missing">—</span><div class="meta">Calculation sources unavailable</div>';
  return `<span class="financial-value">${esc(amount(p,scale))}</span><div class="financial-period meta">${esc(period(p))}</div><details class="financial-evidence"><summary>Public Record calculation</summary><p>${esc(p.formula||'Formula not supplied')}</p><ul>${inputs.map(input=>`<li>${esc(input.source_label||input.metric||input.concept)}: ${sourcePoint(input,amount(input,scaleFor(input.unit,[input])))}<div class="meta">${esc(period(input))} · ${esc(input.concept)} · Filed ${esc(input.filed)}</div></li>`).join('')}</ul></details>`;
}

function changeCell(row, scale) {
  const a=row.current,b=row.prior;
  if (row.comparison_status !== 'comparable' || !supported(a) || !supported(b) || a.unit !== b.unit || a.unit !== row.unit || a.concept !== b.concept) return '<span class="financial-missing">—</span><div class="meta">No comparable prior</div>';
  const delta=a.value-b.value, signed=value=>(value>0?'+':'')+nf(value);
  if (a.unit === 'Percent') return `<span class="financial-value">${esc(signed(delta))} pp</span><div class="meta">Public Record change</div>`;
  if (b.value <= 0) return `<span class="financial-value">${esc(signed(delta/scale.divisor)+' '+scale.label)}</span><div class="meta">Absolute change · prior ≤ 0</div>`;
  return `<span class="financial-value">${esc(signed(delta/b.value*100))}%</span><div class="meta">${esc(signed(delta/scale.divisor)+' '+scale.label)} · Public Record change</div>`;
}

function metricLabel(row) {
  const current=row.current,definition=current?.source_definition;
  return `${esc(row.label||row.id)}${row.evidence_label==='derived_calculation'?'<div class="meta">Derived measure</div>':''}${row.issue?`<div class="financial-issue meta">${esc(row.issue)}</div>`:''}${row.normalization_note?`<div class="financial-issue meta">${esc(row.normalization_note)}</div>`:''}${row.concept && row.concept!=='Public Record calculation'?`<details class="financial-definition"><summary>Source definition</summary><p>${esc(row.concept)}</p>${definition?`<p>${esc(definition)}</p>`:''}</details>`:''}`;
}

function sectionTable(section) {
  const priorLabel=section.period_type==='instant'?'Fiscal year-end':'Prior-year period';
  const kind={quarter:'Quarter',ytd:'Year to date',annual:'Annual',instant:'Balance-sheet instant'}[section.period_type]||section.period_type;
  return `<section class="section financial-section"><div class="section-head"><h3>${esc(section.title)}</h3><span class="meta">${esc(kind)}</span></div><p class="financial-period meta">${esc(section.period_label||period(section))}</p><div class="table-wrap"><table class="financial-table"><thead><tr><th scope="col">Reported metric</th><th scope="col" class="numeric">Current</th><th scope="col" class="numeric">${esc(priorLabel)}</th><th scope="col" class="numeric">Change</th></tr></thead><tbody>${(section.rows||[]).map(row=>{const scale=scaleFor(row.unit,[row.current,row.prior]);return `<tr><th scope="row">${metricLabel(row)}</th><td class="numeric" data-label="Current">${factCell(row.current,scale)}</td><td class="numeric" data-label="${esc(priorLabel)}">${factCell(row.prior,scale)}</td><td class="numeric" data-label="Change">${changeCell(row,scale)}</td></tr>`;}).join('')}</tbody></table></div></section>`;
}

function annualTable(sections) {
  if (!sections.length) return '';
  const metrics=[...new Map(sections.flatMap(s=>(s.rows||[]).map(r=>[r.id,{id:r.id,label:r.label}]))).values()];
  return `<details class="financial-history section"><summary>Annual history · ${sections.length} filed periods</summary><p class="meta">Original annual-filing anchors; not a reconstructed TTM series or an original-release vintage archive.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Annual financial history"><table class="financial-table"><thead><tr><th scope="col">Reported metric</th>${sections.map(s=>`<th scope="col" class="numeric">${esc(s.period_label||period(s))}<div class="meta">${link(s.anchor?.url,(s.anchor?.form||'Annual filing')+' · filed '+(s.anchor?.filed||'date unavailable'))}</div></th>`).join('')}</tr></thead><tbody>${metrics.map(metric=>{const rows=sections.map(s=>s.rows.find(r=>r.id===metric.id)),concepts=new Set(rows.map(r=>r?.concept).filter(Boolean)),units=new Set(rows.map(r=>r?.unit).filter(Boolean));const commonScale=units.size===1?scaleFor([...units][0],rows.map(r=>r?.current)):null;return `<tr><th scope="row">${esc(metric.label||metric.id)}${concepts.size>1||units.size>1?'<div class="financial-issue meta">Source basis varies across filings</div>':''}</th>${rows.map((row,i)=>`<td class="numeric" data-label="${esc(sections[i].period_label||period(sections[i]))}">${factCell(row?.current,commonScale||scaleFor(row?.unit,[row?.current]))}${concepts.size>1&&row?.concept?`<div class="financial-concept meta">${esc(row.concept)}</div>`:''}</td>`).join('')}</tr>`;}).join('')}</tbody></table></div></details>`;
}

export function financialProfile(d,cik) {
  const c=d.financials?.companies?.find(c=>c.cik===cik);
  if (!c) return '<section class="section financials-panel"><div class="section-head"><h2>Reported financials</h2></div><p class="meta">Financial facts are not available for this registrant.</p></section>';
  const status=c.status||'unavailable',anchor=c.anchor,flags=(c.qa_flags||[]).filter(f=>f.severity!=='low');
  const sections=(c.sections||[]).filter(s=>c.profile_type!=='bank'||s.id!=='cash_flow').map(s=>c.profile_type==='bank'?{...s,rows:(s.rows||[]).filter(r=>!['operating_margin','cfo_less_cash_ppe'].includes(r.id))}:s);
  const annual=(c.annual_history||[]).slice(0,5).map(s=>c.profile_type==='bank'?{...s,rows:(s.rows||[]).filter(r=>!['operating_margin','cfo_less_cash_ppe'].includes(r.id))}:s);
  const currentCount=sections.reduce((n,s)=>n+s.rows.filter(r=>supported(r.current)).length,0);
  return `<section class="section financials-panel" aria-label="Reported financials"><div class="section-head"><h2>Reported financials</h2><span class="meta ${status==='ok'&&currentCount?'':'warning'}">${esc(status==='ok'?(currentCount?'SEC companyfacts':'Current facts unavailable'):status==='stale'?'Stale · last successful facts':status==='unavailable'?'Collection unavailable':status)}</span></div>${anchor?`<p class="meta">${link(anchor.url,(anchor.form||'Periodic filing')+' · filed '+anchor.filed)} · Report end ${esc(anchor.report_period)}</p>`:''}<p class="meta">${esc(c.status==='stale'?'Last successful capture':'Captured')} ${esc(c.last_success||c.captured_at||'unavailable')}</p>${!currentCount?'<p class="warning">No mapped current-period values are available for this filing.</p>':''}${c.boundary?`<p class="financial-boundary meta">${esc(c.boundary)}</p>`:''}${sections.length?sections.map(sectionTable).join(''):'<p class="empty-day">No filing-anchored financial statement is available.</p>'}${annualTable(annual)}${flags.length?`<details class="financial-exceptions section"><summary>Source & comparison exceptions · ${flags.length}</summary><ul>${flags.map(f=>`<li><strong>${esc(f.area||'Source')}</strong>${f.period?' · '+esc(f.period):''}: ${esc(f.issue)}</li>`).join('')}</ul></details>`:''}</section>`;
}
