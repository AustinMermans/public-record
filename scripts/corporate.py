"""Small explicit company universe. Sequential SEC requests, <=2 requests/sec."""
from __future__ import annotations
import hashlib,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/corporate'
STAMP=datetime.now(timezone.utc).isoformat(timespec='seconds')
# CIKs anchor identity. Tickers/names are read from SEC, never used for joins.
UNIVERSE=['0000320193','0000789019','0001018724','0000019617','0000104169','0000034088']
ITEMS={'1.01':'Material agreement','1.02':'Agreement terminated','1.03':'Bankruptcy or receivership','2.01':'Acquisition or asset disposal','2.02':'Results of operations and financial condition','2.03':'New financial obligation','2.05':'Exit or disposal costs','2.06':'Material impairment','3.01':'Listing or delisting notice','3.02':'Unregistered equity sale','4.01':'Auditor change','4.02':'Prior financial statements should not be relied on','5.02':'Director or executive change / compensation','5.07':'Shareholder vote','7.01':'Regulation FD disclosure','8.01':'Other events','9.01':'Financial statements and exhibits'}
FORMS={'10-K':'Annual business and financial report','10-Q':'Quarterly financial report','8-K':'Current-event report','DEF 14A':'Proxy statement: voting, governance and compensation','4':'Insider ownership transaction report','3':'Initial insider ownership report','5':'Annual insider ownership report','S-3':'Securities registration','S-8':'Employee-plan securities registration','144':'Notice of proposed securities sale'}

def parse_company(data,cik):
    if str(data['cik']).zfill(10)!=cik:raise ValueError('SEC company identity mismatch')
    recent=data['filings']['recent'];n=len(recent['accessionNumber'])
    required=('filingDate','reportDate','form','primaryDocument')
    if any(len(recent[k])!=n for k in required):raise ValueError('Mismatched SEC column lengths')
    filings=[]
    for i in range(n):
        form=recent['form'][i];base=form.removesuffix('/A')
        if base not in FORMS:continue
        accession=recent['accessionNumber'][i];document=recent['primaryDocument'][i]
        codes=[x.strip() for x in recent.get('items',['']*n)[i].split(',') if x.strip()]
        url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{document}'
        filings.append(dict(id=accession,form=form,amendment=form.endswith('/A'),filed=recent['filingDate'][i],accepted_at=recent.get('acceptanceDateTime',['']*n)[i] or None,report_period=recent['reportDate'][i] or None,items=codes,item_descriptions=[ITEMS.get(x,'Item '+x) for x in codes],description=FORMS[base],url=url))
    filings.sort(key=lambda f:(f['accepted_at'] or f['filed'],f['id']),reverse=True)
    quotas={'10-K':6,'10-Q':12,'8-K':20,'DEF 14A':4,'ownership':12,'other':6};selected=[]
    for f in filings:
        base=f['form'].removesuffix('/A');group=base if base in quotas else 'ownership' if base in ('3','4','5') else 'other'
        if quotas[group]>0:selected.append(f);quotas[group]-=1
    return dict(cik=cik,name=data['name'],tickers=data.get('tickers',[]),industry=data.get('sicDescription'),filings=selected,coverage='Recent-submission quotas: 6 annual, 12 quarterly, 20 current-event, 4 proxy, 12 ownership, 6 other selected forms per company; amendments count within quotas. Not complete history.')

def main():
    DATA.mkdir(parents=True,exist_ok=True);agent=os.environ.get('SEC_USER_AGENT','');companies=[]
    for cik in UNIVERSE:
        file=DATA/(cik+'.json');old=json.loads(file.read_text()) if file.exists() else None
        url=f'https://data.sec.gov/submissions/CIK{cik}.json'
        try:
            if '@' not in agent:raise ValueError('SEC identifying contact is not configured')
            p=subprocess.run(['curl','--http1.1','--fail','--silent','--show-error','--max-time','30','--user-agent',agent,url],capture_output=True,timeout=40)
            if p.returncode:raise ValueError('SEC request failed; HTTP/access or network error')
            company=parse_company(json.loads(p.stdout),cik);digest=hashlib.sha256(p.stdout).hexdigest()
            raw=DATA/'raw'/(digest+'.json');raw.parent.mkdir(exist_ok=True)
            if not raw.exists():raw.write_bytes(p.stdout)
            company.update(status='ok',captured_at=STAMP,url=url,sha256=digest,raw_path=str(raw.relative_to(ROOT)))
            file.write_text(json.dumps(company,separators=(',',':')))
        except Exception as exc:company=dict(old or {'cik':cik,'url':url,'filings':[]},status='stale' if old else 'unavailable',error=str(exc),attempted_at=STAMP)
        companies.append(company);time.sleep(.6)
        print(cik,company['status'],len(company['filings']))
    text=json.dumps(dict(captured_at=STAMP,companies=companies),separators=(',',':'))
    (DATA/'current.json').write_text(text)
    (DATA/('capture-'+STAMP[:19].replace(':','')+'.json')).write_text(text)

if __name__=='__main__':main()
