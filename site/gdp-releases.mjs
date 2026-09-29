// Dated BEA news releases are a different information set from current FRED history.
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stageNames = {advance:'Advance estimate',second:'Second estimate',third:'Third estimate'};
const stageOrder = ['advance','second','third'];
const releaseUrl = u => /^https:\/\/www\.bea\.gov\/news\/20\d{2}\//.test(u || '') ? u : '';
const sourceLink = (u,label) => releaseUrl(u) ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>` : '';
const quarterLabel = q => /^20\d{2}Q[1-4]$/.test(q || '') ? `${q.slice(0,4)} Q${q.slice(-1)}` : '';
const round = (n,places=1) => Number(n).toFixed(places);
const easternToday = () => new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York'}).format(new Date());

export function releaseState(bundle) {
  const releases = (bundle?.releases || []).filter(r =>
    /^20\d{2}Q[1-4]$/.test(r.quarter || '') && stageOrder.includes(r.stage) &&
    /^20\d{2}-\d{2}-\d{2}$/.test(r.published_at || '') &&
    Number.isFinite(r.value) && /^-?\d+(?:\.\d+)?$/.test(r.display_value || '') &&
    Number(r.display_value) === r.value && r.unit === 'percent' &&
    r.basis === 'quarterly seasonally adjusted annual rate' && releaseUrl(r.url));
  const grouped = new Map();
  for (const r of releases) {
    if (!grouped.has(r.quarter)) grouped.set(r.quarter, new Map());
    const stages = grouped.get(r.quarter);
    if (!stages.has(r.stage) || stages.get(r.stage).published_at < r.published_at) stages.set(r.stage,r);
  }
  const quarters = [...grouped.keys()].sort().reverse();
  return {quarters, grouped, latest:quarters[0] || null};
}

export function revisedGdp(data,quarter) {
  const series = (data?.series || []).find(s => s.id === 'GDPC1' && s.source_id === 'fred-GDPC1');
  if (!series || !/^20\d{2}Q[1-4]$/.test(quarter || '')) return null;
  const end = `${quarter.slice(0,4)}-${['01-01','04-01','07-01','10-01'][Number(quarter.at(-1))-1]}`;
  const rows = series.observations || [];
  const index = rows.findIndex(p => p[0] === end);
  if (index < 1 || !Number.isFinite(rows[index][1]) || !Number.isFinite(rows[index-1][1]) || rows[index-1][1] <= 0) return null;
  const previous = new Date(end+'T00:00:00Z'); previous.setUTCMonth(previous.getUTCMonth()-3);
  if (rows[index-1][0] !== previous.toISOString().slice(0,10)) return null;
  return {value:100*((rows[index][1]/rows[index-1][1])**4-1),url:series.url,captured_at:series.captured_at,observation:end,status:data.sources?.find(s=>s.id==='fred-GDPC1')?.status || 'unknown'};
}

function changeText(current,previous) {
  if (!previous) return current.stage==='advance'?'First published estimate for this quarter.':'No preceding captured stage for comparison.';
  const a=Number(current.display_value),b=Number(previous.display_value);
  const precision=Math.max((current.display_value.split('.')[1]||'').length,(previous.display_value.split('.')[1]||'').length);
  if (a===b) {
    const note=current.revision_note ? ` ${esc(current.revision_note)}` : ' Rounding can conceal a smaller revision.';
    return `Same ${round(a,precision)}% at shown precision.${note}`;
  }
  return `Published estimate ${a>b?'rose':'fell'} ${round(Math.abs(a-b),precision)} percentage point${Math.abs(a-b)===1?'':'s'} from the ${stageNames[previous.stage].toLowerCase()}.`;
}

export function gdpReleasePage(data,requestedQuarter,asOf=easternToday()) {
  const bundle=data?.bea_releases, state=releaseState(bundle);
  if (!state.latest) return `<div class="page-title"><div><div class="section-no">Economy / releases</div><h1>GDP release record</h1></div></div><p class="empty">No dated BEA GDP release has been verified in this capture. <a href="https://www.bea.gov/news/schedule/full" target="_blank" rel="noopener noreferrer">Check BEA’s schedule ↗</a>.</p>`;
  const quarter=state.grouped.has(requestedQuarter)?requestedQuarter:state.latest;
  const stages=state.grouped.get(quarter),last=[...stages.values()].sort((a,b)=>stageOrder.indexOf(a.stage)-stageOrder.indexOf(b.stage)).at(-1);
  const revised=revisedGdp(data,quarter);
  const pending=(bundle?.scheduled || []).filter(e=>e.quarter===quarter && stageOrder.includes(e.stage) && !stages.has(e.stage));
  const next=(bundle?.scheduled || []).filter(e=>/^20\d{2}Q[1-4]$/.test(e.quarter||'') && stageOrder.includes(e.stage) && /^20\d{2}-\d{2}-\d{2}$/.test(e.date||'') && e.date>=asOf && !state.grouped.get(e.quarter)?.has(e.stage)).sort((a,b)=>a.date.localeCompare(b.date)||stageOrder.indexOf(a.stage)-stageOrder.indexOf(b.stage))[0];
  let prior=null;
  const cards=stageOrder.map(stage=>{
    const r=stages.get(stage);
    if (!r) {
      const scheduled=pending.find(e=>e.stage===stage);
      return `<div class="gdp-stage pending"><div class="section-no">${stageNames[stage]}</div><h2>Not captured</h2><p>${scheduled?`Scheduled ${esc(scheduled.date)}. A calendar entry is not a published result.`:'No verified release in this capture.'}</p></div>`;
    }
    const explanation=changeText(r,prior);prior=r;
    return `<article class="gdp-stage"><div class="section-no">${stageNames[stage]} · ${esc(r.published_at)}</div><h2>${esc(r.display_value)}<span>%</span></h2><p>${explanation}</p><div class="meta">Real GDP growth · quarterly SAAR · ${sourceLink(r.url,'BEA release')}</div><details><summary>Evidence & clock</summary><p>Published ${esc(r.published_at)} · retrieved ${esc(r.captured_at || 'not supplied')} · source SHA-256 ${esc(r.sha256 || 'not supplied')}. Extraction: ${esc(r.source_locator || 'release body')}.</p>${r.gdi_value == null?'<p>No verified Real GDI value extracted for this stage.</p>':''}</details></article>`;
  }).join('');
  const lead=last ? `<p class="gdp-lead">BEA reported <strong>${esc(last.display_value)}% real GDP growth</strong> for ${quarterLabel(quarter)} in its ${stageNames[last.stage].toLowerCase()} on ${esc(last.published_at)}. ${changeText(last,stageOrder.slice(0,stageOrder.indexOf(last.stage)).reverse().map(s=>stages.get(s)).find(Boolean))}</p>` : '';
  const nextLine=next?`<aside class="gdp-next" aria-label="Next scheduled GDP release"><strong>Next on BEA’s calendar</strong> · ${esc(next.date)} · ${quarterLabel(next.quarter)} ${stageNames[next.stage].toLowerCase()}. Scheduled, not a published result. <a href="#calendar?month=${next.date.slice(0,7)}&amp;day=${next.date}">Calendar →</a> · <a href="https://www.bea.gov/news/schedule/full" target="_blank" rel="noopener noreferrer">BEA schedule ↗</a></aside>`:'';
  return `<div class="page-title"><div><div class="section-no">Economy / published estimates</div><h1>GDP release record</h1></div></div>${bundle.status!=='ok'?`<p class="warning">BEA release check ${esc(bundle.status || 'unavailable')} · retained dated releases may be stale. Last successful check ${esc(bundle.captured_at || 'not supplied')}.</p>`:''}${lead}<div class="filters"><label>Target quarter<select id="gdp-release-quarter">${state.quarters.map(q=>`<option value="${q}" ${q===quarter?'selected':''}>${quarterLabel(q)}</option>`).join('')}</select></label></div>${nextLine}<div class="gdp-stage-grid">${cards}</div><section class="section gdp-revised"><div class="section-head"><h2>Latest revised history</h2><a href="#economy?series=GDPC1">Explore GDP chart →</a></div>${revised?`<p><strong>${round(revised.value,1)}%</strong> for ${quarterLabel(quarter)}, calculated from current-revised FRED GDPC1 levels.</p><div class="meta"><a href="${esc(revised.url)}" target="_blank" rel="noopener noreferrer">FRED series ↗</a> · levels retrieved ${esc(revised.captured_at || 'not supplied')} · ${esc(revised.status)} capture</div>`:'<p>No matching current-revised quarterly observation in this capture.</p>'}<p class="meta">This is a different information set. It may incorporate later annual or benchmark revisions; it is not a fourth release stage and is not used in the stage-to-stage comparison.</p></section><p class="meta">BEA’s dated news pages supply the values above. Displayed tenths cannot establish an exact underlying revision. This selected release history covers 2025 Q4 forward; it does not reconstruct all historical first releases. <a href="https://www.bea.gov/news/schedule/full" target="_blank" rel="noopener noreferrer">Official release schedule ↗</a></p>`;
}

export function gdpReleaseTeaser(data) {
  const state=releaseState(data?.bea_releases),q=state.latest;
  if (!q) return '';
  const last=[...state.grouped.get(q).values()].sort((a,b)=>stageOrder.indexOf(b.stage)-stageOrder.indexOf(a.stage))[0];
  return `<article class="brief"><h3>GDP as published</h3><p><a href="#gdp-releases?quarter=${q}"><strong>${esc(last.display_value)}%</strong> · ${quarterLabel(q)} ${stageNames[last.stage].toLowerCase()}</a></p><div class="evidence">Dated BEA release · ${esc(last.published_at)} · ${sourceLink(last.url,'Source')}</div></article>`;
}
