import {escapeText as esc} from './editorial.mjs';

const safe = url => typeof url === 'string' && /^https:\/\//.test(url);
const link = (url, label) => safe(url) ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>` : esc(label);
const local = (cik) => '#company?cik='+encodeURIComponent(cik)+'&dossier=earnings';
const amount = value => {
  const divisor = Math.abs(value) >= 1e9 ? 1e9 : 1e6;
  return (value/divisor).toLocaleString('en-US',{maximumFractionDigits:2,minimumFractionDigits:2})+' USD '+(divisor===1e9?'bn':'mn');
};
const comparison = row => {
  const prior=row.prior?.value,current=row.current?.value;
  if(typeof prior!=='number'||!Number.isFinite(prior)||typeof current!=='number'||!Number.isFinite(current))return '—';
  if(prior<=0)return 'Prior ≤ 0 · percentage not shown';
  const delta=(current-prior)/prior*100;
  return (delta>0?'+':'')+delta.toLocaleString('en-US',{maximumFractionDigits:1,minimumFractionDigits:1})+'%';
};

export const dossierFor = (d,cik) => d.earnings_dossiers?.dossiers?.find(x=>x.cik===cik) || null;
export const dossierUrl = local;

export function dossierTeaser(d,cik,accession='') {
  const item=dossierFor(d,cik);
  if(!item?.event||item.status==='metadata_only'||accession&&item.event.accession!==accession)return '';
  const match=['matched','stale_matched'].includes(item.status);
  return `<a class="earnings-dossier-link" href="${esc(local(cik))}">${match?'Read earnings with filed figures':'Earnings source & coverage'} →</a>`;
}

export function earningsDossier(d,cik) {
  const item=dossierFor(d,cik);
  if(!item||['no_selected_event','metadata_only'].includes(item.status))return '';
  const event=item.event, matched=['matched','stale_matched'].includes(item.status), figures=item.financial?.figures||[];
  const first=figures.find(row=>row.id==='revenue')||figures[0];
  const lead=matched&&first ? `${first.label}: ${amount(first.current.value)}${first.prior?' versus '+amount(first.prior.value)+' a year earlier ('+comparison(first)+')':''}.` : item.reason;
  const net=figures.find(row=>row.id==='net_income');
  const netChange=net?.prior?.value>0?(net.current.value-net.prior.value)/net.prior.value:null;
  const exceptional=netChange!==null&&Math.abs(netChange)>1;
  return `<section id="company-earnings-dossier" tabindex="-1" class="section earnings-dossier" aria-label="Filed quarterly result"><div class="section-head"><h2>Filed quarterly result</h2><span class="meta ${matched?'':'warning'}">${matched?item.status==='stale_matched'?'Matched · stale capture':'Issuer exhibit + 10-Q':'Source boundary'}</span></div><div class="earnings-dossier-lead"><div><p class="earnings-lead">${esc(lead)}</p>${event.headline?`<p>${esc(event.headline)}</p>`:''}</div><div class="earnings-source-stack"><span class="meta">Issuer release · ${esc(event.filed)}</span>${link(event.exhibit_url||event.url,event.exhibit_url?'Original exhibit':'SEC 8-K')}</div></div>${event.excerpt&&event.exhibit_url?`<p class="earnings-highlight"><span class="meta">Issuer highlight</span><br>${esc(event.excerpt)}</p>`:''}${matched?`<div class="table-wrap"><table class="earnings-table"><thead><tr><th scope="col">Reported measure</th><th scope="col">Quarter ended ${esc(item.period_end)}</th><th scope="col">Prior-year quarter</th><th scope="col">Change</th></tr></thead><tbody>${figures.map(row=>`<tr><th scope="row">${esc(row.label)}</th><td data-label="Current">${link(row.current.url,amount(row.current.value))}<small>${esc(row.current.start)} → ${esc(row.current.end)}</small></td><td data-label="Prior year">${row.prior?`${link(row.prior.url,amount(row.prior.value))}<small>${esc(row.prior.start)} → ${esc(row.prior.end)}</small>`:'—'}</td><td data-label="Change">${esc(comparison(row))}</td></tr>`).join('')}</tbody></table></div>${exceptional?`<p class="earnings-caution">Net income moved ${esc(comparison(net))} year over year. These two filed measures do not establish the cause or whether the change is recurring; inspect the ${link(item.financial.anchor.url,'10-Q')} and ${link(event.exhibit_url,'issuer exhibit')}.</p>`:''}<p class="meta">${esc(item.period_basis)} · ${link(item.financial.anchor.url,'Controlling 10-Q')} filed ${esc(item.financial.anchor.filed)}. Changes calculated from two source-reported values; no consensus or surprise estimate.</p>${item.financial.boundary?`<p class="meta earnings-boundary">${esc(item.financial.boundary)}${item.financial.profile_type==='successor_registrant'?' Comparisons use the current report only; separate CIK histories are not spliced.':''}</p>`:''}`:`<p class="meta">${link(event.url,'Primary 8-K')}${event.exhibit_url?' · '+link(event.exhibit_url,'Issuer exhibit'):''}. Figures are omitted because the release and controlling quarterly facts cannot be joined safely.</p>`}<p class="meta earnings-clock">8-K filed ${esc(event.filed)}${matched?' · Quarter ended '+esc(item.period_end)+' · 10-Q filed '+esc(item.financial.anchor.filed):''} · Exhibit captured ${esc(event.captured_at||'unavailable')}${matched?' · Facts captured '+esc(item.financial.captured_at||'unavailable'):''}</p></section>`;
}
