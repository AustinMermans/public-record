import csv
import io
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from investor_sources import SOURCES, OFR_COLUMNS, parse_nyfed, parse_ofr

STAMP = '2026-09-28T23:00:00+00:00'


class InvestorSourceTests(unittest.TestCase):
    def setUp(self):
        self.ny = {**SOURCES[0], 'expected_count': 2}
        self.rows = [dict(effectiveDate=day, type='SOFR', percentRate=3.9,
                         percentPercentile1=3.83, percentPercentile25=3.89,
                         percentPercentile75=3.95, percentPercentile99=3.99,
                         volumeInBillions=2914, revisionIndicator='')
                     for day in ('2026-09-25', '2026-09-24')]
        self.ofr = {**SOURCES[-1], 'min_count': 2}

    def csv(self, rows):
        out = io.StringIO(); writer = csv.writer(out)
        writer.writerow(['Date'] + [x[0] for x in OFR_COLUMNS]); writer.writerows(rows)
        return out.getvalue()

    def test_ny_dates_metadata_and_units(self):
        self.rows[0]['revisionIndicator'] = '*'
        s = parse_nyfed(json.dumps({'refRates': self.rows}), self.ny, STAMP)['series'][0]
        self.assertEqual(s['observations'][0], ['2026-09-24', 3.9])
        self.assertEqual(s['details'][-1]['volume_billions'], 2914)
        self.assertEqual(s['details'][-1]['revision_indicator'], '*')
        self.assertEqual(s['date_basis'], 'Effective date')
        self.assertIsNone(s['publication_date'])
        self.assertEqual(s['unit'], 'Percent')
        self.assertTrue(s['attribution'] and s['terms_url'])

    def test_ny_rejects_partial_duplicate_wrong_type_and_bad_values(self):
        for mutate in (lambda r:r.pop(), lambda r:r[0].update(effectiveDate=r[1]['effectiveDate']),
                       lambda r:r[0].update(type='EFFR'), lambda r:r[0].update(percentRate=None),
                       lambda r:r[0].update(percentRate=float('nan')), lambda r:r[0].update(volumeInBillions=-1),
                       lambda r:r[0].update(effectiveDate='2026-02-30'), lambda r:r[0].update(effectiveDate='2026-09-29'),
                       lambda r:r[0].update(percentPercentile25=9)):
            rows=[dict(r) for r in self.rows]; mutate(rows)
            with self.assertRaises(ValueError):
                parse_nyfed(json.dumps({'refRates':rows}), self.ny, STAMP)

    def test_ofr_preserves_negative_zero_and_component_definitions(self):
        body=self.csv([['2026-09-24']+[-2.0]*9,['2026-09-23']+[0]*9])
        series=parse_ofr(body,self.ofr,STAMP)['series']
        self.assertEqual(len(series),9)
        self.assertEqual(series[0]['observations'],[['2026-09-23',0],['2026-09-24',-2]])
        self.assertEqual(series[1]['stock_flow'],'Index contribution')
        self.assertEqual(series[6]['geography'],'Global')
        self.assertIn('US contribution',series[6]['name'])

    def test_ofr_rejects_truncation_dates_and_missing_values(self):
        valid=['2026-09-24']+[0]*9
        for rows in ([valid],[valid,valid],[valid,['2026-09-25']+[None]*9],
                     [valid,['not-a-date']+[0]*9],[valid,['2026-09-25']+[float('inf')]*9]):
            with self.assertRaises(ValueError):parse_ofr(self.csv(rows),self.ofr,STAMP)
        with self.assertRaises(ValueError):parse_ofr('<html>Error</html>',self.ofr,STAMP)


if __name__=='__main__':unittest.main()
