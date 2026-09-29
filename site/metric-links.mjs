const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export const indicatorHref = id => '#economy?series='+encodeURIComponent(id)+'&transform=default&period=all';

export function metricLink(href, label, value, suffix='') {
  const text = esc(value ?? '—') + (suffix ? `<small>${esc(suffix)}</small>` : '');
  if (value === null || value === undefined || value === '—' || !/^#(?:economy|funding|outlook)\?/.test(href||'')) return text;
  return `<a class="metric-link" href="${esc(href)}" aria-label="${esc(label+': '+value+suffix+'. View detail')}">${text}</a>`;
}

export function detailTarget(route, query) {
  if (route === 'changes' && ['company','domain','source','kind','page'].some(key => query.get(key))) return 'change-results-status';
  if (route === 'company' && query.get('filing')) return 'company-filing-detail';
  if (route === 'business' && /^[1-9]\d*$/.test(query.get('page')||'')) return 'business-headlines';
  if (route === 'funding' && query.get('view') === 'banking') return 'banking-panel';
  if (route === 'fiscal' && ['fytd','monthly'].includes(query.get('view'))) return 'fiscal-'+query.get('view');
  if (route === 'funding' && query.get('view') === 'spread') return 'funding-comparison';
  if (route === 'outlook' && ['gdpnow','sep','spf','gdp-watch'].includes(query.get('forecast'))) return 'forecast-'+query.get('forecast');
  return null;
}
