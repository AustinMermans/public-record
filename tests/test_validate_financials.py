import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_financials import validate_financials


def bundle():
    accession = '0001628280-26-000001'  # Agent filer need not share issuer CIK.
    url = 'https://www.sec.gov/Archives/edgar/data/1/000162828026000001/report.htm'
    point = dict(value=10, unit='USD', concept='Revenues', namespace='us-gaap',
                 accession=accession, url=url, source_id='s', filed='2026-08-01', form='10-Q',
                 start='2026-04-01', end='2026-06-30', evidence_label='fact_source_reported')
    return dict(schema_version=1, captured_at='2026-09-28T12:00:00+00:00', companies=[dict(
        cik='0000000001', status='ok', captured_at='2026-09-28T12:00:00+00:00',
        anchor=dict(accession=accession, form='10-Q', filed='2026-08-01', report_period='2026-06-30', url=url),
        source_index=[dict(source_id='s', file_tab_page_url_or_location=url)],
        sections=[dict(id='operating', start='2026-04-01', end='2026-06-30', rows=[dict(id='revenue', unit='USD', current=point, prior=None)])])])


class FinancialValidationTests(unittest.TestCase):
    covered = [dict(cik='0000000001')]

    def test_valid_agent_filer_accession(self):
        validate_financials(bundle(), self.covered)

    def test_identity_source_accession_currency_and_date_fail_closed(self):
        cases = [('url', 'https://www.sec.gov/Archives/edgar/data/2/000162828026000001/report.htm'),
                 ('accession', '0001628280-26-000002'), ('source_id', 'missing'),
                 ('unit', 'EUR'), ('filed', '2026-09-29'), ('value', float('nan'))]
        for field, value in cases:
            with self.subTest(field=field):
                data = bundle()
                data['companies'][0]['sections'][0]['rows'][0]['current'][field] = value
                with self.assertRaises(AssertionError):
                    validate_financials(data, self.covered)

    def test_duplicate_or_uncovered_issuer_rejected(self):
        data = bundle(); data['companies'].append(copy.deepcopy(data['companies'][0]))
        with self.assertRaises(AssertionError):
            validate_financials(data, self.covered)
        with self.assertRaises(AssertionError):
            validate_financials(bundle(), [])

    def test_comparable_requires_both_values(self):
        data = bundle(); data['companies'][0]['sections'][0]['rows'][0]['comparison_status'] = 'comparable'
        with self.assertRaises(AssertionError):
            validate_financials(data, self.covered)

    def test_derived_value_requires_traceable_inputs(self):
        data = bundle()
        p = data['companies'][0]['sections'][0]['rows'][0]['current']
        p.update(evidence_label='derived_calculation', formula='a - b', inputs=[])
        with self.assertRaises(AssertionError):
            validate_financials(data, self.covered)

    def test_point_is_bound_to_displayed_duration_and_filing(self):
        for field, value in (('start', '2026-01-01'), ('end', '2020-06-30'), ('form', '10-K'), ('filed', '2026-08-02')):
            with self.subTest(field=field):
                data = bundle()
                data['companies'][0]['sections'][0]['rows'][0]['current'][field] = value
                with self.assertRaises(AssertionError):
                    validate_financials(data, self.covered)

    def test_calculation_inputs_cannot_mix_currency(self):
        data = bundle()
        p = data['companies'][0]['sections'][0]['rows'][0]['current']
        inputs = [copy.deepcopy(p), copy.deepcopy(p)]; inputs[1]['unit'] = 'EUR'
        p.update(evidence_label='derived_calculation', formula='a - b', inputs=inputs)
        with self.assertRaisesRegex(AssertionError, 'incompatible units'):
            validate_financials(data, self.covered)


if __name__ == '__main__':
    unittest.main()
