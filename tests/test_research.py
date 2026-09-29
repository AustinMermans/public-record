import hashlib, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import research
from research import vintage_csv, parse_sep, parse_gdpnow, validate_gdpnow_capture

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
    def test_nowcast_capture_binds_display_to_raw_page(self):
        url='https://www.atlantafed.org/research-and-data/data/gdpnow'
        raw=b'<p>5.0% Third-Quarter GDPNow Estimate for 2026:Q3 Updated: September 25, 2026</p>'
        digest=hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'data/research/raw'/f'{digest}.txt'
            path.parent.mkdir(parents=True);path.write_bytes(raw)
            item=dict(parse_gdpnow(raw.decode(),url),url=url,status='ok',sha256=digest,
                      raw_path=f'data/research/raw/{digest}.txt',captured_at='2026-09-29T20:39:07+00:00')
            bundle=dict(captured_at='2026-09-29T20:39:07+00:00',forecasts=[item])
            validate_gdpnow_capture(bundle,root)
            for key,value in [('value',49.0),('target','2026 Q4'),('published_at','2026-09-26')]:
                altered=json.loads(json.dumps(bundle));altered['forecasts'][0][key]=value
                with self.assertRaisesRegex(ValueError,'do not match'):
                    validate_gdpnow_capture(altered,root)
            altered=json.loads(json.dumps(bundle));altered['forecasts'][0]['raw_path']='data/research/raw/../other.txt'
            with self.assertRaisesRegex(ValueError,'raw path'):
                validate_gdpnow_capture(altered,root)
            path.write_bytes(b'different source')
            with self.assertRaisesRegex(ValueError,'digest mismatch'):
                validate_gdpnow_capture(bundle,root)
    def test_real_gdpnow_capture_reconciles(self):
        root=Path(__file__).resolve().parents[1]
        validate_gdpnow_capture(json.loads((root/'data/research/current.json').read_text()),root)
    def test_two_initial_gdpnow_fetch_failures_remain_unavailable(self):
        url='https://www.atlantafed.org/research-and-data/data/gdpnow'
        with tempfile.TemporaryDirectory() as folder, patch.object(research,'DATA',Path(folder)), patch.object(research,'fetch',side_effect=ValueError('source timeout')):
            first=research.forecast('gdpnow',url,parse_gdpnow)
            self.assertEqual(first['status'],'unavailable')
            (Path(folder)/'gdpnow.json').write_text(json.dumps(first))
            second=research.forecast('gdpnow',url,parse_gdpnow)
            self.assertEqual(second['status'],'unavailable')
            validate_gdpnow_capture({'captured_at':research.STAMP,'forecasts':[second]},Path(folder))
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
