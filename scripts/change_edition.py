"""Assemble independently captured changes without inventing a global window."""
import copy
import hashlib
import json
import re
from datetime import datetime
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

from publication_changes import compare_corporate, compare_research, compare_spf
from financial_changes import compare_financials
from fiscal import compare_fiscal
from banking import compare_banking
from bea_changes import compare_bea_releases
from energy import compare_energy
from inflation import compare as compare_inflation


def channel_domain(sid):
    if sid.startswith(('sec-company-', 'sec-financials-')) or sid == 'sec':
        return 'Companies'
    if sid.startswith('research-'):
        return 'Outlook'
    if sid == 'cleveland-inflation-nowcast':
        return 'Outlook'
    if sid.startswith(('nyfed-', 'ofr-')) or sid == 'fdic-qbp':
        return 'Funding'
    if sid.startswith('fred-') or sid in ('treasury-mts', 'bea-gdp-releases', 'eia-wpsr'):
        return 'Economic data'
    if sid in ('bls', 'bea', 'fomc', 'treasury'):
        return 'Calendar'
    return 'Disclosures'


def filing_identity(url):
    parsed = urlparse(url or '')
    if parsed.scheme != 'https' or parsed.netloc.lower() != 'www.sec.gov':
        return None
    match = re.match(r'^/Archives/edgar/data/(\d+)/(\d{18})/', parsed.path)
    if not match:
        return None
    cik, compact = match.groups()
    if len(cik) > 10:
        return None
    return cik.zfill(10), compact[:10]+'-'+compact[10:12]+'-'+compact[12:]


def calendar_day(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return (date.astimezone(ZoneInfo('America/New_York')) if date.tzinfo else date).date().isoformat()
    except (ValueError, TypeError):
        return None


def legacy_channels(changes, sources):
    """Migration only: never infer unchanged-source success from one global date."""
    channels = []
    for source in sources:
        sid = source['id']
        samples = [x for x in changes.get('items', []) if x['source_id'] == sid]
        state = 'unavailable' if source.get('status') != 'ok' else 'baseline' if sid in changes.get('baselines', []) else 'compared' if samples else 'unavailable'
        channels.append(dict(id=sid, label=source.get('name', sid), status=state,
            from_capture=samples[0].get('from_capture') if samples else None,
            to_capture=source.get('last_success'),
            error=source.get('error') if source.get('status')!='ok' else 'Prior per-channel comparison receipt not retained; next collection records it.' if state=='unavailable' else None))
    return channels


def assemble_changes(data):
    core = copy.deepcopy(data.get('changes') or dict(items=[], baselines=[], skipped=[]))
    core.setdefault('channels', legacy_channels(core, data.get('sources', [])))
    groups = [core]
    for key, compare in (('corporate', compare_corporate), ('research', compare_research), ('spf', compare_spf), ('financials', compare_financials), ('fiscal', compare_fiscal), ('banking', compare_banking), ('bea_releases', compare_bea_releases), ('energy', compare_energy), ('inflation', compare_inflation)):
        module = data.get(key)
        if not module:
            continue
        changes = copy.deepcopy(module.get('changes'))
        if changes is None:
            changes = compare(None, module)
        if 'channels' not in changes:
            # A retained module diff is not a first capture. Recover exact
            # successful windows from its items, never from the bundle clock.
            if key == 'financials':
                sources = [dict(id='sec-financials-'+c['cik'], name=c.get('name', c['cik']),
                    status=c.get('status'), last_success=c.get('captured_at'), error=c.get('error'))
                    for c in module.get('companies', [])]
                changes['channels'] = legacy_channels(changes, sources)
            else:
                raise ValueError('Comparison module lacks channel receipts')
        groups.append(changes)
    companies = {c['cik']: c for c in data.get('corporate', {}).get('companies', [])}
    events = {e['id']: e for e in data.get('events', [])}
    items, channels = [], []
    for group in groups:
        for c in group.get('channels', []):
            channels.append(dict(c, domain=channel_domain(c['id'])))
        for original in group.get('items', []):
            item = copy.deepcopy(original)
            sid = item['source_id']; domain = channel_domain(sid)
            if item.get('record_id') in events:
                domain = 'Calendar'
            item.update(domain=domain, channel_id=sid)
            identity = filing_identity(item.get('url'))
            if identity and domain == 'Companies':
                cik, accession = identity
                if item.get('cik') and item['cik'] != cik:
                    raise ValueError('Financial/filing change CIK differs from SEC evidence URL')
                if item.get('accession') and item['accession'] != accession:
                    raise ValueError('Financial/filing change accession differs from SEC evidence URL')
                item.update(cik=cik, accession=accession, development_id=f'filing:{cik}:{accession}')
            if item.get('cik') in companies:
                item['company'] = companies[item['cik']].get('name', item['cik'])
                detail = '#company?' + urlencode({'cik': item['cik']})
            elif sid == 'fdic-qbp':
                detail = '#funding?' + urlencode(dict(view='banking',metric=item.get('metric_id','noncurrent')))
            elif sid == 'treasury-mts':
                monthly = item.get('period_type') == 'month' and item.get('metric_id') in ('receipts','outlays','balance')
                detail = '#fiscal?' + urlencode(dict(view='monthly',metric=item['metric_id'])) if monthly else '#fiscal?view=fytd'
            elif sid == 'bea-gdp-releases':
                detail = '#gdp-releases?' + urlencode({'quarter': item['target']})
            elif sid == 'eia-wpsr':
                detail = '#energy?' + urlencode({'metric': item['metric_id']})
            elif sid == 'cleveland-inflation-nowcast':
                detail = '#inflation-watch?' + urlencode({'basis': item['basis'], 'target': item['target'], 'metric': item['metric_id']})
            elif item.get('forecast_id'):
                params={'forecast': item['forecast_id']}
                if item['forecast_id']=='spf':
                    if item.get('metric_id'):params['metric']=item['metric_id']
                    if item.get('target'):params['target']=item['target']
                detail = '#outlook?' + urlencode(params)
            elif item.get('series_id'):
                detail = '#economy?' + urlencode({'series': item['series_id'], 'transform': 'level', 'period': 'all'})
            elif domain == 'Calendar':
                day = calendar_day(item.get('date') or item.get('after'))
                event = events.get(item.get('record_id'), {})
                params = {'month': day[:7], 'day': day} if day else {}
                if event.get('kind') == 'Expected publication':
                    params['event-type'] = event['kind']
                detail = '#calendar' + ('?' + urlencode(params) if params else '')
            else:
                detail = '#disclosures?' + urlencode({'publisher': sid})
            item['detail_url'] = detail
            canonical = json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            item['id'] = 'change-' + hashlib.sha256(canonical.encode()).hexdigest()[:24]
            items.append(item)
    if len({c['id'] for c in channels}) != len(channels):
        raise ValueError('Duplicate comparison channel')
    if len({x['id'] for x in items}) != len(items):
        raise ValueError('Duplicate change event')
    to_dates = [c['to_capture'] for c in channels if c.get('to_capture')]
    return dict(core, items=items, channels=channels,
        latest_capture=max(to_dates, key=lambda date: datetime.fromisoformat(date.replace('Z', '+00:00')).timestamp()) if to_dates else None,
        baselines=[c['id'] for c in channels if c['status']=='baseline'],
        skipped=[c['id'] for c in channels if c['status']=='unavailable'],
        comparison_scope='Independent prior-success windows per channel; not a single publication-wide window.')
