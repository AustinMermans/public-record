"""Direct-source money-market and global-stress history; no API keys required."""
import csv
import io
import json
import math
import re
from datetime import date

NY_TERMS = 'https://www.newyorkfed.org/privacy/termsofuse'
NY_NOTICE = ('The reference rate data is subject to the Terms of Use posted at newyorkfed.org. '
             'The New York Fed is not responsible for publication of the reference rate data by Public Record, '
             'does not sanction or endorse any particular republication, and has no liability for your use.')
NY_AFFILIATION = ('Public Record is not affiliated with the New York Fed. The New York Fed does not sanction, '
                  'endorse, or recommend any products or services offered by Public Record.')
SOFR_NOTICE = ('SOFR data are calculated using data provided under license to the New York Fed by DTCC Solutions LLC, '
               'an affiliate of The Depository Trust & Clearing Corporation. Solutions, its affiliates, and third parties '
               'from which they obtained data have no liability for the content of this material.')

SOURCES = [dict(id='nyfed-'+kind.lower(), name='New York Fed · '+kind, domain='Funding',
                url=f'https://markets.newyorkfed.org/api/rates/{market}/{kind.lower()}/last/400.json',
                parser='nyfed', rate_type=kind, expected_count=400, provider_family='New York Fed', priority=1,
                note='Latest 400 published effective dates, not complete history. Rates may be revised; dates are not retrieval dates.')
           for kind, market in [('SOFR', 'secured'), ('EFFR', 'unsecured')]] + [
    dict(id='ofr-fsi', name='OFR · Financial Stress Index', domain='Credit', parser='ofr', priority=1,
         provider_family='Office of Financial Research', min_count=100,
         url='https://www.financialresearch.gov/financial-stress-index/data/fsi.csv',
         note='Global stress index and contributions since 2000. Normally two business days behind; history may be revised.')]


def valid_day(value, stamp):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Expected an ISO observation date')
    date.fromisoformat(value)
    if value > stamp[:10]:
        raise ValueError('Future observation date')
    return value


def number(value):
    if value is None or isinstance(value, bool) or value == '':
        raise ValueError('Missing numerical value')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Nonfinite numerical value')
    return result


def series(s, stamp, sid, name, unit, rows, **meta):
    return dict(id=sid, name=name, domain=s['domain'], publisher=s['provider_family'],
                unit=unit, frequency='Daily · not seasonally adjusted', adjustment='Not seasonally adjusted',
                transform='level', observations=rows, source_id=s['id'], download_url=s['url'],
                captured_at=stamp, publication_date=None, revision_policy='Publisher may revise history; retained captures record observed revisions.',
                vintage='Current publisher history, captured '+stamp[:10], **meta)


def parse_nyfed(body, s, stamp):
    rows = json.loads(body)['refRates']
    if not isinstance(rows, list) or len(rows) != s['expected_count']:
        raise ValueError('Incomplete New York Fed bounded response')
    observations, details, dates = [], [], set()
    for row in rows:
        day = valid_day(row['effectiveDate'], stamp)
        if day in dates or row['type'] != s['rate_type']:
            raise ValueError('Duplicate date or unexpected rate type')
        dates.add(day)
        rate = number(row['percentRate'])
        detail = dict(date=day, rate=rate, volume_billions=number(row['volumeInBillions']),
                      revision_indicator=str(row.get('revisionIndicator', '')))
        for percentile in (1, 25, 75, 99):
            detail['p'+str(percentile)] = number(row['percentPercentile'+str(percentile)])
        if not detail['p1'] <= detail['p25'] <= rate <= detail['p75'] <= detail['p99'] or detail['volume_billions'] < 0:
            raise ValueError('Invalid rate distribution or volume')
        observations.append([day, rate]); details.append(detail)
    observations.sort(); details.sort(key=lambda x: x['date'])
    kind = s['rate_type']
    return {'series': [series(s, stamp, 'NYFED-'+kind,
                             'Secured Overnight Financing Rate (SOFR)' if kind == 'SOFR' else 'Effective Federal Funds Rate (EFFR)',
                             'Percent', observations, url='https://www.newyorkfed.org/markets/reference-rates/'+kind.lower(),
                             geography='United States', universe='Treasury repo transactions' if kind == 'SOFR' else 'Federal funds transactions',
                             stock_flow='Overnight transaction rate', basis='Volume-weighted median', date_basis='Effective date',
                             coverage='Latest 400 published effective dates', details=details,
                             terms_url=NY_TERMS, attribution=NY_NOTICE.replace('reference rate data', kind+' data'), affiliation_notice=NY_AFFILIATION,
                             third_party_notice=SOFR_NOTICE if kind == 'SOFR' else '')]}


OFR_COLUMNS = [('OFR FSI', 'OFR-FSI', 'Global financial stress'),
               ('Credit', 'OFR-CREDIT', 'Credit contribution to global stress'),
               ('Equity valuation', 'OFR-EQUITY', 'Equity valuation contribution to global stress'),
               ('Safe assets', 'OFR-SAFE', 'Safe assets contribution to global stress'),
               ('Funding', 'OFR-FUNDING', 'Funding contribution to global stress'),
               ('Volatility', 'OFR-VOLATILITY', 'Volatility contribution to global stress'),
               ('United States', 'OFR-US', 'US contribution to global stress'),
               ('Other advanced economies', 'OFR-ADVANCED', 'Other advanced economies contribution to global stress'),
               ('Emerging markets', 'OFR-EMERGING', 'Emerging markets contribution to global stress')]


def parse_ofr(body, s, stamp):
    reader = csv.DictReader(io.StringIO(body))
    if not reader.fieldnames or not {'Date', *(c[0] for c in OFR_COLUMNS)} <= set(reader.fieldnames):
        raise ValueError('Expected complete OFR CSV schema')
    values = {column: [] for column, _, _ in OFR_COLUMNS}; dates = set()
    for row in reader:
        day = valid_day(row['Date'], stamp)
        if day in dates:
            raise ValueError('Duplicate OFR observation date')
        dates.add(day)
        for column in values:
            values[column].append([day, number(row[column])])
    if len(dates) < s['min_count']:
        raise ValueError('Insufficient OFR history')
    # Rounded contributions should reconcile within 0.005 points. Preserve,
    # rather than silently repair, larger discrepancies in publisher history.
    maps = {column: dict(rows) for column, rows in values.items()}
    quality = []
    for day in sorted(dates):
        for group, columns in [('Market', [c[0] for c in OFR_COLUMNS[1:6]]),
                               ('Regional', [c[0] for c in OFR_COLUMNS[6:]])]:
            residual = sum(maps[c][day] for c in columns) - maps['OFR FSI'][day]
            if abs(residual) > 0.005:
                quality.append(dict(date=day, decomposition=group, residual=round(residual, 6)))
    return {'series': [series(s, stamp, sid, name, 'Index points', sorted(values[column]),
                             url='https://www.financialresearch.gov/financial-stress-index/', geography='Global',
                             universe='OFR published 33-variable global stress index', stock_flow='Index' if sid == 'OFR-FSI' else 'Index contribution',
                             basis='Historical-average reference; zero is average stress, not zero risk', date_basis='Observation date',
                             coverage='Full history supplied by OFR, beginning in 2000', normal_lag='Two business days',
                             terms_url='https://www.financialresearch.gov/legal-notices/', attribution='Source: Office of Financial Research, Financial Stress Index.',
                             quality_notes=quality if sid == 'OFR-FSI' else [])
                       for column, sid, name in OFR_COLUMNS]}
