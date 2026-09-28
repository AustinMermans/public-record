import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from research import vintage_csv, parse_sep, parse_gdpnow

class ResearchTests(unittest.TestCase):
    def test_vintage_header_is_verified(self):
        with self.assertRaises(ValueError):vintage_csv('observation_date,UNRATE\n2020-01-01,3.5\n','UNRATE','2020-07-30')
    def test_vintage_future_rejected(self):
        with self.assertRaises(ValueError):vintage_csv('observation_date,UNRATE_20200730\n2021-01-01,3.5\n','UNRATE','2020-07-30')
    def test_vintage_missing_preserved(self):
        self.assertEqual(vintage_csv('observation_date,UNRATE_20200730\n2020-01-01,3.5\n2020-02-01,.\n2020-03-01,4.4\n','UNRATE','2020-07-30'),[['2020-01-01',3.5],['2020-03-01',4.4]])
    def test_nowcast_binds_target_and_update(self):
        f=parse_gdpnow('<p>5.0%% Third-Quarter GDPNow Estimate for 2026:Q3</p><p>Updated: September 25, 2026</p>','source')
        self.assertEqual((f['target'],f['value'],f['published_at']),('2026 Q3',5.0,'2026-09-25'))
    def test_nowcast_rejects_unrelated_numbers(self):
        with self.assertRaises(ValueError):parse_gdpnow('<p>Growth is 5.0 percent; many forecasts exist.</p>','source')
    def test_sep_structural_failure(self):
        with self.assertRaises(ValueError):parse_sep('<html>Error</html>','https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260916.htm')
    def test_sep_four_and_five_horizons(self):
        for years in (['2026','2027','2028'],['2026','2027','2028','2029']):
            headers=years+['Longer run']
            labels=['Change in real GDP','Unemployment rate','PCE inflation','Core PCE inflation','Federal funds rate']
            rows=['<tr>'+''.join('<th>'+x+'</th>' for x in headers*3)+'</tr>']
            for label in labels:
                values=['2.0']*len(years)+([''] if label=='Core PCE inflation' else ['2.0'])
                rows.append('<tr><td>'+label+'</td>'+''.join('<td>'+x+'</td>' for x in values*3)+'</tr>')
            f=parse_sep('<table>'+''.join(rows)+'</table>','https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260916.htm')
            self.assertEqual(f['horizons'],headers)
            self.assertEqual(f['rows'][3]['values'][-1],None)

if __name__=='__main__':unittest.main()
