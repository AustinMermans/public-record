import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from change_edition import assemble_changes, calendar_day, filing_identity
from changes import compare
from publication_changes import compare_corporate, compare_research

CIK = '0000320193'
ACCESSION = '0000320193-26-000001'
URL = 'https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/report.htm'


def channel(sid, start='2026-09-28T10:00:00Z', end='2026-09-28T11:00:00Z'):
    return dict(id=sid, label=sid, status='compared', from_capture=start, to_capture=end)


def bundle(sid, items):
    c = channel(sid)
    return dict(channels=[c], items=[dict(source_id=sid, publisher=sid,
        title='Example', kind='Revision to observed value', url='https://example.gov',
        from_capture=c['from_capture'], to_capture=c['to_capture'], **x) for x in items])


class EditionTests(unittest.TestCase):
    def test_four_developments_keep_windows_and_detail_links(self):
        old = dict(captured_at='2026-09-28T10:00:00Z', sources=[dict(id='fred-CPIAUCSL',
            name='CPI', status='ok', last_success='2026-09-28T09:01:00Z')], records=[], events=[],
            series=[dict(id='CPIAUCSL', source_id='fred-CPIAUCSL', name='CPI', unit='Index',
                         url='https://fred.stlouisfed.org/series/CPIAUCSL', observations=[['2026-08-01', 100]])])
        now = copy.deepcopy(old)
        now['captured_at'] = '2026-09-28T11:00:00Z'
        now['sources'][0]['last_success'] = '2026-09-28T10:01:00Z'
        now['series'][0]['observations'][0][1] = 101
        now['changes'] = compare(old, now)
        issuer = dict(cik=CIK, name='Apple', status='ok', captured_at='2026-09-28T09:02:00Z', filings=[])
        company = dict(issuer, captured_at='2026-09-28T10:02:00Z', filings=[dict(
            id=ACCESSION, form='10-Q', filed='2026-09-28', url=URL)])
        now['corporate'] = dict(companies=[company])
        now['corporate']['changes'] = compare_corporate(dict(companies=[issuer]), now['corporate'])
        forecast = dict(id='gdpnow', title='GDPNow', url='https://www.atlantafed.org',
            unit='Percent', basis='SAAR', target='2026 Q3', published_at='2026-09-28',
            status='ok', captured_at='2026-09-28T09:03:00Z', value=2)
        now['research'] = dict(forecasts=[dict(forecast, captured_at='2026-09-28T10:03:00Z', value=3)])
        now['research']['changes'] = compare_research(dict(forecasts=[forecast]), now['research'])
        fin = bundle('sec-financials-'+CIK, [dict(cik=CIK, accession=ACCESSION, before=5, after=6)])
        fin['items'][0].update(url=URL, kind='Revised reported financial fact')
        now['financials'] = dict(changes=fin)
        original = copy.deepcopy(now)
        result = assemble_changes(now)
        self.assertEqual(now, original)
        self.assertEqual(len(result['items']), 4)
        self.assertEqual(len(result['channels']), 4)
        receipts = {c['id']: c for c in result['channels']}
        for item in result['items']:
            receipt = receipts[item['source_id']]
            self.assertEqual(item['from_capture'], receipt['from_capture'])
            self.assertEqual(item['to_capture'], receipt['to_capture'])
            self.assertTrue(item['detail_url'].startswith('#'))
        economic = next(x for x in result['items'] if x['domain']=='Economic data')
        self.assertIn('transform=level', economic['detail_url'])
        self.assertIn('period=all', economic['detail_url'])
        firms = [x for x in result['items'] if x['domain']=='Companies']
        self.assertEqual(len({x['development_id'] for x in firms}), 1)
        self.assertTrue(all(x['detail_url']=='#company?cik='+CIK for x in firms))
        self.assertEqual(next(x for x in result['items'] if x['domain']=='Outlook')['detail_url'], '#outlook?forecast=gdpnow')
        self.assertEqual(result['items'], assemble_changes(now)['items'])

    def test_sec_feed_and_issuer_paths_share_verified_identity(self):
        self.assertEqual(filing_identity(URL), (CIK, ACCESSION))
        self.assertEqual(filing_identity(URL.rsplit('/', 1)[0]+'/'+ACCESSION+'-index.htm'), (CIK, ACCESSION))
        for bad in (URL.replace('https:', 'http:'), URL.replace('www.sec.gov', 'www.sec.gov.evil.com'),
                    URL.replace('/000032019326000001/', '/short/')):
            self.assertIsNone(filing_identity(bad))

    def test_conflicting_sec_identity_fails_closed(self):
        data = dict(changes=bundle('sec', [dict(cik='0000000001')]))
        data['changes']['items'][0]['url'] = URL
        with self.assertRaisesRegex(ValueError, 'CIK differs'):
            assemble_changes(data)

    def test_legacy_unknown_comparison_not_reported_no_change(self):
        data = dict(changes=dict(items=[], baselines=[]), sources=[dict(id='fred-x', name='X',
                    status='ok', last_success='2026-09-28T10:00:00Z')])
        result = assemble_changes(data)
        self.assertEqual(result['channels'][0]['status'], 'unavailable')
        self.assertIsNone(result['channels'][0]['from_capture'])
        self.assertEqual(result['skipped'], ['fred-x'])

    def test_calendar_uses_eastern_day_and_handles_metadata(self):
        self.assertEqual(calendar_day('2026-09-29T01:00:00Z'), '2026-09-28')
        self.assertEqual(calendar_day('2026-09-29'), '2026-09-29')
        self.assertIsNone(calendar_day({'date': '2026-09-29'}))
        data = dict(changes=bundle('bea', [dict(date='2026-09-29T01:00:00Z')]))
        self.assertEqual(assemble_changes(data)['items'][0]['detail_url'], '#calendar?month=2026-09&day=2026-09-28')

    def test_legacy_financial_receipts_not_invented_as_first_baseline(self):
        sid = 'sec-financials-'+CIK
        financials = dict(companies=[dict(cik=CIK, name='Apple', status='ok', captured_at='2026-09-28T11:00:00Z')],
            changes=dict(from_capture='2026-09-28T10:00:00Z', to_capture='2026-09-28T11:00:00Z', items=[], baselines=[]))
        result = assemble_changes(dict(financials=financials))
        self.assertEqual(result['channels'][0]['status'], 'unavailable')
        self.assertFalse(result['baselines'])
        financials['changes']['items'] = bundle(sid, [dict(before=1, after=2)])['items']
        result = assemble_changes(dict(financials=financials))
        self.assertEqual(result['channels'][0]['status'], 'compared')
        self.assertEqual(result['channels'][0]['from_capture'], '2026-09-28T10:00:00Z')

    def test_inspection_records_and_expected_events_have_distinct_destinations(self):
        data = dict(changes=bundle('inspection', [dict(record_id='document', date='2026-09-28'),
            dict(record_id='event', date='2026-09-30')]), events=[dict(id='event', kind='Expected publication')])
        items = assemble_changes(data)['items']
        self.assertEqual(items[0]['domain'], 'Disclosures')
        self.assertEqual(items[0]['detail_url'], '#disclosures?publisher=inspection')
        self.assertEqual(items[1]['domain'], 'Calendar')
        self.assertEqual(items[1]['detail_url'], '#calendar?month=2026-09&day=2026-09-30&event-type=Expected+publication')

    def test_latest_capture_compares_instants_not_offset_strings(self):
        data = dict(changes=dict(items=[], channels=[channel('sec', end='2026-09-28T10:00:00-07:00'),
            channel('fed', end='2026-09-28T16:00:00Z')]))
        self.assertEqual(assemble_changes(data)['latest_capture'], '2026-09-28T10:00:00-07:00')

    def test_duplicate_events_or_channels_are_rejected(self):
        b = bundle('sec', [dict(before=1, after=2)])
        b['items'] *= 2
        with self.assertRaisesRegex(ValueError, 'Duplicate change'):
            assemble_changes(dict(changes=b))
        b['items'] = []
        b['channels'] *= 2
        with self.assertRaisesRegex(ValueError, 'Duplicate comparison'):
            assemble_changes(dict(changes=b))


if __name__ == '__main__':
    unittest.main()
