import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import energy as e

STAMP = '2026-09-29T20:00:00+00:00'


def fixture():
    end = date(2026, 9, 18)
    points = [{'date': (end - timedelta(weeks=50-index)).isoformat(),
               'value': 400000 + index * 1000, 'suppression_flag': None}
              for index in range(51)]
    points[-2]['value'] = 423429
    points[-1]['value'] = 426398
    metadata = dict(source=e.PUBLISHER, release_name='Weekly Petroleum Status Report',
        data_description='Commercial Crude Oil Stocks (Excluding SPR)', periodicity='Weekly',
        release_date='2026-09-23', time_period={'end_date': '2026-09-18'})
    source = dict(metadata=metadata, data={'U.S.': {'sourcekey': 'WCESTUS1',
        'units': 'thousand barrels', 'time_series': points}})
    body = ('"STUB_1","9/18/26","9/11/26","Difference","9/19/25","Percent Change","9/20/24","Percent Change"\r\n'
        '"Commercial (Excluding SPR)","426.398","423.429","2.969","414.754","2.800","413.042","3.200"\r\n'
        '"Total Motor Gasoline","206.046","207.732","-1.686","216.569","-4.900","220.083","-6.400"\r\n'
        '"Distillate Fuel Oil","107.431","107.859","-0.428","122.999","-12.700","122.921","-12.600"\r\n')
    return json.dumps(source).encode(), body.encode()


class EnergyTests(unittest.TestCase):
    def test_exact_rows_units_reconciliation_and_dates(self):
        bundle = e.parse_sources(*fixture(), STAMP)
        self.assertEqual(bundle['week_end'], '2026-09-18')
        self.assertEqual(bundle['published_at'], '2026-09-23')
        self.assertEqual(bundle['metrics'][0]['weekly_change'], '2.969')
        self.assertEqual(bundle['metrics'][2]['year_change_pct'], '-12.7')
        self.assertEqual(bundle['crude_history'][-1], ['2026-09-18', 426398])

    def test_rejects_period_mismatch_and_unverified_suppression(self):
        j, c = fixture()
        data = json.loads(j)
        data['data']['U.S.']['time_series'][-1]['suppression_flag'] = '-'
        with self.assertRaisesRegex(e.EnergyError, 'suppressed'):
            e.parse_sources(json.dumps(data).encode(), c, STAMP)
        with self.assertRaisesRegex(e.EnergyError, 'periods disagree'):
            e.parse_sources(j, c.replace(b'9/18/26', b'9/19/26', 1), STAMP)
        with self.assertRaisesRegex(e.EnergyError, 'periods disagree'):
            e.parse_sources(j, c.replace(b'9/19/25', b'9/20/24', 1), STAMP)
        rounded = e.parse_sources(j, c.replace(b'2.969', b'2.970', 1), STAMP)
        self.assertEqual(rounded['metrics'][0]['weekly_change'], '2.970')
        with self.assertRaisesRegex(e.EnergyError, 'does not reconcile'):
            e.parse_sources(j, c.replace(b'2.969', b'2.971', 1), STAMP)

    def test_replays_retained_raw_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data_dir = root / 'data' / 'energy'
            bodies = fixture()
            bundle = e.collect(None, STAMP, data_dir, fetch=lambda url: bodies[0] if url == e.JSON_URL else bodies[1])
            self.assertEqual(bundle['status'], 'ok')
            e.validate_capture(bundle, root)
            changed = copy.deepcopy(bundle)
            changed['metrics'][0]['current'] = '999.999'
            with self.assertRaisesRegex(e.EnergyError, 'differs from raw'):
                e.validate_capture(changed, root)
            path = root / bundle['receipts']['table']['raw_path']
            path.write_bytes(b'tampered')
            with self.assertRaisesRegex(e.EnergyError, 'hash mismatch'):
                e.validate_capture(bundle, root)

    def test_stale_retains_last_success_without_change_event(self):
        with tempfile.TemporaryDirectory() as folder:
            data_dir = Path(folder) / 'data' / 'energy'
            bodies = fixture()
            previous = e.collect(None, STAMP, data_dir,
                fetch=lambda url: bodies[0] if url == e.JSON_URL else bodies[1])
            stale = e.collect(previous, '2026-09-30T20:00:00+00:00', data_dir,
                fetch=lambda url: (_ for _ in ()).throw(e.EnergyError('EIA blocked')))
            self.assertEqual(stale['status'], 'stale')
            self.assertEqual(stale['captured_at'], STAMP)
            self.assertEqual(stale['changes']['items'], [])
            self.assertEqual(stale['changes']['channels'][0]['status'], 'unavailable')
            e.validate_capture(stale, data_dir.parent.parent)

    def test_new_reporting_week_is_separate_from_same_week_revision(self):
        before = e.parse_sources(*fixture(), STAMP)
        revised = copy.deepcopy(before)
        revised['captured_at'] = '2026-09-30T20:00:00+00:00'
        revised['metrics'][0]['current'] = '426.400'
        changes = e.compare_energy(before, revised)
        self.assertEqual([x['kind'] for x in changes['items']], ['Revised petroleum stock'])
        revised['week_end'] = '2026-09-25'
        changes = e.compare_energy(before, revised)
        self.assertEqual(len(changes['items']), 3)
        self.assertEqual(changes['items'][0]['kind'], 'New petroleum reporting week')

    def test_prior_and_history_revisions_enter_change_ledger(self):
        before = e.parse_sources(*fixture(), STAMP)
        after = copy.deepcopy(before)
        after['captured_at'] = '2026-09-30T20:00:00+00:00'
        after['metrics'][1]['prior'] = '207.730'
        after['crude_history'][8][1] += 100
        kinds = [item['kind'] for item in e.compare_energy(before, after)['items']]
        self.assertEqual(kinds, ['Revised prior-week petroleum stock', 'Revised crude history'])

    def test_crude_table_and_json_revision_is_one_development(self):
        before = e.parse_sources(*fixture(), STAMP)
        after = copy.deepcopy(before)
        after['captured_at'] = '2026-09-30T20:00:00+00:00'
        after['metrics'][0]['current'] = '426.400'
        after['crude_history'][-1][1] = 426400
        kinds = [item['kind'] for item in e.compare_energy(before, after)['items']]
        self.assertEqual(kinds, ['Revised petroleum stock'])
        after = copy.deepcopy(before)
        after['captured_at'] = '2026-09-30T20:00:00+00:00'
        after['metrics'][0]['prior'] = '423.430'
        after['crude_history'][-2][1] = 423430
        kinds = [item['kind'] for item in e.compare_energy(before, after)['items']]
        self.assertEqual(kinds, ['Revised prior-week petroleum stock'])


if __name__ == '__main__':
    unittest.main()
