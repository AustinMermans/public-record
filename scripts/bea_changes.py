"""Differences between successful BEA release-history captures, not schedule events."""


def compare_bea_releases(previous, current):
    sid = 'bea-gdp-releases'
    old = previous if previous and previous.get('status') in ('ok', 'stale') else None
    channel = dict(id=sid, label='BEA · dated GDP estimates',
                   from_capture=(old or {}).get('captured_at'),
                   to_capture=current.get('captured_at'))
    result = dict(items=[], channels=[channel], baselines=[], skipped=[])
    if current.get('status') != 'ok' or not current.get('captured_at'):
        channel.update(status='unavailable', error='BEA release check failed; retained values are not a new comparison.')
        result['skipped'].append(sid)
        return result
    if not old or not old.get('releases'):
        channel['status'] = 'baseline'
        result['baselines'].append(sid)
        return result
    channel['status'] = 'compared'
    before = {(r['quarter'], r['stage']): r for r in old['releases']}
    current_by_key = {(r['quarter'], r['stage']): r for r in current['releases']}
    stages = ('advance','second','third')
    for row in current['releases']:
        key = (row['quarter'], row['stage'])
        if key in before:
            continue
        prior_stages = stages[:stages.index(row['stage'])]
        previous_stage = next((current_by_key.get((row['quarter'],stage)) for stage in reversed(prior_stages)), None)
        same_display = previous_stage is not None and previous_stage['display_value'] == row['display_value']
        result['items'].append(dict(source_id=sid, publisher='U.S. Bureau of Economic Analysis',
            kind='Newly captured GDP release', title=f"BEA real GDP · {row['quarter']} {row['stage']} estimate",
            date=row['published_at'], published_at=row['published_at'], target=row['quarter'],
            stage=row['stage'], unit='Percent · quarterly SAAR',
            before=previous_stage['value'] if previous_stage else None,
            after=row['value'], url=row['url'], previous_url=previous_stage['url'] if previous_stage else None,
            summary=('Dated BEA estimate. Same published precision as the prior stage; underlying revision may be hidden by rounding. Open the quarter record for BEA’s statement.' if same_display else
                     'Dated official GDP estimate captured from a BEA news release; previous value, where shown, is an earlier stage for the same quarter, not a prior-quarter growth rate.'),
            from_capture=old['captured_at'], to_capture=current['captured_at']))
    return result
