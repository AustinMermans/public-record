"""Public, bounded forecast extraction and dated ALFRED observations.

Separate captures: a research failure cannot replace the core data. ALFRED
dates are explicit sampled vintages, not a claim to reconstruct every release.
"""
from __future__ import annotations
import csv, hashlib, io, json, math, re, subprocess
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from publication_changes import compare_research

ROOT=Path(__file__).resolve().parents[1]
STAMP=datetime.now(timezone.utc).isoformat(timespec='seconds')
DATA=ROOT/'data/research'

class TableReader(HTMLParser):
    def __init__(self):
        super().__init__();self.tables=[];self.table=None;self.row=None;self.cell=None;self.ignore=0
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.table=[]
        if tag=='tr':self.row=[]
        if tag in ('th','td'):self.cell=''
        if tag=='sup':self.ignore+=1
    def handle_data(self,value):
        if self.cell is not None and not self.ignore:self.cell+=value
    def handle_endtag(self,tag):
        if tag=='sup':self.ignore=max(0,self.ignore-1)
        if tag in ('th','td') and self.row is not None:
            self.row.append(re.sub(r'\s+',' ',self.cell or '').strip());self.cell=None
        if tag=='tr' and self.table is not None and self.row is not None:self.table.append(self.row);self.row=None
        if tag=='table' and self.table is not None:self.tables.append(self.table);self.table=None

def fetch(url):
    p=subprocess.run(['curl','--http1.1','--fail','--location','--silent','--show-error','--max-time','40','--retry','1','--user-agent','PublicRecord/1.1 github.com/AustinMermans/public-record',url],capture_output=True,timeout=90)
    if p.returncode:raise ValueError(p.stderr.decode(errors='replace')[:160])
    raw=p.stdout;digest=hashlib.sha256(raw).hexdigest()
    path=DATA/'raw'/(digest+'.txt');path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():path.write_bytes(raw)
    return raw.decode('utf-8-sig'),dict(sha256=digest,raw_path=str(path.relative_to(ROOT)),captured_at=STAMP,url=url)

def vintage_csv(body,sid,asof):
    col=f"{sid}_{asof.replace('-','')}";reader=csv.DictReader(io.StringIO(body));out=[]
    if reader.fieldnames!=['observation_date',col]:raise ValueError('Requested ALFRED vintage not identified in response header')
    for row in reader:
        d=row['observation_date'];date.fromisoformat(d)
        if d>asof:raise ValueError('Vintage contains a future observation')
        if row[col] in ('','.'):continue
        v=float(row[col])
        if not math.isfinite(v):raise ValueError('Non-finite vintage value')
        out.append([d,v])
    if len(out)<2 or len(dict(out))!=len(out):raise ValueError('Invalid vintage observations')
    return sorted(out)

def collect_vintage(pair):
    sid,asof=pair;file=DATA/'vintages'/f'{sid}-{asof}.json'
    # Historical-vintage downloads are immutable local evidence, not re-fetched
    # on each daily collection. Each receipt retains its actual retrieval date.
    if file.exists():return json.loads(file.read_text())
    url=f'https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={sid}&vintage_date={asof}'
    try:
        body,receipt=fetch(url);points=vintage_csv(body,sid,asof)
        item=dict(series_id=sid,as_of=asof,observations=points,status='ok',**receipt)
        if sid=='GDPC1':item['unit']='Billions of chained '+('2012' if asof<'2023-09-28' else '2017')+' dollars'
        file.parent.mkdir(parents=True,exist_ok=True);file.write_text(json.dumps(item,separators=(',',':')))
        return item
    except Exception as exc:return dict(series_id=sid,as_of=asof,status='unavailable',error=str(exc),url=url)

def parse_sep(body,url):
    p=TableReader();p.feed(body)
    table=next((t for t in p.tables if any(r and r[0]=='Change in real GDP' for r in t)),None)
    if not table:raise ValueError('SEP median table not found')
    header=next((r for r in table if r and re.fullmatch(r'20\d{2}',r[0])),None)
    if not header:raise ValueError('SEP horizons missing')
    end=next((i for i,x in enumerate(header) if x.lower()=='longer run'),None)
    if end not in (3,4):raise ValueError('Unexpected SEP horizon layout')
    horizons=header[:end+1]
    years=[int(x) for x in horizons[:-1]]
    if years!=list(range(years[0],years[0]+len(years))):raise ValueError('Nonconsecutive SEP horizons')
    labels={'Change in real GDP':'Real GDP growth','Unemployment rate':'Unemployment','PCE inflation':'PCE inflation','Core PCE inflation':'Core PCE inflation','Federal funds rate':'Federal funds rate'}
    rows=[]
    for row in table:
        if not row or row[0] not in labels:continue
        values=[float(x) if x else None for x in row[1:1+len(horizons)]]
        if len(values)!=len(horizons):raise ValueError('Unexpected median count')
        rows.append(dict(name=labels[row[0]],values=values))
    if len(rows)!=5:raise ValueError('Expected five SEP variables')
    match=re.search(r'fomcprojtabl(\d{8})',url)
    published=datetime.strptime(match[1],'%Y%m%d').date().isoformat()
    return dict(id='sep',title='FOMC projections',published_at=published,horizons=horizons,rows=rows,unit='Percent',basis='Participant medians under their individual appropriate-policy assumptions. GDP and inflation: Q4/Q4; unemployment: Q4 average; policy rate: year-end target midpoint. Not a commitment or market forecast.')

def parse_gdpnow(body,url):
    # Tie estimate, target quarter and update date to the same compact source panel.
    text=re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',body)).replace('&nbsp;',' ')
    m=re.search(r'(-?\d+(?:\.\d+)?)\s*%+\s*(?:First|Second|Third|Fourth)[- ]Quarter GDPNow Estimate for\s*(20\d{2}):Q([1-4]).{0,100}?Updated:\s*([A-Z][a-z]+ \d{1,2}, 20\d{2})',text)
    if not m:raise ValueError('GDPNow estimate/target/date panel not recognized')
    return dict(id='gdpnow',title='Atlanta Fed GDPNow',value=float(m[1]),target=f'{m[2]} Q{m[3]}',published_at=datetime.strptime(m[4],'%B %d, %Y').date().isoformat(),unit='Percent · quarterly annualized',basis='Model estimate of real GDP growth, not an official Atlanta Fed forecast.')

def validate_gdpnow_capture(bundle, root=ROOT):
    """Reconcile displayed GDPNow fields to the retained, hash-identified page."""
    items=[item for item in bundle['forecasts'] if item.get('id')=='gdpnow']
    if len(items)!=1:raise ValueError('Expected exactly one GDPNow forecast')
    item=items[0]
    url='https://www.atlantafed.org/research-and-data/data/gdpnow'
    if item.get('url')!=url:raise ValueError('Unexpected GDPNow source URL')
    if item.get('status')=='unavailable':
        if any(key in item for key in ('value','target','published_at','raw_path','sha256')):
            raise ValueError('Unavailable GDPNow contains unverified values')
        return
    if item.get('status') not in ('ok','stale'):
        raise ValueError('Unexpected GDPNow status')
    digest=item.get('sha256','')
    if not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest):
        raise ValueError('Invalid GDPNow source digest')
    expected=f'data/research/raw/{digest}.txt'
    if item.get('raw_path')!=expected:raise ValueError('Invalid GDPNow raw path')
    raw=(Path(root)/expected).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('GDPNow source digest mismatch')
    try:
        parsed=parse_gdpnow(raw.decode('utf-8-sig'),url)
    except UnicodeError as exc:
        raise ValueError('GDPNow source encoding is invalid') from exc
    if any(item.get(key)!=value for key,value in parsed.items()):
        raise ValueError('GDPNow displayed fields do not match retained source')
    captured=datetime.fromisoformat(item['captured_at'])
    bundle_captured=datetime.fromisoformat(bundle['captured_at'])
    if captured.tzinfo is None or bundle_captured.tzinfo is None or captured>bundle_captured:
        raise ValueError('Invalid GDPNow capture clock')
    if parsed['published_at']>captured.date().isoformat():
        raise ValueError('GDPNow source date follows capture')

def forecast(id,url,parser):
    file=DATA/(id+'.json');old=json.loads(file.read_text()) if file.exists() else None
    try:
        if id=='sep':
            calendar,_=fetch(url)
            links=re.findall(r'(?:/monetarypolicy/)?(fomcprojtabl\d{8}\.htm)',calendar)
            links=[s for s in links if s[12:20]<=date.today().strftime('%Y%m%d')]
            if not links:raise ValueError('No dated accessible projections found')
            url='https://www.federalreserve.gov/monetarypolicy/'+sorted(set(links))[-1]
        body,receipt=fetch(url);item=dict(parser(body,url),status='ok',**receipt)
        file.write_text(json.dumps(item,separators=(',',':')));return item
    except Exception as exc:
        # A failed first capture is not a stale success on the next attempt.
        retained=old if old and old.get('id')==id and old.get('status') in ('ok','stale') and all(old.get(key) for key in ('sha256','raw_path','captured_at','published_at')) and (id!='gdpnow' or ('value' in old and old.get('target'))) else None
        return dict(retained or {'id':id,'url':url},status='stale' if retained else 'unavailable',error=str(exc),attempted_at=STAMP)

def main():
    DATA.mkdir(parents=True,exist_ok=True)
    current=DATA/'current.json'
    previous=json.loads(current.read_text()) if current.exists() else None
    (DATA/'comparison-baseline.json').write_text(json.dumps(previous,separators=(',',':')))
    dates=['2020-07-30']+[f'{y}-12-31' for y in range(2020,date.today().year)]
    pairs=[(sid,d) for sid in ('GDPC1','UNRATE','PAYEMS','CPIAUCSL') for d in dates]
    with ThreadPoolExecutor(max_workers=3) as pool:vintages=list(pool.map(collect_vintage,pairs))
    forecasts=[forecast('sep','https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm',parse_sep),forecast('gdpnow','https://www.atlantafed.org/research-and-data/data/gdpnow',parse_gdpnow)]
    bundle=dict(captured_at=STAMP,vintages=vintages,forecasts=forecasts)
    bundle['changes']=compare_research(previous,bundle)
    (DATA/'current.json').write_text(json.dumps(bundle,separators=(',',':')))
    (DATA/('capture-'+STAMP[:19].replace(':','')+'.json')).write_text(json.dumps(bundle,separators=(',',':')))
    print('Vintages:',sum(v['status']=='ok' for v in vintages),'/',len(vintages))
    for f in forecasts:print(f['id'],f['status'],f.get('error',''))

if __name__=='__main__':main()
