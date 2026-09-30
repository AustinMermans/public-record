import copy
import gzip
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from inflation import InflationError, URL, compare, extract_tables, normalize_month_excerpt, parse_page, validate_capture


def fixture(mom='0.50', released=''):
    def table(caption, first, rows):
        period = 'quarter' if first == 'Quarter' else 'month'
        return (f'<table><caption>{caption}</caption><thead><tr><th>{first}</th>'
                '<th>CPI</th><th>Core CPI</th><th>PCE</th><th>Core PCE</th><th>Updated</th>'
                '</tr></thead><tbody>' + rows + '</tbody><tfoot><tr><td colspan="6">'
                f'Note: If the cell is blank, it implies that the actual data corresponding to the {period} for that inflation measure have already been released.'
                '</td></tr></tfoot></table>')
    return ('<html>' + table('Inflation, month-over-month percent change', 'Month',
                            f'<tr><td>September 2026</td><td>{mom}</td><td>0.20</td><td>0.44</td><td>0.28</td><td>09/29</td></tr>'
                            f'<tr><td>August 2026</td><td>{released}</td><td></td><td>0.34</td><td>0.27</td><td>09/29</td></tr>')
            + table('Inflation, year-over-year percent change', 'Month',
                    '<tr><td>September 2026</td><td>3.57</td><td>2.39</td><td>3.97</td><td>3.49</td><td>09/29</td></tr>')
            + table('Quarterly annualized percent change', 'Quarter',
                    '<tr><td>2026:Q3</td><td>1.53</td><td>2.16</td><td>2.55</td><td>3.00</td><td>09/29</td></tr>') + '</html>').encode()


class InflationTests(unittest.TestCase):
    def setUp(self):
        self.stamp = '2026-09-29T23:47:28+00:00'

    def test_extracts_exact_target_basis_and_blank(self):
        rows = parse_page(fixture(), self.stamp)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0], dict(basis='mom', target='2026-09', updated_on='2026-09-29',
                                       values=dict(cpi='0.50', core_cpi='0.20', pce='0.44', core_pce='0.28')))
        self.assertIsNone(rows[1]['values']['cpi'])
        self.assertEqual(rows[-1]['target'], '2026Q3')

    def test_rejects_changed_structure_and_fabricated_values(self):
        body = fixture()
        for corrupted in (body.replace(b'Core CPI</th>', b'Core PPI</th>', 1),
                          body.replace(b'Quarterly annualized percent change', b'Quarterly change'),
                          fixture(mom='0.500'), fixture(mom='101.00'),
                          fixture(released='unknown'),
                          body.replace(b'actual data corresponding', b'data temporarily unavailable')):
            with self.subTest(corrupted=corrupted[:120]):
                with self.assertRaises(InflationError):
                    parse_page(corrupted, self.stamp)

    def test_rejects_future_and_ambiguous_update_day(self):
        with self.assertRaises(InflationError):
            parse_page(fixture().replace(b'09/29', b'10/01'), self.stamp)
        with self.assertRaises(InflationError):
            parse_page(fixture().replace(b'09/29', b'02/29'), self.stamp)

    def test_evidence_reparse_and_tamper(self):
        response = fixture()
        body = extract_tables(response)
        digest = hashlib.sha256(body).hexdigest()
        relative = f'data/inflation/raw/{digest}.tables.html.gz'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = root / relative
            raw.parent.mkdir(parents=True)
            raw.write_bytes(gzip.compress(body, mtime=0))
            snapshot = dict(captured_at=self.stamp, sha256=digest,
                            response_sha256=hashlib.sha256(response).hexdigest(), raw_path=relative,
                            rows=parse_page(body, self.stamp))
            bundle = dict(schema_version=1, status='ok', url=URL, attempted_at=self.stamp,
                          history_error='Monthly chart unavailable in this fixture',
                          history=[snapshot], **snapshot)
            bundle['changes'] = compare(None, bundle)
            validate_capture(bundle, root)
            broken = copy.deepcopy(bundle)
            broken['rows'][0]['values']['cpi'] = '0.51'
            with self.assertRaises(InflationError):
                validate_capture(broken, root)
            broken = copy.deepcopy(bundle)
            broken['changes']['items'].append(dict(kind='Invented news', after='1.00'))
            with self.assertRaises(InflationError):
                validate_capture(broken, root)
            raw.write_bytes(gzip.compress(body+b' ', mtime=0))
            with self.assertRaises(InflationError):
                validate_capture(bundle, root)

    def test_change_is_same_target_only_and_first_capture_baseline(self):
        prior = dict(status='ok', captured_at='2026-09-28T23:00:00+00:00',
                     rows=parse_page(fixture(mom='0.40'), self.stamp))
        current = dict(status='ok', captured_at=self.stamp, rows=parse_page(fixture(), self.stamp))
        self.assertEqual(compare(None, current)['baselines'], ['cleveland-inflation-nowcast'])
        changes = compare(prior, current)['items']
        self.assertEqual(len(changes), 1)
        self.assertEqual((changes[0]['basis'], changes[0]['target'], changes[0]['metric_id'],
                          changes[0]['before'], changes[0]['after']),
                         ('mom', '2026-09', 'cpi', '0.40', '0.50'))
        rolled = copy.deepcopy(current)
        rolled['rows'][0]['target'] = '2026-10'
        self.assertFalse(any(item['target'] == '2026-10' for item in compare(prior, rolled)['items']))

    def test_retained_real_capture(self):
        root = Path(__file__).resolve().parents[1]
        bundle = json.loads((root / 'data/inflation/current.json').read_text())
        validate_capture(bundle, root)
        self.assertEqual(bundle['status'], 'ok')
        self.assertEqual(bundle['rows'][0]['values']['cpi'], '0.50')
        publisher = bundle['publisher_history']
        self.assertEqual({path['target'] for path in publisher['paths']}, {'2026-08', '2026-09'})
        self.assertEqual(len(publisher['paths'][1]['series']['cpi']), 20)
        raw = gzip.decompress((root / publisher['raw_path']).read_bytes())
        parsed = json.loads(raw)
        for altered in (
            lambda value: value[1]['dataset'][0]['data'][-1].update(value='0.01'),
            lambda value: value[1]['chart'].update(yaxisname='Annualized percent change'),
            lambda value: value.pop(),
            lambda value: value[1]['categories'][0]['category'][1].update(label='01/01'),
        ):
            with self.subTest(altered=altered):
                copy_of_source = copy.deepcopy(parsed)
                altered(copy_of_source)
                with self.assertRaises(InflationError):
                    normalize_month_excerpt(json.dumps(copy_of_source).encode(), bundle['rows'], bundle['captured_at'])
        tampered = copy.deepcopy(bundle)
        tampered['publisher_history']['paths'][1]['series']['cpi'][-1][1] = '0.01'
        with self.assertRaises(InflationError):
            validate_capture(tampered, root)

    def test_month_chart_december_to_january_rollover(self):
        root = Path(__file__).resolve().parents[1]
        bundle = json.loads((root / 'data/inflation/current.json').read_text())
        raw = gzip.decompress((root / bundle['publisher_history']['raw_path']).read_bytes())
        september = copy.deepcopy(json.loads(raw)[1])
        september['chart']['subcaption'] = '2026-12'
        september['chart']['_comment'] = '2027-01-03 00:00'
        september['categories'][0]['category'] = [{'label': '12/31'}, {'label': '01/02'}]
        for dataset in september['dataset']:
            dataset['data'] = dataset['data'][-2:]
        row = copy.deepcopy(bundle['rows'][0])
        row['target'] = '2026-12'
        normalized = normalize_month_excerpt(json.dumps([september]).encode(), [row],
                                             '2027-01-03T18:00:00+00:00')
        self.assertEqual([point[0] for point in normalized[0]['series']['cpi']],
                         ['2026-12-31', '2027-01-02'])


if __name__ == '__main__':
    unittest.main()
