"""Reprocess retained raw evidence after a parser correction; no new source claims."""
import json
import collect as c

def main():
    bundle=json.loads((c.DATA/'current.json').read_text())
    specs={s['id']:s for s in c.SOURCES}; sources=[]; groups={k:[] for k in ('events','records','series')}
    for status in bundle['sources']:
        spec=specs.get(status['id'])
        cache=c.DATA/'cache'/(status['id']+'.json')
        if not spec or not cache.exists():sources.append(status);continue
        old=json.loads(cache.read_text()); evidence=old['source'];raw=(c.ROOT/evidence['raw_path']).read_bytes()
        enc=c.re.search(br'encoding=[\"\']([^\"\']+)',raw[:200]);codec=enc.group(1).decode() if enc else 'utf-8-sig'
        c.STAMP=evidence['last_success']
        parsed=c.PARSERS[spec['parser']](raw.decode(codec),spec)
        evidence['count']=sum(len(parsed.get(k,[])) for k in groups)
        cache.write_text(json.dumps({'source':evidence,**parsed},ensure_ascii=False))
        sources.append(evidence)
        for k in groups:groups[k].extend(parsed.get(k,[]))
    bundle['sources']=sources
    for k,items in groups.items():bundle[k]=list({x['id']:x for x in items}.values())
    bundle['records'].sort(key=lambda x:c.date_order(x['date']),reverse=True)
    bundle['events'].sort(key=lambda x:c.date_order(x['date']))
    bundle['processed_at']=c.NOW.isoformat(timespec='seconds')
    (c.DATA/'current.json').write_text(json.dumps(bundle,ensure_ascii=False,separators=(',',':')))
    print('Reprocessed retained evidence; source capture times preserved')

if __name__=='__main__':main()
