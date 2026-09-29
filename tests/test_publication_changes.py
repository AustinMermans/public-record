import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publication_changes import compare_corporate, compare_research


def filing(accession='a', **fields):
    return dict(id=accession, form='8-K', filed='2026-09-23', accepted_at='2026-09-23T16:00:00',
                report_period='2026-09-22', amendment=False, description='Results of operations',
                items=['2.02', '9.01'], item_descriptions=['Results', 'Exhibits'],
                url='https://www.sec.gov/' + accession, **fields)


def corporate(stamp='2026-09-24T10:00:00Z'):
    return dict(captured_at=stamp + '-bundle', companies=[dict(cik='0000000001', name='Issuer',
                captured_at=stamp, status='ok', filings=[filing()])])


def research(stamp='2026-09-24T11:00:00Z'):
    return dict(captured_at=stamp + '-bundle', vintages=[dict(as_of='2020-01-01')], forecasts=[
        dict(id='gdpnow', title='Atlanta Fed GDPNow', published_at='2026-09-23', value=3.2,
             target='2026 Q3', unit='Percent · quarterly annualized', basis='Real GDP growth estimate',
             url='https://www.atlantafed.org/gdpnow', captured_at=stamp, status='ok'),
        dict(id='sep', title='FOMC projections', published_at='2026-09-16',
             horizons=['2026', '2027', 'Longer run'], unit='Percent', basis='Participant medians',
             rows=[dict(name='Real GDP growth', values=[2.3, 2.4, 2.0]),
                   dict(name='Core PCE inflation', values=[3.4, 2.5, None])],
             url='https://www.federalreserve.gov/sep', captured_at=stamp, status='ok')])


class CorporateChangeTests(unittest.TestCase):
    def test_initial_baseline_and_empty_prior_feed(self):
        result = compare_corporate(None, corporate())
        self.assertEqual(result['items'], [])
        self.assertEqual(result['baselines'], ['sec-company-0000000001'])
        self.assertEqual(result['channels'][0]['status'], 'baseline')
        old = corporate(); old['companies'][0]['filings'] = []
        self.assertEqual(compare_corporate(old, corporate())['items'][0]['kind'], 'Newly captured filing')

    def test_new_accession_has_independent_dates_and_source_clocks(self):
        old = corporate(); new = corporate('2026-09-25T10:00:00Z')
        new['companies'][0]['filings'].append(filing('b'))
        item = compare_corporate(old, new)['items'][0]
        self.assertEqual(item['kind'], 'Newly captured filing')
        self.assertEqual(item['from_capture'], old['companies'][0]['captured_at'])
        self.assertEqual(item['to_capture'], new['companies'][0]['captured_at'])
        self.assertEqual(item['date'], '2026-09-23')
        self.assertEqual(item['report_period'], '2026-09-22')
        self.assertEqual(item['accession'], 'b')
        self.assertEqual(item['items'], ['2.02', '9.01'])
        self.assertEqual(item['url'], 'https://www.sec.gov/b')

    def test_amendment_is_distinct_accession(self):
        new = corporate(); amendment = filing('a-amended')
        amendment.update(form='8-K/A', amendment=True)
        new['companies'][0]['filings'].append(amendment)
        item = compare_corporate(corporate(), new)['items'][0]
        self.assertEqual(item['kind'], 'Newly captured filing amendment')
        self.assertTrue(item['amendment'])

    def test_metadata_edit_not_new_filing(self):
        new = corporate(); record = new['companies'][0]['filings'][0]
        record.update(report_period='2026-09-21', description='Corrected description', items=['1.01'])
        item = compare_corporate(corporate(), new)['items'][0]
        self.assertEqual(item['kind'], 'Filing metadata changed')
        self.assertEqual(set(item['changed_fields']), {'report_period', 'description', 'items'})
        self.assertEqual(item['previous_url'], item['url'])

    def test_unchanged_reordered_and_disappeared_are_not_events(self):
        old = corporate(); new = copy.deepcopy(old)
        new['companies'][0]['filings'][0]['items'].reverse()
        new['companies'][0]['filings'][0]['item_descriptions'].reverse()
        self.assertEqual(compare_corporate(old, new)['items'], [])
        new['companies'][0]['filings'] = []
        self.assertEqual(compare_corporate(old, new)['items'], [])

    def test_failed_capture_and_resume_uses_last_success(self):
        old = corporate(); failed = copy.deepcopy(old)
        failed['captured_at'] = 'later-bundle'
        failed['companies'][0].update(status='stale', attempted_at='failed-at', error='secret sentinel')
        diff = compare_corporate(old, failed)
        self.assertEqual(diff['items'], [])
        self.assertEqual(diff['channels'][0]['status'], 'unavailable')
        self.assertNotIn('secret sentinel', str(diff))
        new = corporate('2026-09-28T10:00:00Z'); new['companies'][0]['filings'].append(filing('b'))
        item = compare_corporate(failed, new)['items'][0]
        self.assertEqual(item['from_capture'], old['companies'][0]['captured_at'])

    def test_missing_channel_and_duplicate_accession_fail_closed(self):
        self.assertEqual(compare_corporate(corporate(), {'companies': []})['channels'][0]['status'], 'unavailable')
        new = corporate(); new['companies'][0]['filings'].append(filing())
        self.assertEqual(compare_corporate(corporate(), new)['channels'][0]['status'], 'unavailable')

    def test_company_channels_have_independent_successful_capture_clocks(self):
        old = corporate(); second = copy.deepcopy(old['companies'][0])
        second.update(cik='0000000002', name='Second issuer', captured_at='2026-09-20T10:00:00Z')
        old['companies'].append(second)
        new = copy.deepcopy(old)
        for index, company in enumerate(new['companies']):
            company['captured_at'] = '2026-09-28T1' + str(index) + ':00:00Z'
            company['filings'].append(filing('new'))
        changes = compare_corporate(old, new)['items']
        self.assertEqual([i['from_capture'] for i in changes],
                         ['2026-09-24T10:00:00Z', '2026-09-20T10:00:00Z'])



class ResearchChangeTests(unittest.TestCase):
    def test_baseline_and_vintages_excluded(self):
        diff = compare_research(None, research())
        self.assertEqual(diff['items'], [])
        self.assertEqual(diff['baselines'], ['research-gdpnow', 'research-sep'])
        self.assertEqual(diff['excluded'], ['vintages'])
        new = research(); new['vintages'].append({'as_of': '2026-01-01'})
        self.assertEqual(compare_research(research(), new)['items'], [])

    def test_same_target_estimate_update_and_same_publication_correction(self):
        old = research(); new = research('2026-09-25T11:00:00Z')
        new['forecasts'][0].update(value=3.4, published_at='2026-09-24')
        item = compare_research(old, new)['items'][0]
        self.assertEqual(item['kind'], 'Updated forecast estimate')
        self.assertEqual((item['before'], item['after']), (3.2, 3.4))
        self.assertEqual(item['target'], '2026 Q3')
        self.assertEqual(item['from_capture'], old['forecasts'][0]['captured_at'])
        self.assertEqual(item['previous_published_at'], '2026-09-23')
        new['forecasts'][0]['published_at'] = old['forecasts'][0]['published_at']
        self.assertEqual(compare_research(old, new)['items'][0]['kind'], 'Same-date forecast update')

    def test_target_and_unit_boundaries_block_numeric_comparison(self):
        for field, value, kind in [('target', '2026 Q4', 'Forecast target changed'),
                                    ('unit', 'Index', 'Forecast definition changed'),
                                    ('basis', 'Nominal GDP', 'Forecast definition changed')]:
            with self.subTest(field=field):
                new = research(); new['forecasts'][0].update(value=100, **{field: value})
                item = compare_research(research(), new)['items'][0]
                self.assertEqual(item['kind'], kind)
                self.assertTrue(item['comparison_boundary'])
                self.assertNotEqual(item['after'], 100)

    def test_publication_and_other_metadata_updates(self):
        new = research(); new['forecasts'][0]['published_at'] = '2026-09-24'
        self.assertEqual(compare_research(research(), new)['items'][0]['kind'], 'Forecast publication updated')
        new = research(); new['forecasts'][0]['url'] += '/new'
        self.assertEqual(compare_research(research(), new)['items'][0]['kind'], 'Forecast metadata changed')

    def test_sep_reordered_rows_and_horizons_unchanged(self):
        new = research(); sep = new['forecasts'][1]
        sep['rows'].reverse(); sep['horizons'].reverse()
        for row in sep['rows']:
            row['values'].reverse()
        self.assertEqual(compare_research(research(), new)['items'], [])

    def test_sep_same_horizon_update_vs_same_publication_correction(self):
        new = research(); sep = new['forecasts'][1]
        sep['rows'][0]['values'][1] = 2.1
        item = compare_research(research(), new)['items'][0]
        self.assertEqual((item['kind'], item['target']), ('Same-date forecast update', '2027'))
        sep['published_at'] = '2026-12-16'
        self.assertEqual(compare_research(research(), new)['items'][0]['kind'], 'Updated forecast projection')

    def test_sep_new_horizon_is_not_revision(self):
        new = research(); sep = new['forecasts'][1]
        sep['horizons'].insert(2, '2028')
        for row in sep['rows']:
            row['values'].insert(2, 2.2)
        diff = compare_research(research(), new)
        self.assertEqual(len(diff['items']), 2)
        self.assertTrue(all(i['kind'] == 'New forecast horizon' and i['comparison_boundary'] for i in diff['items']))

    def test_sep_definition_changes_suppress_all_cell_revisions(self):
        new = research(); sep = new['forecasts'][1]
        sep['basis'] = 'Different policy assumption'
        sep['rows'][0]['values'][0] = 100
        changes = compare_research(research(), new)['items']
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['kind'], 'Forecast definition changed')
        self.assertTrue(changes[0]['comparison_boundary'])

    def test_new_sep_measure_is_not_a_numeric_revision(self):
        new = research(); new['forecasts'][1]['rows'].append(dict(name='Unemployment', values=[4.0, 4.1, 4.2]))
        changes = compare_research(research(), new)['items']
        self.assertEqual(len(changes), 3)
        self.assertTrue(all(i['kind'] == 'New forecast measure' for i in changes))

    def test_sep_null_is_missing_not_zero(self):
        new = research(); new['forecasts'][1]['rows'][1]['values'][2] = 0
        item = compare_research(research(), new)['items'][0]
        self.assertEqual((item['kind'], item['before'], item['after']), ('Forecast value became available', None, 0))
        reverse = compare_research(new, research())['items'][0]
        self.assertEqual(reverse['kind'], 'Forecast value unavailable')
        new['forecasts'][1]['rows'].pop()
        self.assertEqual(compare_research(research(), new)['items'], [])

    def test_bad_sep_structure_and_nonfinite_values_skip(self):
        for change in ('duplicate_row', 'duplicate_horizon', 'short_values', 'nan'):
            new = research(); sep = new['forecasts'][1]
            if change == 'duplicate_row': sep['rows'].append(copy.deepcopy(sep['rows'][0]))
            elif change == 'duplicate_horizon': sep['horizons'][1] = sep['horizons'][0]
            elif change == 'short_values': sep['rows'][0]['values'].pop()
            else: sep['rows'][0]['values'][0] = float('nan')
            diff = compare_research(research(), new)
            self.assertEqual(diff['items'], [])
            self.assertEqual(diff['skipped'], ['research-sep'])

    def test_independent_forecast_status_and_resume(self):
        old = research(); failed = research()
        failed['forecasts'][0].update(status='stale', attempted_at='later')
        failed['forecasts'][1]['rows'][0]['values'][0] = 2.5
        diff = compare_research(old, failed)
        self.assertEqual(diff['skipped'], ['research-gdpnow'])
        self.assertEqual(diff['items'][0]['forecast_id'], 'sep')
        new = research('2026-09-28T11:00:00Z'); new['forecasts'][0]['value'] = 3.5
        item = compare_research(failed, new)['items'][0]
        self.assertEqual(item['from_capture'], old['forecasts'][0]['captured_at'])


if __name__ == '__main__':
    unittest.main()
