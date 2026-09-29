"""The earnings bridge is allowed to fail closed, never to infer a quarter from proximity."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from earnings_dossiers import assemble_dossiers, quarter_identity


class EarningsDossierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corporate=json.loads((ROOT/'data/corporate/current.json').read_text())
        cls.briefs=json.loads((ROOT/'data/business_briefs/current.json').read_text())
        cls.financials=json.loads((ROOT/'data/financials/current.json').read_text())

    def one(self,ticker,mutate=None):
        company=copy.deepcopy(next(c for c in self.corporate['companies'] if ticker in c.get('tickers',[])))
        briefs=copy.deepcopy([b for b in self.briefs['briefs'] if b['cik']==company['cik']])
        financial=copy.deepcopy([f for f in self.financials['companies'] if f['cik']==company['cik']])
        if mutate:mutate(company,briefs,financial)
        return assemble_dossiers({'companies':[company]},{'briefs':briefs},{'companies':financial},ROOT)['dossiers'][0]

    def test_headlines_need_a_result_and_fiscal_quarter(self):
        self.assertEqual(quarter_identity('Apple reports third quarter 2026 results'),(2026,'Q3'))
        self.assertEqual(quarter_identity('Third quarter 2026 financial results'),(2026,'Q3'))
        self.assertIsNone(quarter_identity('Tesla announces third quarter 2026 production and deliveries'))
        self.assertIsNone(quarter_identity('Company announces results'))

    def test_apple_quarter_is_source_matched_with_exact_filing_links(self):
        item=self.one('AAPL')
        self.assertEqual(item['status'],'matched')
        self.assertEqual(item['period_end'],'2026-06-27')
        self.assertIn('exhibit',item['period_basis'].lower())
        self.assertEqual(item['financial']['figures'][0]['current']['value'],109_417_000_000)
        self.assertEqual(item['financial']['figures'][0]['prior']['value'],94_036_000_000)
        self.assertEqual(item['financial']['figures'][0]['current']['url'],item['financial']['anchor']['url'])
        self.assertNotEqual(item['event']['accession'],item['financial']['anchor']['accession'])

    def test_period_and_cik_mismatches_do_not_join(self):
        changed=self.one('AAPL',lambda c,b,f:f[0]['sections'][0].update(end='2026-03-28'))
        self.assertNotIn(changed['status'],('matched','stale_matched'))
        changed=self.one('AAPL',lambda c,b,f:f[0]['anchor'].update(url='https://www.sec.gov/Archives/edgar/data/9999/other.htm'))
        self.assertEqual(changed['status'],'period_unverified')
        def conflicting_headline(company,briefs,financials):
            latest=max(briefs,key=lambda b:b.get('filed',''))
            latest['headline']='Apple reports fourth quarter 2026 results'
        changed=self.one('AAPL',conflicting_headline)
        self.assertEqual(changed['status'],'period_mismatch')
        with patch('earnings_dossiers.exhibit_period',return_value=(None,(2026,'Q3'),True)):
            changed=self.one('AAPL')
        self.assertEqual(changed['status'],'period_unverified')

    def test_annual_facts_and_metadata_only_do_not_become_quarter_dossiers(self):
        self.assertEqual(self.one('MSFT')['status'],'quarter_facts_unavailable')
        self.assertEqual(self.one('TSLA')['status'],'metadata_only')

    def test_successor_registry_is_not_spliced_to_predecessor_event(self):
        successor=self.one('XOM')
        self.assertEqual(successor['status'],'matched')
        self.assertEqual(successor['cik'],'0002115436')
        self.assertTrue(successor['financial']['anchor']['url'].startswith('https://www.sec.gov/Archives/edgar/data/2115436/'))
        predecessor=copy.deepcopy(next(c for c in self.corporate['companies'] if c['cik']=='0000034088'))
        item=assemble_dossiers({'companies':[predecessor]},self.briefs,self.financials,ROOT)['dossiers'][0]
        self.assertNotIn(item['status'],('matched','stale_matched'))

    def test_full_capture_keeps_every_selected_registrant_and_explicit_fallbacks(self):
        result=assemble_dossiers(self.corporate,self.briefs,self.financials,ROOT)
        self.assertEqual(result['coverage'],len(self.corporate['companies']))
        self.assertEqual(result['matched'],sum(d['status']=='matched' for d in result['dossiers']))
        self.assertGreater(result['matched'],0)
        self.assertTrue(all(d['reason'] and d['status'] for d in result['dossiers']))


if __name__=='__main__':unittest.main()
