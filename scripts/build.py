"""Validate and publish only the explicit public website surface."""
import json, shutil
from pathlib import Path
from datetime import datetime
from versioning import validate_release
from validate_financials import validate_financials
from change_edition import assemble_changes
from fiscal import validate_fiscal
from banking import validate_banking
from spf import validate_capture as validate_spf
from publication_changes import compare_spf
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
    data['version']=validate_release(ROOT)
    research=ROOT/'data/research/current.json'
    corporate=ROOT/'data/corporate/current.json'
    financials=ROOT/'data/financials/current.json'
    if corporate.exists():
        data['corporate']=json.loads(corporate.read_text())
        for company in data['corporate']['companies']:
            assert len({f['id'] for f in company['filings']})==len(company['filings'])
            for filing in company['filings']:
                assert filing['url'].startswith('https://www.sec.gov/Archives/edgar/data/'+str(int(company['cik']))+'/')
                datetime.fromisoformat(filing['filed'])
    if financials.exists():
        data['financials']=json.loads(financials.read_text())
        validate_financials(data['financials'],data.get('corporate',{}).get('companies',[]))
    if research.exists():
        data['research']=json.loads(research.read_text())
        for v in data['research']['vintages']:
            if v['status']=='ok':
                assert v['observations'] and v['observations'][-1][0]<=v['as_of']
                assert v['observations']==sorted(v['observations'])
                assert len(dict(v['observations']))==len(v['observations'])
        for f in data['research']['forecasts']:
            if f.get('published_at'):assert f['published_at']<=data['research']['captured_at'][:10]
    spf=ROOT/'data/spf/current.json'
    if spf.exists():
        data['spf']=json.loads(spf.read_text())
        validate_spf(data['spf'],ROOT)
        baseline=ROOT/'data/spf/comparison-baseline.json'
        previous=json.loads(baseline.read_text()) if baseline.exists() else None
        data['spf']['changes']=compare_spf(previous,data['spf'])
    fiscal=ROOT/'data/fiscal/current.json'
    if fiscal.exists():
        data['fiscal']=json.loads(fiscal.read_text())
        validate_fiscal(data['fiscal'], raw_root=ROOT)
    banking=ROOT/'data/banking/current.json'
    if banking.exists():
        data['banking']=json.loads(banking.read_text())
        validate_banking(data['banking'], raw_root=ROOT)
    data['changes']=assemble_changes(data)
    if fiscal.exists():
        f=data['fiscal']
        data['sources'].append(dict(id='treasury-mts',name='US Treasury · Monthly Treasury Statement',
            domain='Fiscal',url=f['url'],status=f['status'],last_success=f.get('captured_at'),
            attempted_at=f.get('attempted_at'),count=len(f.get('metrics',[])),
            note='Federal receipts, outlays and net interest; matched fiscal-year-to-date periods. Not debt outstanding.',
            error=f.get('error')))
    if banking.exists():
        b=data['banking']
        data['sources'].append(dict(id='fdic-qbp',name='FDIC · Quarterly Banking Profile',
            domain='Banking',url=b['url'],status=b['status'],last_success=b.get('captured_at'),
            attempted_at=b.get('attempted_at'),count=len(b.get('metrics',[])),
            note='FDIC-reported all-insured aggregates; quarterly observations, not bank holding companies.',
            error=b.get('error')))
    if spf.exists():
        f=data['spf']
        data['sources'].append(dict(id='research-spf',name='Philadelphia Fed · Survey of Professional Forecasters',
            domain='Outlook',url='https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/median-forecasts',
            status=f['status'],last_success=f.get('captured_at'),attempted_at=f.get('attempted_at'),
            count=sum(len(x['points']) for x in f.get('series',{}).values()),
            note='Survey medians for released quarterly targets; historical workbook cells are not original-release file vintages.',
            error=f.get('error')))
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    for p in (ROOT/'site').iterdir():
        if p.is_file(): shutil.copy2(p,out/p.name)
    (out/'data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    (out/'.nojekyll').touch()
    (out/'release.json').write_text(json.dumps({'version':data['version'],'captured_at':data['captured_at'],'records':len(data['records']),'events':len(data['events']),'series':len(data['series'])}))
    print(f"Built Public Record {data['version']}: {len(data['events'])} events, {len(data['records'])} disclosures, {len(data['series'])} series")

if __name__=='__main__':main()
