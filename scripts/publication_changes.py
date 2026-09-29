"""Pure comparisons of retained SEC submissions and published forecast captures.

Collection clocks belong to individual channels, not the enclosing bundle.
Disappearance from a rolling feed is deliberately not interpreted as withdrawal.
Cached ALFRED vintages are not refreshed publications and are excluded here.
"""
import json
import math


def _result(previous, current):
    return dict(from_capture=(previous or {}).get('captured_at'),
                to_capture=current.get('captured_at'), items=[], baselines=[],
                skipped=[], channels=[])


def _channel(result, sid, label, old, new, valid):
    channel = dict(id=sid, label=label, from_capture=(old or {}).get('captured_at'),
                   to_capture=(new or {}).get('captured_at'))
    # A stale prior capture still contains its last successful evidence. Its
    # attempted_at must never replace that successful comparison baseline.
    if not new or new.get('status') != 'ok' or not new.get('captured_at'):
        channel.update(status='unavailable', error='Current source capture unavailable; comparison skipped.')
        result['skipped'].append(sid)
    elif not valid(new):
        channel.update(status='unavailable', error='Current source structure invalid; comparison skipped.')
        result['skipped'].append(sid)
    elif not old or not old.get('captured_at') or not valid(old):
        channel['status'] = 'baseline'
        result['baselines'].append(sid)
    else:
        channel['status'] = 'compared'
    result['channels'].append(channel)
    return channel['status'] == 'compared'


def _indexed(records, key):
    return {record[key]: record for record in records}


def _text(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _filings_valid(company):
    filings = company.get('filings')
    return (isinstance(filings, list)
            and all(isinstance(f, dict) and f.get('id') and f.get('form')
                    and f.get('filed') and f.get('url') for f in filings)
            and len({f['id'] for f in filings}) == len(filings))


def _filing_metadata(filing):
    fields = ('form', 'amendment', 'filed', 'accepted_at', 'report_period',
              'description', 'url')
    result = {key: filing.get(key) for key in fields}
    # Feed ordering is not evidence of a filing change.
    for key in ('items', 'item_descriptions'):
        result[key] = sorted(filing.get(key) or [])
    return result


def compare_corporate(previous, current):
    """Compare accession identities within each issuer's successful captures."""
    result = _result(previous, current)
    before = _indexed((previous or {}).get('companies', []), 'cik')
    after = _indexed(current.get('companies', []), 'cik')
    for cik in sorted(before.keys() | after.keys()):
        old, company = before.get(cik), after.get(cik)
        name = (company or old).get('name') or cik
        sid = 'sec-company-' + cik
        if not _channel(result, sid, name, old, company, _filings_valid):
            continue
        context = dict(source_id=sid, publisher='SEC EDGAR · ' + name, cik=cik,
                       company=name, from_capture=old['captured_at'],
                       to_capture=company['captured_at'])
        prior = _indexed(old['filings'], 'id')
        for filing in sorted(company['filings'], key=lambda f: (f['filed'], f['id'])):
            earlier = prior.get(filing['id'])
            item = dict(context, title=name + ' · ' + filing['form'],
                        accession=filing['id'], record_id=filing['id'],
                        url=filing['url'], date=filing['filed'],
                        **{key: filing.get(key) for key in
                           ('form', 'filed', 'accepted_at', 'report_period',
                            'amendment', 'description', 'items', 'item_descriptions')})
            item['summary'] = filing.get('description') or ''
            if not earlier:
                kind = ('Newly captured filing amendment' if filing.get('amendment')
                        or filing['form'].endswith('/A') else 'Newly captured filing')
                result['items'].append(dict(item, kind=kind))
                continue
            old_fields, new_fields = _filing_metadata(earlier), _filing_metadata(filing)
            changed = [key for key in new_fields if old_fields[key] != new_fields[key]]
            if changed:
                result['items'].append(dict(item, kind='Filing metadata changed',
                    previous_url=earlier['url'], changed_fields=changed,
                    before=_text({key: old_fields[key] for key in changed}),
                    after=_text({key: new_fields[key] for key in changed})))
    return result


def _number_or_missing(value):
    return value is None or (isinstance(value, (int, float))
                             and not isinstance(value, bool) and math.isfinite(value))


def _forecast_valid(forecast):
    if not all(forecast.get(key) for key in ('id', 'title', 'url', 'published_at', 'unit', 'basis')):
        return False
    if forecast['id'] == 'gdpnow':
        return bool(forecast.get('target')) and 'value' in forecast and _number_or_missing(forecast['value'])
    if forecast['id'] != 'sep':
        return False
    horizons, rows = forecast.get('horizons'), forecast.get('rows')
    if (not isinstance(horizons, list) or not horizons
            or not all(isinstance(h, str) and h for h in horizons)
            or len(set(horizons)) != len(horizons)
            or not isinstance(rows, list) or not rows):
        return False
    names = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row['name']:
            return False
        values = row.get('values')
        if not isinstance(values, list) or len(values) != len(horizons) or not all(map(_number_or_missing, values)):
            return False
        names.append(row['name'])
    return len(set(names)) == len(names)


def _definition(forecast):
    return {key: forecast.get(key) for key in ('unit', 'basis', 'definition')}


def _forecast_context(old, new):
    return dict(source_id='research-' + new['id'], publisher=new['title'],
                forecast_id=new['id'], title=new['title'], url=new['url'],
                previous_url=old['url'], from_capture=old['captured_at'],
                to_capture=new['captured_at'], date=new['published_at'],
                published_at=new['published_at'], previous_published_at=old['published_at'],
                unit=new['unit'])


def _value_change(context, before, after, publication_changed, projection=False):
    if before == after:
        return None
    if before is None:
        kind = 'Forecast value became available'
    elif after is None:
        kind = 'Forecast value unavailable'
    elif not publication_changed:
        # A date-only publication stamp cannot distinguish an intraday model
        # update, a publisher correction, and a changed extraction.
        kind = 'Same-date forecast update'
    else:
        kind = 'Updated forecast projection' if projection else 'Updated forecast estimate'
    return dict(context, kind=kind, before=before, after=after)


def _compare_forecast(old, new):
    context = _forecast_context(old, new)
    if new['id'] == 'gdpnow':
        context.update(target=new['target'], period_label=new['target'], previous_target=old['target'])
    if _definition(old) != _definition(new):
        return [dict(context, kind='Forecast definition changed', comparison_boundary=True,
                     before=_text(_definition(old)), after=_text(_definition(new)),
                     changed_fields=[key for key in _definition(new)
                                     if _definition(old)[key] != _definition(new)[key]],
                     summary='Numerical comparison suppressed; this capture establishes a new definition baseline.')]
    publication_changed = old['published_at'] != new['published_at']
    items = []
    if new['id'] == 'gdpnow':
        if old['target'] != new['target']:
            items.append(dict(context, kind='Forecast target changed', comparison_boundary=True,
                              before=old['target'], after=new['target'],
                              summary='Different forecast targets; numerical revision comparison suppressed.'))
        else:
            change = _value_change(context, old['value'], new['value'], publication_changed)
            if change:
                items.append(change)
    else:
        prior = {row['name']: dict(zip(old['horizons'], row['values'])) for row in old['rows']}
        for row in sorted(new['rows'], key=lambda row: row['name']):
            for horizon, value in sorted(zip(new['horizons'], row['values'])):
                cell = dict(context, title=new['title'] + ' · ' + row['name'],
                            metric_id=row['name'], target=horizon, period_label=horizon)
                if row['name'] not in prior or horizon not in prior[row['name']]:
                    kind = 'New forecast measure' if row['name'] not in prior else 'New forecast horizon'
                    items.append(dict(cell, kind=kind, comparison_boundary=True,
                                      before=None, after=value,
                                      summary='New comparison target; not a revision to an earlier projection.'))
                else:
                    change = _value_change(cell, prior[row['name']][horizon], value,
                                           publication_changed, projection=True)
                    if change:
                        items.append(change)
    # Publication-only updates remain visible even if every comparable value is
    # unchanged. When values change, their records already carry both dates.
    if not items and publication_changed:
        items.append(dict(context, kind='Forecast publication updated',
                          before=old['published_at'], after=new['published_at']))
    metadata = [key for key in ('title', 'url') if old[key] != new[key]]
    if not items and metadata:
        items.append(dict(context, kind='Forecast metadata changed', changed_fields=metadata,
                          before=_text({key: old[key] for key in metadata}),
                          after=_text({key: new[key] for key in metadata})))
    return items


def compare_research(previous, current):
    """Compare GDPNow/SEP; exclude static ALFRED vintage caches explicitly."""
    result = _result(previous, current)
    result['excluded'] = ['vintages']
    before = _indexed((previous or {}).get('forecasts', []), 'id')
    after = _indexed(current.get('forecasts', []), 'id')
    for fid in sorted(before.keys() | after.keys()):
        old, forecast = before.get(fid), after.get(fid)
        label = (forecast or old).get('title') or fid
        sid = 'research-' + fid
        if _channel(result, sid, label, old, forecast, _forecast_valid):
            result['items'].extend(_compare_forecast(old, forecast))
    return result
