// Dated BEA Personal Income and Outlays releases are official actuals;
// Cleveland Fed snapshots are a separate, point-in-time model information set.
const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const beaUrl = u => /^https:\/\/www\.bea\.gov\/news\/20\d{2}\/[a-z0-9-]+$/.test(u || '') ? u : '';
const clevelandUrl = 'https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting';
const fields = ['headline_mom','core_mom','headline_yoy','core_yoy'];
const month = t => /^20\d{2}-(0[1-9]|1[0-2])$/.test(t || '') ? new Intl.DateTimeFormat('en-US',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(t+'-01T12:00:00Z')) : '';
const dateLabel = value => {const d=new Date(value+'T12:00:00Z');return /^20\d{2}-\d{2}-\d{2}$/.test(value||'')&&Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===value ? new Intl.DateTimeFormat('en-US',{month:'long',day:'numeric',year:'numeric',timeZone:'UTC'}).format(d) : value;};
const display = (r,key) => {
  const printed=r?.display_values?.[key];
  return typeof printed==='string' && /^-?\d+(?:\.\d+)?$/.test(printed) && Number(printed)===r.values[key]
    ? printed : Number(r.values[key]).toFixed(1);
};
const timestamp = x => {
  const parsed=Date.parse(x || '');
  return Number.isFinite(parsed)?parsed:null;
};

export function pceReleaseState(bundle) {
  const releases=(bundle?.releases||[]).filter(r => month(r.target) && beaUrl(r.url) &&
    /^20\d{2}-\d{2}-\d{2}$/.test(r.published_at||'') && timestamp(r.embargo_at)!==null &&
    fields.every(key=>Number.isFinite(r.values?.[key]) && Math.abs(r.values[key])<100));
  const byTarget=new Map(releases.map(r=>[r.target,r]));
  const scheduled=(bundle?.scheduled||[]).filter(s=>month(s.target)&&/^20\d{2}-\d{2}-\d{2}$/.test(s.date||'')&&!byTarget.has(s.target));
  const targets=[...new Set([...byTarget.keys(),...scheduled.map(s=>s.target)])].sort().reverse();
  return {releases:releases.sort((a,b)=>b.target.localeCompare(a.target)),byTarget,scheduled,targets,latest:releases.map(r=>r.target).sort().at(-1)||null};
}

function modelRow(snapshot,target) {
  const row=(snapshot?.rows||[]).find(r=>r.basis==='mom'&&r.target===target);
  if (!row || !/^20\d{2}-\d{2}-\d{2}$/.test(row.updated_on||'')) return null;
  const pce=Number(row.values?.pce), core=Number(row.values?.core_pce);
  return row.values?.pce!==null&&row.values?.core_pce!==null&&Number.isFinite(pce)&&Number.isFinite(core)
    ? {pce,core,updated_on:row.updated_on,captured_at:snapshot.captured_at} : null;
}

export function archivedPceModel(inflation,target,embargoAt=null) {
  const cutoff=embargoAt?timestamp(embargoAt):null;
  if (embargoAt && cutoff===null) return null;
  const eligible=(inflation?.history||[]).filter(snapshot=>{
    const captured=timestamp(snapshot.captured_at);
    return captured!==null && (cutoff===null||captured<cutoff);
  }).sort((a,b)=>timestamp(b.captured_at)-timestamp(a.captured_at));
  for (const snapshot of eligible) {
    const row=modelRow(snapshot,target);
    if (row) return row;
  }
  return null;
}

function modelComparison(actual,forecast) {
  if (Math.abs(forecast-actual)<0.05) return 'Less than 0.1 pp apart at the published precision';
  const gap=forecast-actual;
  const magnitude=Math.round((Math.abs(gap)+1e-9)*10)/10;
  return `Model about ${magnitude.toFixed(1)} pp ${gap>0?'above':'below'} the published actual`;
}

function measure(r,key,label,model,modelKey) {
  const actual=display(r,key), yearly=display(r,key.replace('_mom','_yoy'));
  const estimate=model?.[modelKey];
  return `<article class="pce-measure"><div class="section-no">${esc(label)}</div><h2><span class="sr-only">${esc(label)}: </span>${esc(actual)}<small>%</small></h2><p>Monthly change · seasonally adjusted, not annualized</p><p class="pce-year">${esc(yearly)}% <span>from the same month one year earlier</span></p>${estimate===undefined?'<p class="meta">No verified pre-release Cleveland Fed snapshot for this target.</p>':`<p class="pce-model">Cleveland Fed pre-release model: <strong>${estimate.toFixed(2)}%</strong></p><p class="meta">${esc(modelComparison(r.values[key],estimate))} · model updated ${esc(model.updated_on)}, captured ${esc(model.captured_at)} · <a href="${clevelandUrl}" target="_blank" rel="noopener noreferrer">Model source ↗</a></p>`}</article>`;
}

function scheduledCard(row,inflation) {
  const model=archivedPceModel(inflation,row.target);
  return `<section id="pce-read" tabindex="-1" aria-label="${esc(month(row.target))} PCE: scheduled, no verified BEA actual" class="pce-pending"><div class="section-no">${esc(month(row.target))} · scheduled</div><h2>No verified BEA actual yet</h2><p>BEA scheduled this release for ${esc(dateLabel(row.date))}; publication has not been verified.</p>${model?`<p>Cleveland Fed monthly model, not an actual: headline <strong>${model.pce.toFixed(2)}%</strong>, core <strong>${model.core.toFixed(2)}%</strong> · updated ${esc(model.updated_on)}, captured ${esc(model.captured_at)}.</p>`:'<p>No retained same-target monthly model estimate is available.</p>'}<p class="meta"><a href="https://www.bea.gov/news/schedule/full" target="_blank" rel="noopener noreferrer">BEA schedule ↗</a> · <a href="${clevelandUrl}" target="_blank" rel="noopener noreferrer">Model source ↗</a></p></section>`;
}

export function pceReleasePage(data,requestedTarget) {
  const bundle=data?.bea_pce, state=pceReleaseState(bundle);
  const header='<div class="page-title"><div><div class="section-no">Economy / published prices</div><h1>PCE release record</h1></div></div>';
  if (!state.targets.length) return header+'<p class="empty">No dated BEA PCE release has been verified in this capture. <a href="https://www.bea.gov/news/schedule/full" target="_blank" rel="noopener noreferrer">BEA schedule ↗</a></p>';
  const target=state.targets.includes(requestedTarget)?requestedTarget:state.latest||state.targets[0];
  const r=state.byTarget.get(target),pending=state.scheduled.find(s=>s.target===target);
  const context=r?`${month(target)} published: headline ${display(r,'headline_mom')}% and core ${display(r,'core_mom')}% month over month.`:`${month(target)} scheduled; no verified BEA actual.`;
  const picker=`<div class="filters pce-picker"><label>Reference month<select id="pce-target" aria-controls="pce-read" aria-describedby="pce-target-context">`+
    `<optgroup label="Published">${state.releases.map(item=>`<option value="${esc(item.target)}"${item.target===target?' selected':''}>${esc(month(item.target))}</option>`).join('')}</optgroup>`+
    `<optgroup label="Scheduled">${state.scheduled.sort((a,b)=>a.target.localeCompare(b.target)).map(item=>`<option value="${esc(item.target)}"${item.target===target?' selected':''}>${esc(month(item.target))} · scheduled</option>`).join('')}</optgroup></select></label><p id="pce-target-context" class="sr-only">${esc(context)}</p></div>`;
  const warning=bundle?.status!=='ok'?`<p class="warning">BEA release check ${esc(bundle?.status||'unavailable')}; retained entries may be stale. Last successful check ${esc(bundle?.last_success||'not supplied')}.</p>`:'';
  const next=state.scheduled.filter(s=>s.target>target).sort((a,b)=>a.date.localeCompare(b.date))[0];
  const nextLine=next?`<p class="pce-next">Next on BEA’s schedule: ${esc(month(next.target))} on ${esc(dateLabel(next.date))}. <a href="#pce-releases?target=${esc(next.target)}">See pending target →</a></p>`:'';
  const names={'headline_mom':'Headline monthly','core_mom':'Core monthly','headline_yoy':'Headline yearly','core_yoy':'Core yearly'};
  const rows=state.releases.map(item=>`<tr><th scope="row"><a href="#pce-releases?target=${esc(item.target)}">${esc(month(item.target))}</a><small>${esc(item.published_at)}</small></th>${fields.map(key=>`<td class="numeric" data-label="${names[key]}">${esc(display(item,key))}%</td>`).join('')}</tr>`).join('');
  const history=`<section class="section"><div class="section-head"><h2>Dated release history</h2><span class="meta">Each row is that month’s BEA news release</span></div><div class="table-wrap pce-history"><table><thead><tr><th>Target</th><th class="numeric">Headline m/m</th><th class="numeric">Core m/m</th><th class="numeric">Headline y/y</th><th class="numeric">Core y/y</th></tr></thead><tbody>${rows}</tbody></table></div><p class="meta">These retained release-body values are not a continuously revised index series. For revised histories, use <a href="https://fred.stlouisfed.org/series/PCEPI" target="_blank" rel="noopener noreferrer">headline PCE at FRED ↗</a> or <a href="#economy?series=PCEPILFE">core PCE here</a>; older BEA interactive-table links can display later revisions.</p></section>`;
  if (!r) return header+warning+picker+scheduledCard(pending,data?.inflation)+history;
  const model=archivedPceModel(data?.inflation,target,r.embargo_at);
  const lead=`<p class="pce-lead">For ${esc(month(target))}, BEA published <strong>${esc(display(r,'headline_mom'))}% headline</strong> and <strong>${esc(display(r,'core_mom'))}% core</strong> PCE inflation from the prior month on ${esc(dateLabel(r.published_at))}.</p>`;
  const locators=r.source_locator && typeof r.source_locator==='object'
    ? Object.values(r.source_locator).join(' / ') : r.source_locator||'News Release body';
  const sources=`<p class="meta pce-sources"><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">Exact BEA release ↗</a></p><details class="pce-provenance"><summary>Source receipt and method</summary><p class="meta">Embargo ${esc(r.embargo_at)} · Retrieved ${esc(r.captured_at||'not supplied')} · SHA-256 ${esc(r.sha256||'not supplied')} · ${esc(locators)}</p><p class="meta">Monthly rates are not annualized; year-over-year rates compare the same month a year earlier. Cleveland Fed values are one model, not market consensus. Differences use BEA’s published rounded tenths, not unrounded indexes, and are not trading surprises or accuracy scores. Only a model snapshot captured before the release’s embargo qualifies for comparison.</p></details>`;
  return header+warning+picker+`<section id="pce-read" tabindex="-1" aria-label="${esc(month(target))} published BEA PCE price results">${lead}${nextLine}<div class="pce-measures">${measure(r,'headline_mom','Headline PCE',model,'pce')}${measure(r,'core_mom','Excluding food & energy',model,'core')}</div>${sources}</section>`+history;
}

export function bindPce(root) {
  root.querySelector('#pce-target')?.addEventListener('change',event=>{
    const target=event.currentTarget.value;
    if (month(target)) location.hash='#pce-releases?target='+target;
  });
}

export function pceReleaseTeaser(data) {
  const state=pceReleaseState(data?.bea_pce),r=state.byTarget.get(state.latest);
  if (!r) return '';
  const next=state.scheduled.sort((a,b)=>a.date.localeCompare(b.date))[0];
  return `<article class="brief"><h3>PCE as published</h3><p><a href="#pce-releases?target=${esc(r.target)}"><strong>${esc(display(r,'core_mom'))}% core</strong> and ${esc(display(r,'headline_mom'))}% headline m/m · ${esc(month(r.target))}</a></p><div class="evidence">BEA release · ${esc(r.published_at)} · <a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">Source ↗</a>${next?` · <a href="#pce-releases?target=${esc(next.target)}">Next: ${esc(month(next.target))}</a>`:''}</div></article>`;
}
