import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from financials import normalize_company


STAMP = '2026-09-28T23:00:00+00:00'
ACC = '0000320193-26-000001'
ANNUAL = '0000320193-25-000001'
REV = 'RevenueFromContractWithCustomerExcludingAssessedTax'


def fact(value, start=None, end='2026-06-27', accession=ACC, form='10-Q', filed='2026-07-31', fp='Q3', **extra):
    row=dict(val=value,end=end,accn=accession,form=form,filed=filed,fy=2026,fp=fp,**extra)
    if start:row['start']=start
    return row


def fixture(cik='0000320193'):
    company=dict(cik=cik,name='Example issuer',filings=[
        dict(id=ACC,form='10-Q',filed='2026-07-31',report_period='2026-06-27',url='https://www.sec.gov/current.htm'),
        dict(id=ANNUAL,form='10-K',filed='2025-10-31',report_period='2025-09-27',url='https://www.sec.gov/annual.htm')])
    facts={}
    for tag,value,unit in [(REV,100,'USD'),('OperatingIncomeLoss',20,'USD'),('NetIncomeLoss',15,'USD'),('EarningsPerShareDiluted',1.5,'USD/shares')]:
        facts[tag]=dict(label=tag,description='Exact source definition',units={unit:[
            fact(value,'2026-03-29'),fact(value*.8,'2025-03-30','2025-06-28'),
            fact(value*3,'2025-09-28'),fact(value*2.4,'2024-09-29','2025-06-28'),
            fact(value*4,'2024-09-29','2025-09-27',ANNUAL,'10-K','2025-10-31','FY')]})
    for tag,value in [('NetCashProvidedByUsedInOperatingActivities',50),('PaymentsToAcquirePropertyPlantAndEquipment',10)]:
        facts[tag]=dict(units={'USD':[fact(value,'2025-09-28'),fact(value*.8,'2024-09-29','2025-06-28')]})
    for tag,value in [('Assets',200),('Liabilities',120),('StockholdersEquity',80),('CashAndCashEquivalentsAtCarryingValue',30)]:
        facts[tag]=dict(units={'USD':[fact(value),fact(value*.8,end='2025-09-27')]})
    return dict(cik=int(cik),facts={'us-gaap':facts}),company


def row(result, rid, section=None):
    return next(r for s in result['sections'] if section is None or s['id']==section for r in s['rows'] if r['id']==rid)


class FinancialNormalizationTests(unittest.TestCase):
    def normalize(self,p,c):return normalize_company(p,c,STAMP)

    def test_exact_quarter_ytd_and_year_end_are_separate(self):
        p,c=fixture();n=self.normalize(p,c)
        self.assertEqual(row(n,'revenue')['current']['value'],100)
        self.assertEqual(row(n,'revenue')['current']['start'],'2026-03-29')
        self.assertEqual(row(n,'revenue')['prior']['start'],'2025-03-30')
        self.assertEqual(row(n,'cfo')['current']['value'],50)
        self.assertEqual(row(n,'cfo')['current']['start'],'2025-09-28')
        self.assertEqual(row(n,'assets')['prior']['end'],'2025-09-27')
        self.assertEqual(n['annual_history'][0]['start'],'2024-09-29')
        self.assertEqual(n['readiness']['status'],'partial')

    def test_derived_metrics_are_typed_and_have_matched_source_inputs(self):
        p,c=fixture();n=self.normalize(p,c)
        for rid,expected in [('operating_margin',20),('cfo_less_cash_ppe',40)]:
            value=row(n,rid)['current']
            self.assertEqual(value['value'],expected)
            self.assertEqual(value['evidence_label'],'derived_calculation')
            self.assertEqual(len(value['inputs']),2)
            self.assertEqual(len({(i['start'],i['end'],i['accession'],i['unit']) for i in value['inputs']}),1)
        self.assertEqual(row(n,'operating_margin')['unit'],'Percent')
        self.assertEqual(row(n,'cfo_less_cash_ppe')['unit'],'USD')

    def test_every_used_source_has_index_and_exact_accession_link(self):
        p,c=fixture();n=self.normalize(p,c);sources={x['source_id'] for x in n['source_index']}
        for s in n['sections']+n['annual_history']:
            for r in s['rows']:
                for key in ('current','prior'):
                    v=r[key]
                    if v:
                        self.assertIn(v['source_id'],sources)
                        self.assertIn(v['url'],['https://www.sec.gov/current.htm','https://www.sec.gov/annual.htm'])
                        self.assertEqual(v['retrieved_at'],STAMP)
        self.assertTrue(n['validation_checks'])

    def test_obsolete_concept_is_not_current_fallback(self):
        p,c=fixture();p['facts']['us-gaap'][REV]['units']['USD']=[fact(10,'2020-04-01','2020-06-30','old','10-Q','2020-07-31','Q2')]
        n=self.normalize(p,c)
        self.assertIsNone(row(n,'revenue')['current'])
        self.assertIsNone(row(n,'operating_margin')['current'])
        self.assertEqual(row(n,'revenue')['evidence_label'],'missing_required_source')

    def test_newest_filing_with_missing_facts_is_not_replaced_by_old_filing(self):
        p,c=fixture();c['filings'].append(dict(id='newer',form='10-Q',filed='2026-09-01',report_period='2026-08-01',url='https://www.sec.gov/newer.htm'))
        n=self.normalize(p,c)
        self.assertEqual(n['anchor']['accession'],'newer')
        self.assertEqual(n['readiness']['status'],'not_ready')
        self.assertTrue(all(r['current'] is None for s in n['sections'] for r in s['rows']))
        self.assertTrue(n['annual_history'])

    def test_conflicting_same_period_and_duplicate_frames(self):
        p,c=fixture();entries=p['facts']['us-gaap'][REV]['units']['USD']
        entries.append(dict(entries[0],frame='CY2026Q2'))
        self.assertEqual(row(self.normalize(p,c),'revenue')['current']['value'],100)
        entries.append(dict(entries[0],val=101,frame='OTHER'))
        r=row(self.normalize(p,c),'revenue')
        self.assertIsNone(r['current']);self.assertEqual({x['value'] for x in r['conflicts']},{100,101})

    def test_amendment_conflict_only_suppresses_affected_line(self):
        p,c=fixture();c['filings'].append(dict(id='amendment',form='10-Q/A',filed='2026-08-02',report_period='2026-06-27',url='https://www.sec.gov/amendment.htm'))
        p['facts']['us-gaap'][REV]['units']['USD'].append(fact(105,'2026-03-29',accession='amendment',form='10-Q/A',filed='2026-08-02'))
        n=self.normalize(p,c)
        self.assertEqual(n['anchor']['accession'],ACC)
        self.assertIsNone(row(n,'revenue')['current'])
        self.assertEqual(row(n,'net_income')['current']['value'],15)
        self.assertTrue(any(x['url']=='https://www.sec.gov/amendment.htm' for x in row(n,'revenue')['conflicts']))

    def test_currency_difference_is_missing_not_converted(self):
        p,c=fixture();tag=p['facts']['us-gaap'][REV];tag['units']['EUR']=tag['units'].pop('USD')
        self.assertIsNone(row(self.normalize(p,c),'revenue')['current'])

    def test_comparative_currency_or_definition_is_not_substituted(self):
        p,c=fixture();current=p['facts']['us-gaap'][REV]['units']['USD'][0]
        p['facts']['us-gaap'][REV]['units']['USD']=[current]
        p['facts']['us-gaap']['Revenues']=dict(units={'USD':[fact(80,'2025-03-30','2025-06-28')]})
        n=self.normalize(p,c)
        self.assertEqual(row(n,'revenue')['current']['value'],100)
        self.assertIsNone(row(n,'revenue')['prior'])
        self.assertTrue(any(b['metric_or_framework']=='revenue' for b in n['comparability_bridges']))

    def test_bank_profile_has_no_industrial_cash_flow_or_margin(self):
        p,c=fixture('0000019617');p['facts']['us-gaap']['RevenuesNetOfInterestExpense']=p['facts']['us-gaap'][REV]
        n=self.normalize(p,c)
        self.assertEqual(n['profile_type'],'bank')
        self.assertNotIn('cash_flow',[s['id'] for s in n['sections']])
        self.assertNotIn('operating_margin',[r['id'] for s in n['sections'] for r in s['rows']])
        self.assertEqual(row(n,'revenue')['concept'],'us-gaap:RevenuesNetOfInterestExpense')

    def test_issuer_specific_walmart_total_revenue(self):
        p,c=fixture('0000104169');p['facts']['us-gaap']['Revenues']=copy.deepcopy(p['facts']['us-gaap'][REV])
        p['facts']['us-gaap']['Revenues']['units']['USD'][0]['val']=102
        n=self.normalize(p,c)
        self.assertEqual(row(n,'revenue')['current']['value'],102)
        self.assertEqual(row(n,'revenue')['concept'],'us-gaap:Revenues')

    def test_noncontrolling_and_temporary_equity_bases_are_visible(self):
        p,c=fixture('0000731766');p['facts']['us-gaap']['Revenues']=p['facts']['us-gaap'][REV]
        p['facts']['us-gaap']['StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest']=dict(units={'USD':[fact(75)]})
        p['facts']['us-gaap']['RedeemableNoncontrollingInterestEquityCarryingAmount']=dict(units={'USD':[fact(5)]})
        n=self.normalize(p,c)
        self.assertIn('including noncontrolling',row(n,'equity')['label'])
        self.assertEqual(row(n,'temporary_equity')['current']['value'],5)
        check=next(x for x in n['validation_checks'] if x['area']=='balance_sheet')
        self.assertEqual(check['result'],'pass');self.assertIn('temporary equity',check['test'])

    def test_net_income_concept_basis_is_visible(self):
        p,c=fixture();p['facts']['us-gaap']['ProfitLoss']=p['facts']['us-gaap'].pop('NetIncomeLoss')
        self.assertIn('including noncontrolling',row(self.normalize(p,c),'net_income')['label'])

    def test_stub_duration_is_not_called_quarter(self):
        p,c=fixture()
        for tag in [REV,'OperatingIncomeLoss','NetIncomeLoss','EarningsPerShareDiluted']:
            p['facts']['us-gaap'][tag]['units'][next(iter(p['facts']['us-gaap'][tag]['units']))]=[fact(100,'2026-05-01')]
        n=self.normalize(p,c)
        self.assertIsNone(row(n,'revenue')['current'])
        self.assertIn('Duration unavailable',n['sections'][0]['period_label'])

    def test_fifty_three_week_annual_period_and_prior_remain_explicit(self):
        p,c=fixture();c['filings'][0].update(form='10-K',report_period='2026-10-03',filed='2026-11-01')
        for tag, obj in p['facts']['us-gaap'].items():
            for unit in obj['units']:
                obj['units'][unit]=[fact(100,'2025-09-28','2026-10-03',form='10-K',filed='2026-11-01',fp='FY'),
                                  fact(80,'2024-09-29','2025-09-27',form='10-K',filed='2026-11-01',fp='FY')]
        n=normalize_company(p,c,'2026-11-30T00:00:00+00:00')
        self.assertEqual(n['sections'][0]['period_type'],'annual')
        self.assertEqual(row(n,'revenue')['current']['start'],'2025-09-28')
        self.assertEqual(row(n,'revenue')['prior']['start'],'2024-09-29')

    def test_negative_revenue_suppresses_margin_not_reported_value(self):
        p,c=fixture();p['facts']['us-gaap'][REV]['units']['USD'][0]['val']=-100
        n=self.normalize(p,c)
        self.assertEqual(row(n,'revenue')['current']['value'],-100)
        self.assertIsNone(row(n,'operating_margin')['current'])

    def test_metadata_only_refresh_preserves_financial_values(self):
        p,c=fixture();a=self.normalize(p,c);b=normalize_company(p,c,'2026-09-29T00:00:00+00:00')
        self.assertEqual([(r['id'],r['current']['value'] if r['current'] else None) for s in a['sections'] for r in s['rows']],
                         [(r['id'],r['current']['value'] if r['current'] else None) for s in b['sections'] for r in s['rows']])

    def test_identity_mismatch_and_absent_anchor(self):
        p,c=fixture();p['cik']=123
        with self.assertRaises(ValueError):self.normalize(p,c)
        p,c=fixture();c['filings']=[]
        self.assertEqual(self.normalize(p,c)['readiness']['status'],'not_ready')


if __name__=='__main__':unittest.main()
