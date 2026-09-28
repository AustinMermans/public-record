"""Serialized SEC companyfacts retrieval with lossless, content-addressed evidence."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from corporate import UNIVERSE
from financial_changes import compare_financials

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/financials'


def decode_payload(raw, cik):
    if len(raw) > 100_000_000:
        raise ValueError('Companyfacts response exceeds bounded size')
    payload = json.loads(raw)
    if str(payload.get('cik', '')).zfill(10) != cik or not isinstance(payload.get('facts'), dict):
        raise ValueError('Companyfacts identity or schema mismatch')
    return payload


def public_error(error):
    # TimeoutExpired and OS/subprocess errors can embed the complete command,
    # including the private identifying User-Agent. Never persist that text.
    if isinstance(error, subprocess.TimeoutExpired):
        return 'SEC companyfacts request timed out'
    allowed = {'SEC identifying contact is not configured',
               'Companyfacts identity or schema mismatch',
               'Companyfacts response exceeds bounded size',
               'SEC companyfacts HTTP request failed'}
    if isinstance(error, ValueError) and str(error) in allowed:
        return str(error)
    return 'SEC companyfacts retrieval failed (' + type(error).__name__ + ')'


def fetch(cik, stamp, agent):
    path = DATA / 'receipts' / (cik+'.json')
    old = json.loads(path.read_text()) if path.exists() else None
    url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
    try:
        if '@' not in agent:
            raise ValueError('SEC identifying contact is not configured')
        response = subprocess.run(['curl','--http1.1','--fail','--silent','--show-error',
                                   '--max-time','30','--user-agent',agent,url],capture_output=True,timeout=40)
        if response.returncode:
            raise ValueError('SEC companyfacts HTTP request failed')
        decode_payload(response.stdout, cik)
        digest = hashlib.sha256(response.stdout).hexdigest()
        raw_path = DATA / 'raw' / (digest+'.json.gz')
        raw_path.parent.mkdir(parents=True,exist_ok=True)
        if not raw_path.exists():
            raw_path.write_bytes(gzip.compress(response.stdout,mtime=0))
        receipt = dict(cik=cik,status='ok',captured_at=stamp,last_success=stamp,attempted_at=stamp,url=url,
                       sha256=digest,hash_basis='Uncompressed response bytes',raw_path=str(raw_path.relative_to(ROOT)))
    except Exception as error:
        receipt = dict(old or {'cik':cik,'url':url},status='stale' if old and old.get('raw_path') else 'unavailable',
                       attempted_at=stamp,error=public_error(error))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(receipt,separators=(',',':')))
    return receipt


def load_raw(receipt):
    raw = gzip.decompress((ROOT/receipt['raw_path']).read_bytes())
    if hashlib.sha256(raw).hexdigest() != receipt['sha256']:
        raise ValueError('Raw companyfacts hash mismatch')
    return decode_payload(raw,receipt['cik'])


def capture_metadata(companies, processed_at):
    return dict(captured_at=max((c['captured_at'] for c in companies if c.get('captured_at')),default=None),
                attempted_at=max((c['attempted_at'] for c in companies if c.get('attempted_at')),default=None),
                processed_at=processed_at)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch-only',action='store_true',help='Retain raw evidence without normalizing or publishing it')
    parser.add_argument('--reparse',action='store_true',help='Normalize retained evidence without a new retrieval claim')
    args=parser.parse_args()
    if args.fetch_only and args.reparse:parser.error('Choose only one mode')
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
    DATA.mkdir(parents=True,exist_ok=True)
    companies={c['cik']:c for c in json.loads((ROOT/'data/corporate/current.json').read_text())['companies']}
    normalized=[]
    old_bundle_path=DATA/'current.json'
    old_bundle=json.loads(old_bundle_path.read_text()) if old_bundle_path.exists() else None
    baseline_path=DATA/'comparison-baseline.json'
    if args.reparse:
        # Rebuilding retained evidence must not compare the capture to itself
        # and erase the last observed changes.
        baseline=json.loads(baseline_path.read_text()) if baseline_path.exists() else None
    else:
        baseline=old_bundle
        if not args.fetch_only:
            baseline_path.write_text(json.dumps(baseline,separators=(',',':')))
    if not args.fetch_only:
        from financials import normalize_company
    for cik in UNIVERSE:
        if args.reparse:
            p=DATA/'receipts'/(cik+'.json')
            receipt=json.loads(p.read_text()) if p.exists() else dict(cik=cik,status='unavailable',error='No retained response')
        else:
            receipt=fetch(cik,stamp,os.environ.get('SEC_USER_AGENT',''))
            # Applies even to failures, and prevents concurrent SEC requests.
            time.sleep(.65)
        if args.fetch_only:
            print(cik,receipt['status'],flush=True);continue
        cache=DATA/(cik+'.json')
        previous=json.loads(cache.read_text()) if cache.exists() else None
        try:
            if not receipt.get('raw_path'):raise ValueError(receipt.get('error','No retained response'))
            result=normalize_company(load_raw(receipt),companies[cik],receipt['captured_at'])
            result.update(receipt)
            result['last_success']=receipt.get('last_success',receipt['captured_at'])
            result['processed_at']=stamp
            cache.write_text(json.dumps(result,separators=(',',':')))
        except Exception as error:
            result=dict(previous or {'cik':cik,'name':companies[cik].get('name',cik),'sections':[],
                                     'qa_flags':[],'validation_checks':[],'source_index':[]},
                        status='stale' if previous else 'unavailable',attempted_at=receipt.get('attempted_at'),
                        processed_at=stamp,error=str(error))
        normalized.append(result)
        print(cik,result['status'],len(result.get('sections',[])),flush=True)
    if args.fetch_only:return
    bundle=dict(schema_version=1,companies=normalized,**capture_metadata(normalized,stamp))
    bundle['changes']=compare_financials(baseline,bundle)
    text=json.dumps(bundle,separators=(',',':'))
    (DATA/'current.json').write_text(text)
    if not args.reparse:
        (DATA/('capture-'+stamp[:19].replace(':','')+'.json')).write_text(text)


if __name__=='__main__':main()
