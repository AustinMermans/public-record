"""Compare observed source captures, never infer changes from an unavailable feed."""
import json

# Retrieval metadata is deliberately excluded. Changes in a measurement's
# definition require a new baseline, even if the series ID remains unchanged.
DEFINITION_FIELDS=('unit','frequency','adjustment','seasonal_adjustment','basis',
                   'definition','definition_version','methodology','methodology_version',
                   'geography','universe','stock_flow','price_basis','base_year')

def definition_label(series,fields):
    def value(key):
        item=series.get(key)
        if item is None:return 'not specified'
        return json.dumps(item,sort_keys=True,ensure_ascii=False) if isinstance(item,(dict,list)) else str(item)
    return '; '.join(f'{key}: {value(key)}' for key in fields)

def compare(previous,current):
    result={'from_capture':previous.get('captured_at') if previous else None,'to_capture':current['captured_at'],'items':[],'baselines':[],'skipped':[],'channels':[]}
    old_sources={s['id']:s for s in (previous or {}).get('sources',[])}
    for s in current['sources']:
        sid=s['id'];old=old_sources.get(sid)
        state='unavailable' if s['status']!='ok' else 'baseline' if not old or not old.get('last_success') else 'compared'
        result['channels'].append(dict(id=sid,label=s['name'],status=state,
            from_capture=(old or {}).get('last_success'),to_capture=s.get('last_success'),
            attempted_at=s.get('attempted_at'),error=s.get('error') if state=='unavailable' else None))
        if s['status']!='ok':result['skipped'].append(sid);continue
        if not old or not old.get('last_success'):
            result['baselines'].append(sid);continue
        context={'source_id':sid,'publisher':s['name'],'from_capture':old['last_success'],'to_capture':s['last_success']}
        def append(kind,title,url,**kwargs):result['items'].append(dict(context,kind=kind,title=title,url=url,**kwargs))
        for group in ('records','events'):
            before={r['id']:r for r in previous.get(group,[]) if r['source_id']==sid}
            after=[r for r in current.get(group,[]) if r['source_id']==sid]
            for r in after:
                prior=before.get(r['id'])
                if not prior:
                    append('Newly captured document' if group=='records' else 'Newly captured schedule',r['title'],r['url'],record_id=r['id'],date=r['date'])
                elif group=='events' and prior['date']!=r['date']:
                    append('Schedule changed',r['title'],r['url'],record_id=r['id'],before=prior['date'],after=r['date'])
                elif group=='records' and any(prior.get(k)!=r.get(k) for k in ('title','summary','date')):
                    append('Record metadata changed',r['title'],r['url'],record_id=r['id'],date=r['date'])
        before_series={x['id']:x for x in previous.get('series',[]) if x['source_id']==sid}
        for series in (x for x in current.get('series',[]) if x['source_id']==sid):
            old_series=before_series.get(series['id'])
            if not old_series:continue
            changed_fields=[key for key in DEFINITION_FIELDS if old_series.get(key)!=series.get(key)]
            if changed_fields:
                append('Series definition changed',series['name'],series['url'],
                       series_id=series['id'],changed_fields=changed_fields,comparison_boundary=True,
                       before=definition_label(old_series,changed_fields),after=definition_label(series,changed_fields),
                       summary='Numerical changes suppressed; this capture establishes a new definition baseline.')
                continue
            old_values=dict(old_series['observations']);last=max(old_values)
            for date,value in series['observations']:
                if date not in old_values:
                    append('New observation period' if date>last else 'Historical observation added',series['name'],series['url'],series_id=series['id'],date=date,before=None,after=value,unit=series['unit'])
                elif value!=old_values[date]:
                    append('Revision to observed value',series['name'],series['url'],series_id=series['id'],date=date,before=old_values[date],after=value,unit=series['unit'])
    return result
