"""Compare retained financial screens without mixing periods or definitions."""
import json


def rows(company):
    # Current-filing comparative evidence takes precedence over the annual
    # panel's original-report history when the exact metric/period overlaps.
    result = {}
    for section in [*company.get('annual_history', []), *company.get('sections', [])]:
        sid = 'operating' if section['id'] == 'annual' else section['id']
        for row in section.get('rows', []):
            for which in ('prior', 'current'):
                point = row.get(which)
                if point:
                    key = (sid, row['id'], point.get('start'), point['end'])
                    result[key] = (row, point)
    return result


def basis(point):
    result = {k: point.get(k) for k in ('namespace', 'concept', 'unit', 'formula', 'evidence_label')}
    if point.get('inputs'):
        result['inputs'] = [dict(metric=p.get('metric'), **basis(p)) for p in point['inputs']]
    return result


def compare_financials(previous, current):
    result = dict(from_capture=(previous or {}).get('captured_at'),
                  to_capture=current['captured_at'], items=[], baselines=[], skipped=[], channels=[])
    before = {c['cik']: c for c in (previous or {}).get('companies', [])}
    for company in current['companies']:
        cik = company['cik']; sid = 'sec-financials-' + cik
        old = before.get(cik)
        state = 'unavailable' if company.get('status') != 'ok' else 'baseline' if not old or not old.get('captured_at') or not rows(old) else 'compared'
        result['channels'].append(dict(id=sid,label=company['name']+' financials',status=state,
            cik=cik,from_capture=(old or {}).get('captured_at'),to_capture=company.get('captured_at'),
            attempted_at=company.get('attempted_at'),error=company.get('error') if state=='unavailable' else None))
        if company.get('status') != 'ok':
            result['skipped'].append(sid)
            continue
        if not old or not old.get('captured_at') or not rows(old):
            result['baselines'].append(sid)
            continue
        context = dict(source_id=sid, publisher='SEC companyfacts · ' + company['name'],
                       cik=cik, from_capture=old['captured_at'], to_capture=company['captured_at'])
        prior = rows(old)
        for key, (row, point) in rows(company).items():
            previous_pair = prior.get(key)
            item = dict(context, title=company['name'] + ' · ' + row['label'],
                        url=point['url'], date=point['end'], start=point.get('start'),
                        unit=point['unit'], metric_id=row['id'], accession=point['accession'])
            if previous_pair:
                _, p = previous_pair
                if basis(p) != basis(point):
                    result['items'].append(dict(item, kind='Financial definition changed',
                        before=json.dumps(basis(p), sort_keys=True), after=json.dumps(basis(point), sort_keys=True),
                        comparison_boundary=True, previous_url=p['url'],
                        summary='Definition changed; numerical revision comparison suppressed.'))
                elif p['value'] != point['value']:
                    kind = 'Recalculated financial metric' if point.get('evidence_label') == 'derived_calculation' else 'Revised reported financial fact'
                    result['items'].append(dict(item, kind=kind,
                        before=p['value'], after=point['value'], previous_url=p['url'],
                        previous_accession=p['accession']))
            else:
                ends = [k[3] for k in prior if k[:2] == key[:2]]
                kind = 'New financial period' if ends and point['end'] > max(ends) else 'Newly available financial fact'
                result['items'].append(dict(item, kind=kind, before=None, after=point['value']))
    return result
