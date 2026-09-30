"""Point-in-time PCE price readings must replay from official retained bytes."""

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import bea_pce as bea


class BEAPCETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture = json.loads((ROOT / 'data/bea_pce/current.json').read_text())
        cls.schedule = (ROOT / cls.capture['schedule']['raw_path']).read_bytes()
        cls.rows = bea.parse_schedule(cls.schedule)
        cls.bodies = {row['url']: (ROOT / row['raw_path']).read_bytes()
                      for row in cls.capture['releases']}
        cls.july = next(row for row in cls.rows if row['target'] == '2026-07')
        cls.july_body = cls.bodies[cls.july['url']]

    def test_retained_official_capture_replays_and_separates_price_horizons(self):
        bea.validate_capture(self.capture, ROOT)
        self.assertEqual(self.capture['changes']['baselines'], [bea.SOURCE_ID])
        self.assertEqual(self.capture['changes']['items'], [])
        releases = {row['target']: row for row in self.capture['releases']}
        self.assertEqual(sorted(releases), [f'2026-{month:02d}' for month in range(1, 8)])
        self.assertEqual(releases['2026-07']['values'], dict(
            headline_mom=0.2, core_mom=0.2, headline_yoy=3.7, core_yoy=3.3))
        self.assertEqual(releases['2026-06']['values']['headline_mom'], -0.1)
        self.assertEqual(releases['2026-06']['display_values']['headline_mom'], '-0.1')
        self.assertEqual(releases['2026-07']['embargo_at'], '2026-08-26T12:30+00:00')
        self.assertTrue(all(row['source_locator']['mom'].startswith('News Release body')
                            for row in releases.values()))

    def test_schedule_view_link_is_required_for_an_actual(self):
        august = next(row for row in self.rows if row['target'] == '2026-08')
        self.assertIsNone(august['url'])
        self.assertEqual(august['date'], '2026-09-30')
        self.assertEqual(self.capture['scheduled'][0]['target'], '2026-08')
        self.assertNotIn('2026-08', {row['target'] for row in self.capture['releases']})
        self.assertNotIn('2025-10', {row['target'] for row in self.rows})
        self.assertNotIn('2025-11', {row['target'] for row in self.rows})

    def test_page_identity_publication_boundary_and_target_must_reconcile(self):
        with self.assertRaisesRegex(bea.BEAPCEError, 'embargo has not elapsed'):
            bea.parse_release(self.july_body, self.july, '2026-08-26T12:29:00+00:00')
        with self.assertRaisesRegex(bea.BEAPCEError, 'publication date differs'):
            bea.parse_release(self.july_body, dict(self.july, date='2026-08-27'),
                              '2026-09-29T20:00:00+00:00')
        with self.assertRaisesRegex(bea.BEAPCEError, 'canonical URL differs'):
            bea.parse_release(self.july_body, dict(self.july,
                              url='https://www.bea.gov/news/2026/personal-income-and-outlays-june-2026'),
                              '2026-09-29T20:00:00+00:00')
        changed = self.july_body.replace(b'PCE price index</strong> for July increased 0.2 percent',
                                         b'PCE price index</strong> for June increased 0.2 percent', 1)
        self.assertNotEqual(changed, self.july_body)
        with self.assertRaisesRegex(bea.BEAPCEError, 'changed BEA PCE mom'):
            bea.parse_release(changed, self.july, '2026-09-29T20:00:00+00:00')

    def test_missing_or_duplicate_source_paragraph_fails_closed(self):
        changed = self.july_body.replace(b'Excluding food and energy, the PCE price index also increased 0.2 percent.',
                                         b'Core inflation was 0.2 percent.', 1)
        self.assertNotEqual(changed, self.july_body)
        with self.assertRaisesRegex(bea.BEAPCEError, 'changed BEA PCE mom'):
            bea.parse_release(changed, self.july, '2026-09-29T20:00:00+00:00')
        changed = self.july_body.replace(b'<p><a href=', b'<p>From the preceding month, the PCE price index for July increased 9.9 percent. Excluding food and energy, the PCE price index increased 9.9 percent.</p><p><a href=', 1)
        with self.assertRaisesRegex(bea.BEAPCEError, 'Duplicate BEA PCE mom'):
            bea.parse_release(changed, self.july, '2026-09-29T20:00:00+00:00')

    def test_raw_hash_and_value_tampering_detected_by_replay(self):
        tampered = copy.deepcopy(self.capture)
        tampered['releases'][-1]['values']['headline_mom'] = 2.0
        with self.assertRaisesRegex(bea.BEAPCEError, 'rate/display reconciliation'):
            bea.validate_capture(tampered, ROOT)
        tampered = copy.deepcopy(self.capture)
        tampered['releases'][-1]['sha256'] = '0' * 64
        with self.assertRaisesRegex(bea.BEAPCEError, 'hash mismatch'):
            bea.validate_capture(tampered, ROOT)
        tampered = copy.deepcopy(self.capture)
        tampered['releases'][-1]['discovery_schedule_sha256'] = '0' * 64
        with self.assertRaisesRegex(bea.BEAPCEError, 'missing original discovery schedule'):
            bea.validate_capture(tampered, ROOT)
        tampered = copy.deepcopy(self.capture)
        tampered['releases'].pop()
        with self.assertRaisesRegex(bea.BEAPCEError, 'omits schedule month'):
            bea.validate_capture(tampered, ROOT)

    def test_refresh_reuses_verified_releases_and_failure_preserves_last_success(self):
        lookup = {bea.SCHEDULE_URL: self.schedule, **self.bodies}
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / 'data' / 'bea_pce'
            fetched = []
            def fetch(url):
                fetched.append(url)
                return lookup[url]
            first = bea.collect(target, fetch, '2026-09-29T20:00:00+00:00')
            self.assertEqual(first['status'], 'ok')
            self.assertEqual(first['changes']['baselines'], [bea.SOURCE_ID])
            self.assertEqual(len(fetched), 8)
            bea.validate_capture(first, Path(temporary))
            fetched.clear()
            second = bea.collect(target, fetch, '2026-09-29T21:00:00+00:00')
            self.assertEqual(fetched, [bea.SCHEDULE_URL])
            self.assertEqual(first['releases'], second['releases'])
            self.assertEqual(second['changes']['items'], [])
            self.assertEqual(second['changes']['channels'][0]['status'], 'compared')
            def failed(_):
                raise subprocess.TimeoutExpired('curl', 50)
            stale = bea.collect(target, failed, '2026-09-30T20:00:00+00:00')
            self.assertEqual(stale['status'], 'stale')
            self.assertEqual(stale['releases'], first['releases'])
            self.assertEqual(stale['captured_at'], second['captured_at'])
            self.assertEqual(stale['attempted_at'], '2026-09-30T20:00:00+00:00')
            self.assertEqual(stale['changes']['skipped'], [bea.SOURCE_ID])
            bea.validate_capture(stale, Path(temporary))
            unavailable = bea.collect(Path(temporary) / 'empty', failed,
                                      '2026-09-30T20:00:00+00:00')
            self.assertEqual(unavailable['status'], 'unavailable')
            self.assertEqual(unavailable['releases'], [])

    def test_change_receipt_emits_only_new_target_and_rejects_rewrites(self):
        previous = copy.deepcopy(self.capture)
        previous['releases'] = previous['releases'][:-1]
        current = copy.deepcopy(self.capture)
        changes = bea.compare_bea_pce(previous, current)
        self.assertEqual(changes['channels'][0]['status'], 'compared')
        self.assertEqual(len(changes['items']), 1)
        self.assertEqual(changes['items'][0]['target'], '2026-07')
        self.assertEqual(changes['items'][0]['after'], dict(
            headline_mom=0.2, core_mom=0.2, headline_yoy=3.7, core_yoy=3.3))
        self.assertEqual(changes['items'][0]['url'], self.july['url'])
        current['releases'][0]['values']['headline_mom'] = 9.9
        with self.assertRaisesRegex(bea.BEAPCEError, 'actual changed'):
            bea.compare_bea_pce(previous, current)

    def test_change_receipt_cannot_publish_unverified_release(self):
        tampered = copy.deepcopy(self.capture)
        tampered['changes']['items'].append(dict(
            source_id=bea.SOURCE_ID, target='2026-08',
            title='Invented PCE publication', after={'headline_mom': 9.9}))
        with self.assertRaisesRegex(bea.BEAPCEError, 'baseline claims a release change'):
            bea.validate_capture(tampered, ROOT)
        rereleased = copy.deepcopy(self.capture)
        from_capture = '2026-09-30T01:50:00+00:00'
        rereleased['changes'] = dict(
            channels=[dict(id=bea.SOURCE_ID, label='BEA · dated PCE price releases',
                           status='compared', from_capture=from_capture,
                           to_capture=rereleased['captured_at'])],
            items=[bea._change_item(rereleased['releases'][-1], from_capture,
                                    rereleased['captured_at'])],
            baselines=[], skipped=[])
        with self.assertRaisesRegex(bea.BEAPCEError, 'change item differs'):
            bea.validate_capture(rereleased, ROOT)

    def test_year_rollover_retains_old_actuals_and_discovers_new_year(self):
        url_2027 = 'https://www.bea.gov/news/2027/personal-income-and-outlays-january-2027'
        schedule_2027 = (
            '<html><h1>Release Schedule</h1><table>'
            '<tr class="scheduled-releases-type-press">'
            '<td class="scheduled-date">January 29 <small>8:30 AM</small></td>'
            '<td class="release-title">Personal Income and Outlays, December 2026</td>'
            '<td class="views-field-field-scheduled-release-url"></td></tr>'
            '<tr class="scheduled-releases-type-press">'
            '<td class="scheduled-date">February 26 <small>8:30 AM</small></td>'
            '<td class="release-title">Personal Income and Outlays, January 2027</td>'
            '<td class="views-field-field-scheduled-release-url">'
            f'<a href="/news/2027/personal-income-and-outlays-january-2027">View</a>'
            '</td></tr></table></html>').encode()
        release_2027 = (
            '<html><head><link rel="canonical" href="' + url_2027 + '"></head><body>'
            '<div class="field--name-field-release-date">EMBARGOED UNTIL RELEASE AT '
            '8:30 a.m. EST, Friday, February 26, 2027</div>'
            '<h1>Personal Income and Outlays, January 2027</h1>'
            '<div class="release-body">'
            '<p>From the preceding month, the PCE price index for January increased 0.3 percent. '
            'Excluding food and energy, the PCE price index increased 0.2 percent.</p>'
            '<p>From the same month one year ago, the PCE price index for January increased '
            '2.9 percent. Excluding food and energy, the PCE price index increased 2.8 percent '
            'from one year ago.</p></div></body></html>').encode()
        self.assertEqual(bea.parse_schedule(schedule_2027)[0]['date'], '2027-01-29')
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / 'data' / 'bea_pce'
            lookup = {bea.SCHEDULE_URL: self.schedule, **self.bodies}
            old = bea.collect(target, lookup.__getitem__, '2026-09-29T20:00:00+00:00')
            self.assertEqual(old['status'], 'ok')
            lookup[bea.SCHEDULE_URL] = schedule_2027
            rollover = bea.collect(target, lookup.__getitem__, '2027-01-02T20:00:00+00:00')
            self.assertEqual(rollover['status'], 'ok')
            self.assertEqual(rollover['releases'], old['releases'])
            self.assertEqual([row['target'] for row in rollover['scheduled']],
                             ['2026-12', '2027-01'])
            self.assertEqual(rollover['changes']['items'], [])
            bea.validate_capture(rollover, Path(temporary))
            lookup[url_2027] = release_2027
            published = bea.collect(target, lookup.__getitem__, '2027-03-01T20:00:00+00:00')
            self.assertEqual(published['status'], 'ok')
            self.assertEqual(published['releases'][:7], old['releases'])
            self.assertEqual(len(published['discovery_schedules']), 2)
            self.assertEqual(published['releases'][-1]['target'], '2027-01')
            self.assertEqual(published['releases'][-1]['values'], dict(
                headline_mom=0.3, core_mom=0.2, headline_yoy=2.9, core_yoy=2.8))
            self.assertEqual([item['target'] for item in published['changes']['items']],
                             ['2027-01'])
            bea.validate_capture(published, Path(temporary))

    def test_malformed_schedule_or_link_is_not_accepted(self):
        bad = self.schedule.replace(b'/news/2026/personal-income-and-outlays-july-2026',
                                    b'https://other.example/news/2026/personal-income-and-outlays-july-2026', 1)
        with self.assertRaisesRegex(bea.BEAPCEError, 'canonical single-month BEA'):
            bea.parse_schedule(bad)
        with self.assertRaisesRegex(bea.BEAPCEError, 'structure missing'):
            bea.parse_schedule(b'<html><h1>Release Schedule</h1><p>No schedule table exists; '
                               b'other unrelated releases may still be listed here but none '
                               b'can establish a PCE publication.</p></html>')


if __name__ == '__main__':
    unittest.main()
