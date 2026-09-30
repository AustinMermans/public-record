"""SPF source and release safety regression tests; no network calls."""
import hashlib
import io
import json
import sys
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import spf

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = json.loads((ROOT / 'data/spf/current.json').read_text())
RAW = {name: (ROOT / info['raw_path']).read_bytes()
       for name, info in CAPTURE['sources'].items()}


def replace_zip_member(body, name, old, new):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(body)) as source, zipfile.ZipFile(output, 'w') as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == name:
                assert old in content
                content = content.replace(old, new, 1)
            target.writestr(item, content)
    return output.getvalue()


class SPFTests(unittest.TestCase):
    def test_official_capture_hashes_and_q3_2026_reconciliation(self):
        self.assertEqual(CAPTURE['status'], 'ok')
        for name, info in CAPTURE['sources'].items():
            self.assertEqual(hashlib.sha256(RAW[name]).hexdigest(), info['sha256'])
            self.assertEqual(info['url'], spf.URLS[name])
        dates = spf.parse_release_dates(RAW['release_dates'])
        self.assertNotIn('1990Q2', dates)
        self.assertEqual(dates['1990Q3'], '1990-08-31')
        self.assertEqual(dates['2026Q3'], '2026-08-14')
        expected = {
            'RGDP': (2.2707, 'RGDP!D233'),
            'UNEMP': (4.3, 'UNEMP!E233'),
            'CPI': (2.5227, 'CPI!E233'),
            'CORECPI': (2.7858, 'CORECPI!E233'),
            'PCE': (2.55, 'PCE!E233'),
            'COREPCE': (2.6158, 'COREPCE!E233'),
        }
        for metric, (value, cell) in expected.items():
            point = next(p for p in CAPTURE['series'][metric]['points']
                         if p['survey'] == '2026Q3' and p['target'] == '2026Q4')
            self.assertEqual((point['value'], point['cell'], point['released']),
                             (value, cell, '2026-08-14'))

    def test_suffix_target_mapping(self):
        self.assertEqual([spf.target_quarter('2026Q3', i) for i in range(2, 7)],
                         ['2026Q3', '2026Q4', '2027Q1', '2027Q2', '2027Q3'])

    def test_missing_source_cells_are_absent_not_zero(self):
        rows = spf.parse_workbook(RAW['medianLevel'], {'CORECPI': 'CORECPI'})['CORECPI']
        self.assertEqual(rows['1990Q3'], {})
        self.assertEqual(CAPTURE['series']['CORECPI']['points'][0]['survey'], '2007Q1')

    def test_release_day_and_before_excluded(self):
        for stamp in ('2026-08-13T20:00:00+00:00', '2026-08-14T20:00:00+00:00'):
            snapshot = spf.build_snapshot(RAW['medianGrowth'], RAW['medianLevel'],
                                          RAW['release_dates'], stamp, CAPTURE['sources'])
            for series in snapshot['series'].values():
                self.assertFalse(any(p['survey'] == '2026Q3' for p in series['points']))
        next_day = spf.build_snapshot(RAW['medianGrowth'], RAW['medianLevel'],
                                      RAW['release_dates'], '2026-08-15T00:00:00+00:00',
                                      CAPTURE['sources'])
        self.assertTrue(any(p['survey'] == '2026Q3' for p in next_day['series']['RGDP']['points']))

    def test_missing_release_date_and_malformed_workbook_rejected(self):
        text = RAW['release_dates'].replace(b'     Q3             8/11/26             8/14/26',
                                            b'     Q3             8/11/26             bad')
        self.assertNotEqual(text, RAW['release_dates'])
        with self.assertRaisesRegex(spf.SPFError, 'Missing historical release date'):
            spf.build_snapshot(RAW['medianGrowth'], RAW['medianLevel'], text,
                               '2026-09-29T00:00:00+00:00', CAPTURE['sources'])
        with self.assertRaisesRegex(spf.SPFError, 'XLSX'):
            spf.parse_workbook(b'<html>error</html>', {'RGDP': 'drgdp'})

    def test_negative_growth_allowed_and_negative_unemployment_rejected(self):
        changed_growth = replace_zip_member(RAW['medianGrowth'], 'xl/worksheets/sheet8.xml',
                                            b'<v>2.2707</v>', b'<v>-2.2707</v>')
        row = spf.parse_workbook(changed_growth, {'RGDP': 'drgdp'})['RGDP']['2026Q3']
        self.assertEqual(row[3], (-2.2707, 'RGDP!D233'))
        changed_level = replace_zip_member(RAW['medianLevel'], 'xl/worksheets/sheet4.xml',
                                           b'<v>4.3000</v>', b'<v>-4.3000</v>')
        with self.assertRaisesRegex(spf.SPFError, 'unemployment'):
            spf.parse_workbook(changed_level, {'UNEMP': 'UNEMP'})

    def test_failed_refresh_retains_last_success_and_marks_stale(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp)
            target.joinpath('current.json').write_text(json.dumps(CAPTURE))
            def fail(_url):
                raise OSError('network timeout')
            result = spf.collect(target, fail, '2026-09-30T00:00:00+00:00')
            self.assertEqual(result['status'], 'stale')
            self.assertEqual(result['captured_at'], CAPTURE['captured_at'])
            self.assertEqual(result['attempted_at'], '2026-09-30T00:00:00+00:00')
            self.assertEqual(result['series'], CAPTURE['series'])
            self.assertEqual(result['sources'], CAPTURE['sources'])

    def test_success_preserves_previous_capture_for_change_comparison(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp)
            target.joinpath('current.json').write_text(json.dumps(CAPTURE))
            by_url = {spf.URLS[name]: body for name, body in RAW.items()}
            result = spf.collect(target, by_url.__getitem__, '2026-09-30T00:00:00+00:00')
            self.assertEqual(result['status'], 'ok')
            baseline = json.loads(target.joinpath('comparison-baseline.json').read_text())
            self.assertEqual(baseline['captured_at'], CAPTURE['captured_at'])
            self.assertEqual(baseline['series'], CAPTURE['series'])

    def test_first_failure_unavailable(self):
        with TemporaryDirectory() as tmp:
            result = spf.collect(Path(tmp), lambda _url: b'<html>bad</html>',
                                 '2026-09-30T00:00:00+00:00')
            self.assertEqual(result['status'], 'unavailable')
            self.assertIsNone(result['captured_at'])

    def test_build_validation_reconciles_raw_bytes_and_normalized_values(self):
        spf.validate_capture(CAPTURE, ROOT)
        changed = json.loads(json.dumps(CAPTURE))
        changed['series']['RGDP']['points'][-1]['value'] += 0.1
        with self.assertRaisesRegex(spf.SPFError, 'differs from source cells'):
            spf.validate_capture(changed, ROOT)
        changed = json.loads(json.dumps(CAPTURE))
        changed['sources']['medianGrowth']['sha256'] = '0' * 64
        with self.assertRaisesRegex(spf.SPFError, 'hash mismatch'):
            spf.validate_capture(changed, ROOT)

    def test_stale_validation_retains_evidence_and_attempt_clock(self):
        stale = json.loads(json.dumps(CAPTURE))
        captured = datetime.fromisoformat(CAPTURE['captured_at'])
        stale.update(status='stale', attempted_at=(captured + timedelta(hours=1)).isoformat(), error='source unavailable')
        spf.validate_capture(stale, ROOT)
        stale['attempted_at'] = (captured - timedelta(hours=1)).isoformat()
        with self.assertRaisesRegex(spf.SPFError, 'later attempt'):
            spf.validate_capture(stale, ROOT)


if __name__ == '__main__':
    unittest.main()
