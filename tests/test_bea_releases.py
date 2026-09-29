"""BEA GDP release gate: publication, point-in-time values, and raw receipts."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import bea_releases as bea


ADV = 'GDP (Advance Estimate), 2nd Quarter 2026'
SECOND = 'GDP (Second Estimate) and Corporate Profits, 2nd Quarter 2026'
THIRD = ('GDP (Third Estimate), Industries, Corporate Profits, State GDP, and State '
         'Personal Income, 2nd Quarter 2026; State PCE, 2025')
ADV_URL = 'https://www.bea.gov/news/2026/gdp-advance-estimate-2nd-quarter-2026'
SECOND_URL = 'https://www.bea.gov/news/2026/gdp-second-estimate-and-corporate-profits-2nd-quarter-2026'


def schedule(linked_second=True, future_link=False):
    def row(day, title, path=''):
        link = f'<a href="{path}">View</a>' if path else ''
        return (f'<tr class="scheduled-releases-type-press">'
                f'<td class="scheduled-date no-wrap"><div class="release-date">{day}</div>'
                '<small>8:30 AM</small></td><td>News</td>'
                f'<td class="release-title">{title}</td>'
                f'<td class="views-field-field-scheduled-release-url">{link}</td></tr>')
    return ('<html><h1>Release Schedule</h1><table>'
            + row('July 30', ADV, '/news/2026/gdp-advance-estimate-2nd-quarter-2026')
            + row('August 26', SECOND,
                  '/news/2026/gdp-second-estimate-and-corporate-profits-2nd-quarter-2026'
                  if linked_second else '')
            + row('September 30', THIRD,
                  '/news/2026/gdp-third-estimate-industries-corporate-profits-state-gdp-and-state-personal-income-2nd'
                  if future_link else '')
            + '</table></html>').encode()


def release(title, day, stage, value, gdi=None, technical='', table_value=None):
    sentence = (f'Real gross domestic product (GDP) increased at an annual rate of {value} '
                f'percent in the second quarter of 2026 (April, May, and June), according to '
                f'the {stage} estimate released today by the U.S. Bureau of Economic Analysis (BEA).')
    gdi_text = (f'<p>Real gross domestic income (GDI) increased {gdi} percent in the second '
                'quarter, compared with 1.2 percent in the first quarter.</p>') if gdi else ''
    table = (f'<table><thead><tr><th colspan="3">Real GDP and Related Measures'
             '<br><span>[Percent Change (SAAR) from 2026:Q1 to 2026:Q2]</span></th></tr>'
             '<tr><th>&nbsp;</th><th>Advance Estimate</th><th>Second Estimate</th></tr>'
             '</thead><tbody><tr><th>Real GDP</th><td>1.5</td>'
             f'<td>{table_value}</td></tr></tbody></table>') if table_value is not None else ''
    url = ADV_URL if stage == 'advance' else SECOND_URL
    return (f'<html><head><meta name="description" content="{sentence}">'
            f'<link rel="canonical" href="{url}"></head><body>'
            f'<div class="field--name-field-release-date">EMBARGOED UNTIL RELEASE AT '
            f'8:30 a.m. EDT, {day}</div><h1>{title}</h1>'
            f'<div class="release-body"><p><a href="#">{sentence}</a></p><div><img src="a.png"></div>'
            f'{gdi_text}{table}<p><strong>Technical Notes</strong></p><p>{technical}</p></div>'
            '</body></html>').encode()


ADV_HTML = release(ADV, 'Thursday, July 30, 2026', 'advance', '1.5')
SECOND_HTML = release(SECOND, 'Wednesday, August 26, 2026', 'second', '1.5', '2.2',
                      'Real GDP increased at an annual rate of 1.5 percent in the second '
                      'quarter, a downward revision of less than 0.1 percentage point.', '1.5')


class BEAReleaseTests(unittest.TestCase):
    def test_schedule_links_are_discovery_only_and_future_stays_pending(self):
        rows = bea.parse_schedule(schedule(future_link=True))
        self.assertEqual([(r['quarter'], r['stage'], r['date']) for r in rows],
                         [('2026Q2', 'advance', '2026-07-30'),
                          ('2026Q2', 'second', '2026-08-26'),
                          ('2026Q2', 'third', '2026-09-30')])
        self.assertTrue(rows[-1]['url'])
        with TemporaryDirectory() as tmp:
            fetched = []
            lookup = {bea.SCHEDULE_URL: schedule(future_link=True), ADV_URL: ADV_HTML,
                      SECOND_URL: SECOND_HTML}
            def fetch(url):
                fetched.append(url)
                return lookup[url]
            bundle = bea.collect(Path(tmp) / 'bea_releases', fetch,
                                 '2026-09-29T16:00:00+00:00')
            self.assertEqual(bundle['status'], 'ok')
            self.assertEqual(len(bundle['releases']), 2)
            self.assertEqual(bundle['scheduled'][0]['stage'], 'third')
            self.assertNotIn(rows[-1]['url'], fetched)

    def test_rounded_same_rate_preserves_publisher_downward_revision(self):
        row = bea.parse_schedule(schedule())[1]
        result = bea.parse_release(SECOND_HTML, row, '2026-09-29T16:00:00+00:00')
        self.assertEqual((result['value'], result['display_value'], result['gdi_value']),
                         (1.5, '1.5', 2.2))
        self.assertIn('current-stage', result['table_source_locator'])
        self.assertIn('downward revision of less than 0.1 percentage point', result['revision_note'])
        advance = bea.parse_release(ADV_HTML, bea.parse_schedule(schedule())[0],
                                    '2026-09-29T16:00:00+00:00')
        self.assertNotIn('gdi_value', advance)  # Absence is not zero or a later-stage backfill.

    def test_qualified_revision_of_other_measure_is_not_attributed_to_real_gdp(self):
        paragraphs = [
            'Real GDP increased at the same rate as in the advance estimate.',
            'The PCE price index had a downward revision of less than 0.1 percentage point.',
            'Real GDP increased 1.5 percent. The PCE price index had a downward revision of less than 0.1 percentage point.',
        ]
        self.assertEqual(bea._revision_note(paragraphs),
                         'BEA reports the same displayed rate as in the advance estimate.')

    def test_page_date_stage_quarter_and_source_sentence_must_reconcile(self):
        row = bea.parse_schedule(schedule())[1]
        with self.assertRaisesRegex(bea.BEAError, 'embargo has not elapsed'):
            bea.parse_release(SECOND_HTML, row, '2026-08-26T11:30:00+00:00')
        with self.assertRaisesRegex(bea.BEAError, 'publication date differs'):
            bea.parse_release(SECOND_HTML, dict(row, date='2026-08-27'),
                              '2026-09-29T16:00:00+00:00')
        with self.assertRaisesRegex(bea.BEAError, 'page title differs'):
            bea.parse_release(SECOND_HTML, dict(row, stage='third'),
                              '2026-09-29T16:00:00+00:00')
        with self.assertRaisesRegex(bea.BEAError, 'canonical URL differs'):
            bea.parse_release(SECOND_HTML, dict(row, url=ADV_URL),
                              '2026-09-29T16:00:00+00:00')
        changed = SECOND_HTML.replace(b'second quarter of 2026', b'first quarter of 2026')
        with self.assertRaisesRegex(bea.BEAError, 'different quarter'):
            bea.parse_release(changed, row, '2026-09-29T16:00:00+00:00')
        changed = SECOND_HTML.replace(b'at an annual rate of 1.5 percent',
                                      b'at an annual rate of 2.5 percent', 1)
        with self.assertRaisesRegex(bea.BEAError, 'description and release-body'):
            bea.parse_release(changed, row, '2026-09-29T16:00:00+00:00')
        changed = SECOND_HTML.replace(b'<td>1.5</td></tr>', b'<td>2.5</td></tr>')
        with self.assertRaisesRegex(bea.BEAError, 'current-stage SAAR table disagree'):
            bea.parse_release(changed, row, '2026-09-29T16:00:00+00:00')

    def test_unlinked_past_schedule_does_not_create_an_actual(self):
        rows = bea.parse_schedule(schedule(linked_second=False))
        self.assertIsNone(rows[1]['url'])
        with TemporaryDirectory() as tmp:
            bundle = bea.collect(Path(tmp) / 'bea_releases',
                                 {bea.SCHEDULE_URL: schedule(linked_second=False), ADV_URL: ADV_HTML}.__getitem__,
                                 '2026-09-29T16:00:00+00:00')
            self.assertEqual([r['stage'] for r in bundle['releases']], ['advance'])
            self.assertEqual([r['stage'] for r in bundle['scheduled']], ['second', 'third'])

    def test_raw_reconciliation_and_incremental_repoll(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / 'bea_releases'
            fetched = []
            lookup = {bea.SCHEDULE_URL: schedule(), ADV_URL: ADV_HTML, SECOND_URL: SECOND_HTML}
            def fetch(url):
                fetched.append(url)
                return lookup[url]
            first = bea.collect(target, fetch, '2026-09-29T16:00:00+00:00')
            self.assertEqual(first['status'], 'ok')
            self.assertEqual(first['changes']['baselines'], ['bea-gdp-releases'])
            bea.validate_capture(first, Path(tmp))
            self.assertEqual(len(fetched), 3)
            fetched.clear()
            second = bea.collect(target, fetch, '2026-09-29T17:00:00+00:00')
            self.assertEqual(second['status'], 'ok')
            self.assertEqual(fetched, [bea.SCHEDULE_URL])
            self.assertEqual(first['releases'], second['releases'])
            self.assertEqual(second['changes']['items'], [])
            changed = copy.deepcopy(second)
            changed['releases'][0]['value'] = 1.6
            changed['releases'][0]['display_value'] = '1.6'
            with self.assertRaisesRegex(bea.BEAError, 'differs from retained source'):
                bea.validate_capture(changed, Path(tmp))
            changed = copy.deepcopy(second)
            changed['releases'][0]['sha256'] = '0' * 64
            with self.assertRaisesRegex(bea.BEAError, 'hash mismatch'):
                bea.validate_capture(changed, Path(tmp))

    def test_repository_nested_data_paths_validate_from_repository_root(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / 'data' / 'bea_releases'
            lookup = {bea.SCHEDULE_URL: schedule(), ADV_URL: ADV_HTML, SECOND_URL: SECOND_HTML}
            captured = bea.collect(target, lookup.__getitem__, '2026-09-29T16:00:00+00:00')
            self.assertEqual(captured['status'], 'ok')
            self.assertTrue(captured['schedule']['raw_path'].startswith('data/bea_releases/raw/'))
            self.assertTrue(all(r['raw_path'].startswith('data/bea_releases/raw/')
                                for r in captured['releases']))
            bea.validate_capture(captured, Path(tmp))

    def test_failed_refresh_retains_values_and_separate_clocks(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / 'bea_releases'
            lookup = {bea.SCHEDULE_URL: schedule(), ADV_URL: ADV_HTML, SECOND_URL: SECOND_HTML}
            good = bea.collect(target, lookup.__getitem__, '2026-09-29T16:00:00+00:00')
            def failed(_):
                raise OSError('network unavailable')
            stale = bea.collect(target, failed, '2026-09-30T16:00:00+00:00')
            self.assertEqual(stale['status'], 'stale')
            self.assertEqual(stale['captured_at'], good['captured_at'])
            self.assertEqual(stale['releases'], good['releases'])
            self.assertEqual(stale['attempted_at'], '2026-09-30T16:00:00+00:00')
            self.assertEqual(stale['changes']['skipped'], ['bea-gdp-releases'])
            self.assertEqual(stale['changes']['items'], [])
            bea.validate_capture(stale, Path(tmp))
            initial = bea.collect(Path(tmp) / 'empty', failed,
                                  '2026-09-30T16:00:00+00:00')
            self.assertEqual(initial['status'], 'unavailable')
            self.assertEqual(initial['releases'], [])

    def test_timeout_is_stale_not_a_workflow_exception(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / 'bea_releases'
            lookup = {bea.SCHEDULE_URL: schedule(), ADV_URL: ADV_HTML, SECOND_URL: SECOND_HTML}
            good = bea.collect(target, lookup.__getitem__, '2026-09-29T16:00:00+00:00')
            def timed_out(_):
                raise subprocess.TimeoutExpired('curl', 50)
            stale = bea.collect(target, timed_out, '2026-09-29T17:00:00+00:00')
            self.assertEqual(stale['status'], 'stale')
            self.assertEqual(stale['releases'], good['releases'])
            self.assertEqual(stale['changes']['skipped'], ['bea-gdp-releases'])

    def test_malicious_or_malformed_schedule_link_rejected(self):
        bad = schedule().replace(b'/news/2026/gdp-advance', b'https://evil.example/news/2026/gdp-advance')
        with self.assertRaisesRegex(bea.BEAError, 'canonical BEA'):
            bea.parse_schedule(bad)
        with self.assertRaisesRegex(bea.BEAError, 'No recent'):
            bea.parse_schedule(b'<html><h1>Release Schedule</h1><table>'
                               b'<tr class="scheduled-releases-type-press"></tr>'
                               b'</table><p>Other unrelated release rows here</p></html>')


if __name__ == '__main__':
    unittest.main()
