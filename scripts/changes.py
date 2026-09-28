"""Compare observed source captures, never infer changes from an unavailable feed."""
def compare(previous,current):
    result={'from_capture':previous.get('captured_at') if previous else None,'to_capture':current['captured_at'],'items':[],'baselines':[],'skipped':[]}
    old_sources={s['id']:s for s in (previous or {}).get('sources',[])}
    for s in current['sources']:
        sid=s['id'];old=old_sources.get(sid)
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
            old_values=dict(old_series['observations']);last=max(old_values)
            for date,value in series['observations']:
                if date not in old_values:
                    append('New observation period' if date>last else 'Historical observation added',series['name'],series['url'],series_id=series['id'],date=date,before=None,after=value,unit=series['unit'])
                elif value!=old_values[date]:
                    append('Revision to observed value',series['name'],series['url'],series_id=series['id'],date=date,before=old_values[date],after=value,unit=series['unit'])
    return result
