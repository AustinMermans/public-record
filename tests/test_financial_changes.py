import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from financial_changes import compare_financials


def capture(stamp='2026-09-28', end='2026-06-30', value=10, **point_fields):
    point = dict(value=value, start='2026-04-01', end=end, concept='Revenues',
                 namespace='us-gaap', unit='USD', accession='a', url='https://www.sec.gov/a', **point_fields)
    return dict(captured_at=stamp, companies=[dict(cik='1', name='Issuer', captured_at=stamp,
        status='ok', sections=[dict(id='operating', rows=[dict(id='revenue', label='Revenue', current=point, prior=None)])])])


class FinancialChangeTests(unittest.TestCase):
    def test_first_capture_baseline_not_fabricated_news(self):
        diff = compare_financials(None, capture())
        self.assertEqual(diff['items'], [])
        self.assertEqual(diff['baselines'], ['sec-financials-1'])

    def test_metadata_only_is_not_financial_change(self):
        old = capture(); new = capture(stamp='2026-09-29')
        new['companies'][0]['sections'][0]['rows'][0]['current']['filed'] = '2026-07-01'
        self.assertEqual(compare_financials(old, new)['items'], [])

    def test_exact_period_revision_and_provenance(self):
        diff = compare_financials(capture(), capture(stamp='2026-09-29', value=11))
        self.assertEqual(len(diff['items']), 1)
        item = diff['items'][0]
        self.assertEqual(item['kind'], 'Revised reported financial fact')
        self.assertEqual((item['before'], item['after']), (10, 11))
        self.assertEqual(item['from_capture'], '2026-09-28')
        self.assertEqual(item['previous_url'], 'https://www.sec.gov/a')

    def test_definition_change_blocks_numeric_revision(self):
        new = capture(value=100)
        new['companies'][0]['sections'][0]['rows'][0]['current']['unit'] = 'EUR'
        item = compare_financials(capture(), new)['items'][0]
        self.assertEqual(item['kind'], 'Financial definition changed')
        self.assertTrue(item['comparison_boundary'])

    def test_new_period_not_growth_or_revision(self):
        new = capture(end='2026-09-30', value=11)
        new['companies'][0]['sections'][0]['rows'][0]['current']['start'] = '2026-07-01'
        self.assertEqual(compare_financials(capture(), new)['items'][0]['kind'], 'New financial period')

    def test_derived_input_definition_change_is_not_numeric_revision(self):
        old = capture(); new = capture(value=11)
        for data, concept in ((old, 'RevenueFromContractWithCustomerExcludingAssessedTax'), (new, 'Revenues')):
            p = data['companies'][0]['sections'][0]['rows'][0]['current']
            p.update(concept='margin', formula='100 * a / b', inputs=[dict(metric='revenue', concept=concept, unit='USD')])
        self.assertEqual(compare_financials(old, new)['items'][0]['kind'], 'Financial definition changed')

    def test_recalculation_is_not_issuer_reported_revision(self):
        old = capture(evidence_label='derived_calculation')
        new = capture(value=11, evidence_label='derived_calculation')
        self.assertEqual(compare_financials(old, new)['items'][0]['kind'], 'Recalculated financial metric')

    def test_stale_capture_skipped(self):
        new = capture(value=11); new['companies'][0]['status'] = 'stale'
        diff = compare_financials(capture(), new)
        self.assertEqual(diff['items'], [])
        self.assertEqual(diff['skipped'], ['sec-financials-1'])

    def test_disappearance_not_zero_or_withdrawal(self):
        new = capture(); new['companies'][0]['sections'][0]['rows'][0]['current'] = None
        self.assertEqual(compare_financials(capture(), new)['items'], [])

    def test_duplicate_annual_evidence_has_one_comparative_change(self):
        old = capture(); new = capture(value=11)
        annual = copy.deepcopy(old['companies'][0]['sections'][0]); annual['id'] = 'annual'
        new['companies'][0]['annual_history'] = [annual]
        self.assertEqual(len(compare_financials(old, new)['items']), 1)


if __name__ == '__main__':
    unittest.main()
