"""Read-only channel discovery; run manually, never part of the published site."""
import concurrent.futures, json, subprocess
URLS = {
 'bls':'https://www.bls.gov/schedule/news_release/bls.ics',
 'bea':'https://www.bea.gov/news/schedule/icalendar',
 'census':'https://www.census.gov/economic-indicators/',
 'inspection':'https://www.federalregister.gov/api/v1/public-inspection-documents/current.json',
 'register':'https://www.federalregister.gov/api/v1/documents.json?per_page=100&order=newest',
 'fed':'https://www.federalreserve.gov/feeds/press_all.xml',
 'fred':'https://fred.stlouisfed.org/graph/?g=1&cosd=2019-01-01&id=UNRATE&coed=2026-09-28',
 'fredcsv':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNRATE&cosd=2019-01-01',
 'sec':'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&count=100&output=atom',
 'cand':'https://ecf.cand.uscourts.gov/cgi-bin/rss_outside.pl',
 'treasury':'https://www.treasurydirect.gov/TA_WS/securities/announced?format=json',
 'fomc':'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm',
}
def probe(item):
    key,url=item
    r=subprocess.run(['curl','-LsS','--max-time','35','-A','PublicRecord/0.0 (public disclosure research)',url],capture_output=True,text=True)
    body=r.stdout
    from pathlib import Path
    p=Path(__file__).resolve().parents[1]/'data'/'discovery';p.mkdir(parents=True,exist_ok=True)
    (p/(key+'.txt')).write_text(body)
    try:
        data=json.loads(body)
        shape=list(data)[:12] if isinstance(data,dict) else data[:1]
    except Exception:
        import re
        shape=re.findall(r'(?:href|src)=["\']([^"\']*(?:ics|calendar|json)[^"\']*)',body)[:20] or body[:350]
    return dict(id=key,bytes=len(body),exit=r.returncode,shape=shape,error=r.stderr[:200])
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for result in pool.map(probe,URLS.items()): print(json.dumps(result),flush=True)
