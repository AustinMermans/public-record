"""Validate and publish only the explicit public website surface."""
import json, re, shutil
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from versioning import validate_release
from validate_financials import validate_financials
from change_edition import assemble_changes
from fiscal import validate_fiscal
from banking import validate_banking
from spf import validate_capture as validate_spf
from business_briefs import validate_capture as validate_business_briefs
from bea_releases import validate_capture as validate_bea_releases
from bea_pce import validate_capture as validate_bea_pce
from energy import validate_capture as validate_energy
from inflation import validate_capture as validate_inflation
from publication_changes import compare_spf
from research import validate_gdpnow_capture
from earnings_dossiers import assemble_dossiers
from issuer_reads import attach_issuer_reads
ROOT=Path(__file__).resolve().parents[1]
EASTERN=ZoneInfo('America/New_York')

def event_order(event):
    value=event['date']
    if len(value)>10:
        instant=datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(EASTERN)
        return (instant.date().isoformat(),instant.hour*60+instant.minute,event['id'])
    window=re.match(r'After (\d{1,2}):(\d{2}) ([ap])\.m\. ET',event.get('time_window',''))
    if window:
        hour=int(window[1])%12+(12 if window[3]=='p' else 0)
        return (value,hour*60+int(window[2]),event['id'])
    return (value,24*60,event['id'])

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
    business_briefs=ROOT/'data/business_briefs/current.json'
    if business_briefs.exists():
        if 'corporate' not in data:
            raise ValueError('Business briefs require corporate coverage')
        data['business_briefs']=json.loads(business_briefs.read_text())
        validate_business_briefs(data['business_briefs'],ROOT,data['corporate'])
    if financials.exists():
        data['financials']=json.loads(financials.read_text())
        validate_financials(data['financials'],data.get('corporate',{}).get('companies',[]))
    if 'corporate' in data and 'business_briefs' in data and 'financials' in data:
        data['earnings_dossiers']=assemble_dossiers(data['corporate'],data['business_briefs'],data['financials'],ROOT)
        issuer_catalogue=ROOT/'data/issuer_reads/catalog.json'
        if issuer_catalogue.exists():
            data['earnings_dossiers']=attach_issuer_reads(
                data['earnings_dossiers'],data['business_briefs'],
                json.loads(issuer_catalogue.read_text()),ROOT)
    if research.exists():
        data['research']=json.loads(research.read_text())
        validate_gdpnow_capture(data['research'],ROOT)
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
    bea_releases=ROOT/'data/bea_releases/current.json'
    if bea_releases.exists():
        data['bea_releases']=json.loads(bea_releases.read_text())
        validate_bea_releases(data['bea_releases'],ROOT)
    bea_pce=ROOT/'data/bea_pce/current.json'
    if bea_pce.exists():
        data['bea_pce']=json.loads(bea_pce.read_text())
        validate_bea_pce(data['bea_pce'],ROOT)
    energy=ROOT/'data/energy/current.json'
    if energy.exists():
        data['energy']=json.loads(energy.read_text())
        validate_energy(data['energy'],ROOT)
        e=data['energy']
        product_gaps=', '.join(sorted(e.get('history_errors', {})))
        partial=bool(product_gaps or e.get('schedule_error'))
        data['sources'].append(dict(id='eia-wpsr',name='EIA · Weekly Petroleum Status Report',
            domain='Economy',url=e['table_url'],
            status='partial' if e['status']=='ok' and partial else e['status'],
            last_success=e.get('captured_at'),attempted_at=e.get('attempted_at'),
            count=len(e.get('metrics',[])),
            note='Three Table 4 stock levels; current-edition histories, not original report vintages.'
                +(f' Missing history: {product_gaps}.' if product_gaps else '')
                +(' Release schedule unavailable.' if e.get('schedule_error') else ''),
            error=e.get('error') or e.get('schedule_error')))
        if e['status']=='ok':
            for scheduled in e.get('release_schedule', []):
                report_day=datetime.fromisoformat(scheduled['report_week']).date()
                data['events'].append(dict(id='eia-wpsr-'+scheduled['report_week'],
                    source_id='eia-wpsr',publisher='EIA · Weekly Petroleum Status Report',
                    domain='Economy',title='Weekly Petroleum Status Report · week ending '
                    +f'{report_day:%b} {report_day.day}, {report_day.year}',
                    url=scheduled['url'],date=scheduled['date'],
                    kind='Scheduled release',captured_at=e['captured_at'],priority=1,
                    time_window=scheduled['time_window'],report_week=scheduled['report_week'],
                    summary='Expected release of Tables 1–14 '
                    +scheduled['time_window'][0].lower()+scheduled['time_window'][1:]
                    +('; '+scheduled['holiday']+' exception' if scheduled['holiday'] else '')
                    +'. Schedule only; not confirmation of publication.'))
        data['events'].sort(key=event_order)
        validate(data)
    inflation=ROOT/'data/inflation/current.json'
    if inflation.exists():
        data['inflation']=json.loads(inflation.read_text())
        validate_inflation(data['inflation'],ROOT)
        item=data['inflation']
        data['sources'].append(dict(id='cleveland-inflation-nowcast',
            name='Cleveland Fed · Inflation Nowcasting',domain='Outlook',url=item['url'],
            status='partial' if item['status']=='ok' and item.get('history_error') else item['status'],last_success=item.get('captured_at'),
            attempted_at=item.get('attempted_at'),count=len(item.get('rows',[])),
            note='Daily model estimates for CPI and PCE, not official inflation releases or survey consensus. Publisher history is its current edition; our original capture history begins at collection.',
            error=item.get('error') or item.get('history_error')))
    data['changes']=assemble_changes(data)
    if business_briefs.exists():
        b=data['business_briefs']
        counts={status:sum(x['status']==status for x in b['briefs']) for status in ('ok','stale','metadata_only')}
        data['sources'].append(dict(id='sec-business-briefs',name='SEC EDGAR · Issuer Item 2.02 exhibits',
            domain='Business',url='https://www.sec.gov/edgar/search/',
            status='ok' if counts['ok']==len(b['briefs']) else ('partial' if counts['ok'] or counts['stale'] else 'unavailable'),
            last_success=max((x['captured_at'] for x in b['briefs'] if x.get('captured_at')),default=None),
            attempted_at=b.get('attempted_at'),count=counts['ok'],
            note=f"Newest two selected Item 2.02 8-Ks per covered issuer; exact EX-99.1 text only. {counts['ok']} current, {counts['stale']} stale, {counts['metadata_only']} metadata-only. Not independent news or a complete filing feed."))
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
    if bea_releases.exists():
        b=data['bea_releases']
        data['sources'].append(dict(id='bea-gdp-releases',name='BEA · dated GDP estimates',
            domain='Economy',url='https://www.bea.gov/news/schedule/full',status=b['status'],
            last_success=b.get('last_success'),attempted_at=b.get('attempted_at'),
            count=len(b.get('releases',[])),
            note='Verified real GDP growth in dated advance, second and third news releases. Recent targets only; separate from current-revised FRED history.',
            error=b.get('error')))
    if bea_pce.exists():
        b=data['bea_pce']
        data['sources'].append(dict(id='bea-pce-releases',name='BEA · dated PCE price releases',
            domain='Economy',url='https://www.bea.gov/news/schedule/full',status=b['status'],
            last_success=b.get('last_success'),attempted_at=b.get('attempted_at'),
            count=len(b.get('releases',[])),
            note='Verified headline and core PCE monthly/yearly rates from dated Personal Income and Outlays news releases; separate from revised indexes and Cleveland Fed model estimates.',
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
