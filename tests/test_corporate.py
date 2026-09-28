import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from corporate import parse_company
class CorporateTests(unittest.TestCase):
    def data(self):
        return dict(cik='1',name='Fixture',filings={'recent':dict(accessionNumber=['0000000001-26-000001'],filingDate=['2026-09-28'],reportDate=['2026-09-25'],form=['8-K/A'],primaryDocument=['report.htm'],items=['2.02,9.01'])})
    def test_form_amendment_and_items(self):
        f=parse_company(self.data(),'0000000001')['filings'][0]
        self.assertTrue(f['amendment']);self.assertIn('Results of operations',f['item_descriptions'][0]);self.assertIn('/1/000000000126000001/',f['url'])
    def test_wrong_identity_rejected(self):
        with self.assertRaises(ValueError):parse_company(self.data(),'0000000002')
    def test_column_mismatch_rejected(self):
        d=self.data();d['filings']['recent']['form']=[]
        with self.assertRaises(ValueError):parse_company(d,'0000000001')
    def test_ownership_does_not_crowd_out_annual(self):
        d=self.data();r=d['filings']['recent']
        r.update(accessionNumber=[f'0000000001-26-{i:06d}' for i in range(81)],filingDate=['2026-09-28']*80+['2025-12-31'],reportDate=['2026-09-25']*81,form=['4']*80+['10-K'],primaryDocument=['report.htm']*81,items=['']*81)
        filings=parse_company(d,'0000000001')['filings']
        self.assertEqual(sum(f['form']=='4' for f in filings),12)
        self.assertEqual(sum(f['form']=='10-K' for f in filings),1)
