"""Validate and publish only the explicit public website surface."""
import json, shutil
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]

def validate(data):
    assert data['schema_version']==1
    datetime.fromisoformat(data['captured_at'])
    sources={s['id']:s for s in data['sources']}
    assert len(sources)==len(data['sources'])
    for group in ('events','records','series'):
        assert len({r['id'] for r in data[group]})==len(data[group]),f'Duplicate {group} ID'
        for r in data[group]:
            assert r['source_id'] in sources
            assert r['url'].startswith(('https://','http://'))
            assert r['captured_at']
            if r.get('date'): datetime.fromisoformat(r['date'])
    for s in data['series']:
        assert s['observations']==sorted(s['observations'])
        assert len({x[0] for x in s['observations']})==len(s['observations'])
        assert len(s['observations'])>1
        assert s['observations'][-1][0]<=data['captured_at'][:10],s['id']+' has future observations'
    assert data['events'] and data['records'] and data['series'],'Core data absent'

def main():
    data=json.loads((ROOT/'data/current.json').read_text()); validate(data)
    data['version']=(ROOT/'VERSION').read_text().strip()
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    for p in (ROOT/'site').iterdir():
        if p.is_file(): shutil.copy2(p,out/p.name)
    (out/'data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    (out/'.nojekyll').touch()
    (out/'release.json').write_text(json.dumps({'version':data['version'],'captured_at':data['captured_at'],'records':len(data['records']),'events':len(data['events']),'series':len(data['series'])}))
    print(f"Built Public Record {data['version']}: {len(data['events'])} events, {len(data['records'])} disclosures, {len(data['series'])} series")

if __name__=='__main__':main()
