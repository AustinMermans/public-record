"""Bounded public-source collectors. No credentials; failure is data, never an empty success."""
from __future__ import annotations
import csv, hashlib, html, io, json, math, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
NOW = datetime.now(timezone.utc)
STAMP = NOW.isoformat(timespec='seconds')
UA = 'PublicRecord/0.1 (public disclosure research; github.com/AustinMermans/public-record)'

# Unit, adjustment and transformation are explicit; no proprietary series.
SERIES = [
 ('CPIAUCSL','Consumer prices','Inflation','BLS','Index, 1982–84=100','Monthly · seasonally adjusted','yoy'),
 ('CPILFESL','Core consumer prices','Inflation','BLS','Index, 1982–84=100','Monthly · seasonally adjusted','yoy'),
 ('PCEPILFE','Core PCE prices','Inflation','BEA','Index, 2017=100','Monthly · seasonally adjusted','yoy'),
 ('UNRATE','Unemployment rate','Labor','BLS','Percent','Monthly · seasonally adjusted','level'),
 ('PAYEMS','Nonfarm payrolls','Labor','BLS','Thousands of persons','Monthly · seasonally adjusted','change'),
 ('ICSA','Initial jobless claims','Labor','DOL','Persons','Weekly · seasonally adjusted','level'),
 ('GDPC1','Real GDP','Activity','BEA','Billions of chained 2017 dollars','Quarterly · seasonally adjusted annual rate','qoq'),
 ('RSAFS','Retail & food services sales','Activity','Census','Millions of dollars','Monthly · seasonally adjusted; nominal','yoy'),
 ('INDPRO','Industrial production','Activity','Federal Reserve','Index, 2017=100','Monthly · seasonally adjusted','yoy'),
 ('HOUST','Housing starts','Housing','Census / HUD','Thousands of units','Monthly · seasonally adjusted annual rate','level'),
 ('DGS10','10-year Treasury yield','Rates','Federal Reserve','Percent','Daily · not seasonally adjusted','level'),
 ('T10Y2Y','10-year minus 2-year spread','Rates','Federal Reserve','Percentage points','Daily · not seasonally adjusted','level'),
 ('DFF','Effective federal funds rate','Rates','Federal Reserve','Percent','Daily · not seasonally adjusted','level'),
]

def source(id, name, domain, url, parser, note, priority=2):
    return dict(id=id,name=name,domain=domain,url=url,parser=parser,note=note,priority=priority)

SOURCES = [
 source('bls','BLS release calendar','Economy','https://www.bls.gov/schedule/news_release/bls.ics','ics','Official scheduled releases. A scheduled date is not confirmation of publication.',1),
 source('bea','BEA release calendar','Economy','https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics','ics','Official GDP, income, PCE and international-account schedules.',1),
 source('fomc','FOMC meeting calendar','Policy','https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm','fomc','Meeting end dates; time is not supplied by this calendar. Projections occur at starred meetings.',1),
 source('treasury','Treasury auction announcements','Rates','https://www.treasurydirect.gov/TA_WS/securities/announced?format=json','treasury','Announced securities only. Competitive bidding deadline shown in Eastern time.',1),
 source('inspection','Federal Register · public inspection','Regulation','https://www.federalregister.gov/api/v1/public-inspection-documents/current.json','inspection','Filed for inspection; not yet necessarily published or effective. Publication date may change.',1),
 source('register','Federal Register · published','Regulation','https://www.federalregister.gov/api/v1/documents.json?per_page=100&order=newest','register','Latest 100 records, not the full Register. Read the official PDF before relying on legal effect.',1),
 source('fed','Federal Reserve press releases','Policy','https://www.federalreserve.gov/feeds/press_all.xml','rss','Publisher-defined rolling window of Board press releases.',1),
 source('sec','SEC · latest 8-K filings','Corporate','https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&count=100&output=atom','rss','Latest 100 8-K feed entries when accessible. Not an earnings calendar or all SEC filings.',2),
 source('cand','US District Court · Northern California','Legal','https://ecf.cand.uscourts.gov/cgi-bin/rss_outside.pl','rss','Selected court, rolling RSS window; docket links may require PACER. Event coverage is not a complete docket.',3),
 source('nysd','US District Court · Southern New York','Legal','https://ecf.nysd.uscourts.gov/cgi-bin/rss_outside.pl','rss','Selected court, rolling RSS window; docket links may require PACER. Event coverage is not a complete docket.',3),
 source('cacd','US District Court · Central California','Legal','https://ecf.cacd.uscourts.gov/cgi-bin/rss_outside.pl','rss','Selected court, rolling RSS window; docket links may require PACER. Event coverage is not a complete docket.',3),
] + [source('fred-'+s[0],s[1],'Economy',f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={s[0]}&cosd=2015-01-01','fred','Current revised history via FRED; capture time is not original release time.',1) | {'spec':s} for s in SERIES]

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>',' ',str(value or '')))).strip()

def safe_url(value):
    return str(value) if re.match(r'^https?://',str(value)) else ''

def key(*values):
    return hashlib.sha256('|'.join(map(str,values)).encode()).hexdigest()[:20]

def iso(value):
    if not value: return None
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        return d.isoformat() if d.tzinfo else d.date().isoformat()
    except ValueError:
        try: return parsedate_to_datetime(value).isoformat()
        except (ValueError, TypeError): return None

def record(s,title,url,date,kind,**extra):
    return dict(id=key(s['id'],url,title,date,kind),source_id=s['id'],publisher=s['name'],domain=s['domain'],title=clean(title),url=safe_url(url) or s['url'],date=date,kind=kind,captured_at=STAMP,priority=s['priority'],**extra)

def parse_ics(body,s):
    if 'BEGIN:VCALENDAR' not in body or 'END:VCALENDAR' not in body: raise ValueError('Response is not a complete iCalendar feed')
    unfolded=re.sub(r'\r?\n[ \t]', '', body)
    out=[]
    for chunk in unfolded.split('BEGIN:VEVENT')[1:]:
        fields={}
        for line in chunk.split('END:VEVENT')[0].splitlines():
            if ':' in line:
                left,val=line.split(':',1); fields[left.split(';')[0]]=(left,val)
        if 'SUMMARY' not in fields or 'DTSTART' not in fields: raise ValueError('Calendar event missing title or DTSTART')
        if fields.get('STATUS',('', ''))[1]=='CANCELLED': continue
        left,start=fields['DTSTART']
        if len(start)==8: date=datetime.strptime(start,'%Y%m%d').date().isoformat()
        else:
            d=datetime.strptime(start.rstrip('Z'),'%Y%m%dT%H%M%S')
            tz=re.search('TZID=([^;:]+)',left)
            zone=timezone.utc if start.endswith('Z') else ZoneInfo(tz.group(1) if tz else 'America/New_York')
            date=d.replace(tzinfo=zone).isoformat()
        title=fields['SUMMARY'][1].replace('\\,',',').replace('\\n',' ').replace('\\;',';')
        link=fields.get('URL',('',s['url']))[1]
        uid=fields.get('UID',('',key(title,date)))[1]
        item=record(s,title,link,date,'Scheduled release',schedule_uid=uid,summary='Publisher schedule; actual and consensus values are not supplied by this feed.')
        item['id']=key(s['id'],uid)
        out.append(item)
    if not out: raise ValueError('No calendar events parsed')
    return {'events':out}

def parse_fomc(body,s):
    parts=re.split(r'(20\d{2}) FOMC Meetings',body); out=[]
    for i in range(1,len(parts),2):
        year=parts[i]
        pairs=re.findall(r'fomc-meeting__month[^>]*>(.*?)</div>.*?fomc-meeting__date[^>]*>(.*?)</div>',parts[i+1],re.S)
        for month,days in pairs:
            month=clean(month).split('/')[-1]; days=clean(days)
            if 'notation' in days: continue
            nums=re.findall(r'\d+',days)
            if not nums: continue
            try: dt=datetime.strptime(f'{year} {month} {nums[-1]}','%Y %B %d').date().isoformat()
            except ValueError: continue
            title='FOMC meeting concludes'+(' · projections' if '*' in days else '')
            out.append(record(s,title,s['url'],dt,'Policy meeting',summary='Official meeting end date. Exact release time not provided by this calendar.'))
    if not out: raise ValueError('FOMC calendar structure not recognized')
    return {'events':out}

def parse_rss(body,s):
    root=ET.fromstring(body.lstrip('\ufeff'))
    items=root.findall('.//item') or root.findall('{http://www.w3.org/2005/Atom}entry')
    if not items: raise ValueError('No RSS/Atom entries; cannot establish an empty feed')
    out=[]
    for el in items:
        def get(tag): return el.findtext(tag) or el.findtext('{http://www.w3.org/2005/Atom}'+tag) or ''
        link=get('link')
        if not link:
            x=el.find('{http://www.w3.org/2005/Atom}link'); link=x.get('href','') if x is not None else ''
        title=get('title'); date=iso(get('pubDate') or get('updated') or get('published'))
        if not title or not safe_url(link): raise ValueError('Feed entry missing title or source link')
        kind='Docket entry' if s['domain']=='Legal' else '8-K filing' if s['id']=='sec' else 'Press release'
        description=get('description') or get('summary')
        item=record(s,title,link,date,kind,summary=clean(description)[:1200])
        item['document_urls']=list(dict.fromkeys(urljoin(link,html.unescape(u)) for u in re.findall(r'href=[\"\']([^\"\']+)',description) if safe_url(urljoin(link,html.unescape(u)))))
        guid=get('guid') or get('id')
        # A docket may have several entries with an identical case title and timestamp.
        # Preserve the publisher entry identity instead of deduplicating by case URL.
        if guid: item.update(id=key(s['id'],guid),source_entry_id=guid)
        out.append(item)
    merged={}
    for item in out:
        if item['id'] not in merged:
            item['entry_descriptions']=[item['summary']] if item['summary'] else []
            merged[item['id']]=item
        else:
            existing=merged[item['id']]
            existing['entry_descriptions']=list(dict.fromkeys(existing['entry_descriptions']+([item['summary']] if item['summary'] else [])))
            existing['document_urls']=list(dict.fromkeys(existing['document_urls']+item['document_urls']))
            existing['summary']=' · '.join(existing['entry_descriptions'])
    return {'records':list(merged.values()),'feed_entry_count':len(out)}

def parse_register(body,s):
    data=json.loads(body); items=data['results']; out=[]; events=[]
    if not isinstance(items,list): raise ValueError('Invalid results schema')
    for d in items:
        pi=s['parser']=='inspection'
        date=iso(d.get('filed_at')) if pi else d.get('publication_date')
        item=record(s,d['title'],d['html_url'],date,'Public inspection' if pi else d['type'],document_number=d['document_number'],summary=clean(d.get('abstract'))[:650],agencies=[a.get('name') or a.get('raw_name') for a in d.get('agencies',[])],pdf_url=safe_url(d.get('pdf_url')),publication_date=d.get('publication_date'))
        if d.get('type') in ('Rule','Proposed Rule','Presidential Document'): item['priority']=1
        else: item['priority']=2
        out.append(item)
        if pi and d.get('publication_date'):
            events.append(record(s,d['title'],d['html_url'],d['publication_date'],'Expected publication',summary='Expected Federal Register publication; not an effective date.',document_number=d['document_number']))
    return {'records':out,'events':events,'reported_total':data.get('count'),'coverage':'Full current inspection response' if s['parser']=='inspection' else 'Latest 100 records (bounded sample)'}

def parse_treasury(body,s):
    items=json.loads(body)
    if not isinstance(items,list) or not items: raise ValueError('Expected announced security records')
    out=[]
    for d in items:
        day=d['auctionDate'][:10]; date=day
        if d.get('closingTimeCompetitive'):
            t=datetime.strptime(d['closingTimeCompetitive'],'%I:%M %p').time()
            date=datetime.combine(datetime.fromisoformat(day).date(),t,ZoneInfo('America/New_York')).isoformat()
        pdf=d.get('pdfFilenameAnnouncement')
        link='https://www.treasurydirect.gov/auctions/announcements-data-results/announcement-results-press-releases/'
        if pdf: link=f"https://www.treasurydirect.gov/instit/annceresult/press/preanre/{d['announcementDate'][:4]}/{pdf}"
        amount=float(d['offeringAmount'])/1e9 if d.get('offeringAmount') else None
        amount_text=f'${amount:g}bn' if amount is not None else 'not supplied'
        item=record(s,f"{d['securityTerm']} Treasury {d['securityType']} auction",link,date,'Treasury auction',summary=f"CUSIP {d['cusip']} · announced offering {amount_text}. Time is the competitive bid deadline.",cusip=d['cusip'],offering_billions=amount)
        item['id']=key(s['id'],d['cusip'],d['announcementDate'],d['issueDate'])
        out.append(item)
    return {'events':out}

def parse_fred(body,s):
    sid,name,domain,publisher,unit,frequency,transform=s['spec']
    reader=csv.DictReader(io.StringIO(body)); out=[]
    if not reader.fieldnames or sid not in reader.fieldnames: raise ValueError('Expected FRED CSV schema, received another response')
    for row in reader:
        value=row[sid]; date=row.get('observation_date') or row.get('DATE')
        if not date: raise ValueError('Missing observation date')
        if value in ('','.'): continue
        num=float(value)
        if not math.isfinite(num): raise ValueError('Non-finite series value')
        out.append([date,num])
    out.sort()
    if len(out)<2: raise ValueError('Insufficient numerical observations')
    return {'series':[dict(id=sid,name=name,domain=domain,publisher=publisher,unit=unit,frequency=frequency,transform=transform,observations=out,url=f'https://fred.stlouisfed.org/series/{sid}',download_url=s['url'],captured_at=STAMP,source_id=s['id'],vintage='Current revised history, captured '+STAMP[:10])]}

PARSERS={'ics':parse_ics,'fomc':parse_fomc,'rss':parse_rss,'inspection':parse_register,'register':parse_register,'treasury':parse_treasury,'fred':parse_fred}

def collect(s):
    cache=DATA/'cache'/(s['id']+'.json')
    previous=json.loads(cache.read_text()) if cache.exists() else None
    status={k:v for k,v in s.items() if k not in ('parser','spec')}
    status.update(attempted_at=STAMP)
    try:
        r=subprocess.run(['curl','--http1.1','--fail','--location','--silent','--show-error','--max-time','40','--retry','1','--retry-delay','2','--user-agent',UA,s['url']],capture_output=True,timeout=90)
        if r.returncode: raise ValueError(r.stderr.decode(errors='replace').strip()[:250])
        encoding=re.search(br'encoding=[\"\']([^\"\']+)',r.stdout[:200])
        codec=encoding.group(1).decode('ascii') if encoding else 'utf-8-sig'
        body=r.stdout.decode(codec,errors='strict')
        parsed=PARSERS[s['parser']](body,s)
        digest=hashlib.sha256(r.stdout).hexdigest()
        # Content-addressed raw responses keep audit evidence without repeated identical files.
        raw=DATA/'raw'/s['id']/(digest+'.txt'); raw.parent.mkdir(parents=True,exist_ok=True)
        if not raw.exists(): raw.write_bytes(r.stdout)
        status.update(status='ok',last_success=STAMP,sha256=digest,raw_path=str(raw.relative_to(ROOT)),count=sum(len(parsed.get(k,[])) for k in ('events','records','series')))
        result={'source':status,**parsed}
        cache.parent.mkdir(parents=True,exist_ok=True); cache.write_text(json.dumps(result,ensure_ascii=False))
    except Exception as exc:
        if previous:
            status.update({k:previous['source'][k] for k in ('sha256','raw_path') if k in previous['source']})
        status.update(status='stale' if previous else 'unavailable',error=str(exc)[:250],last_success=previous['source'].get('last_success') if previous else None,count=previous['source'].get('count',0) if previous else 0)
        result={**(previous or {}),'source':status}
    print(s['id'],status['status'],status['count'],flush=True)
    return result

def main():
    DATA.mkdir(exist_ok=True)
    from changes import compare
    previous=json.loads((DATA/'current.json').read_text()) if (DATA/'current.json').exists() else None
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(collect,SOURCES))
    bundle={'schema_version':1,'captured_at':STAMP,'sources':[r['source'] for r in results]}
    for k in ('records','events','series'):
        items=[x for r in results for x in r.get(k,[])]
        bundle[k]=list({x['id']:x for x in items}.values())
    bundle['records'].sort(key=lambda x:date_order(x['date']),reverse=True)
    bundle['events'].sort(key=lambda x:date_order(x['date']))
    bundle['changes']=compare(previous,bundle)
    # Capture history starts here; never backfill a fictitious vintage.
    archive=DATA/'snapshots';archive.mkdir(exist_ok=True)
    text=json.dumps(bundle,ensure_ascii=False,separators=(',',':'))
    (archive/(NOW.strftime('%Y%m%dT%H%M%SZ')+'.json')).write_text(text)
    (DATA/'current.json').write_text(text)
    if not bundle['events'] or not bundle['series']: raise SystemExit('Core calendar or economic history absent; do not publish')

def date_order(value):
    if not value:return float('-inf')
    d=datetime.fromisoformat(value)
    if not d.tzinfo:d=d.replace(tzinfo=ZoneInfo('America/New_York'))
    return d.timestamp()

if __name__=='__main__': main()
