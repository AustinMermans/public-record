"""Publication gate for normalized financial identity and evidence links."""
import math
import re
from datetime import date, datetime


def validate_financials(bundle, covered_companies):
    assert bundle['schema_version'] == 1
    if bundle.get('captured_at'):
        datetime.fromisoformat(bundle['captured_at'])
    covered = {c['cik'] for c in covered_companies}
    seen = set()
    for company in bundle['companies']:
        cik = company['cik']
        assert cik in covered and cik not in seen, 'Unknown or duplicate financial CIK'
        seen.add(cik)
        assert company['status'] in ('ok', 'stale', 'unavailable')
        if company.get('captured_at'):
            datetime.fromisoformat(company['captured_at'])
        prefix = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/'
        anchor = company.get('anchor')
        if anchor:
            assert anchor['url'].startswith(prefix), 'Anchor URL issuer mismatch'
            assert date.fromisoformat(anchor['report_period']) <= date.fromisoformat(anchor['filed'])
        sources = {s['source_id']: s for s in company.get('source_index', [])}
        assert len(sources) == len(company.get('source_index', [])), 'Duplicate source ID'

        def point(p):
            assert isinstance(p['value'], (int, float)) and not isinstance(p['value'], bool) and math.isfinite(p['value'])
            assert p['source_id'] in sources, 'Missing evidence index entry'
            assert p['url'].startswith(prefix), 'Financial URL issuer mismatch'
            assert re.fullmatch(r'\d{10}-\d{2}-\d{6}', p['accession'])
            assert '/' + p['accession'].replace('-', '') + '/' in p['url'], 'Financial accession URL mismatch'
            assert sources[p['source_id']]['file_tab_page_url_or_location'] == p['url']
            assert p['unit'] and p['concept']
            assert date.fromisoformat(p['end']) <= date.fromisoformat(p['filed'])
            assert p['filed'] <= company['captured_at'][:10], 'Fact filed after capture'
            if p.get('start'):
                assert date.fromisoformat(p['start']) <= date.fromisoformat(p['end'])
            assert p['evidence_label'] in ('fact_source_reported', 'derived_calculation', 'contradicted_source')
            if p['evidence_label'] == 'derived_calculation':
                assert p.get('formula') and len(p.get('inputs', [])) == 2
                assert p['inputs'][0]['unit'] == p['inputs'][1]['unit'], 'Calculation inputs use incompatible units'
                assert p['unit'] in (p['inputs'][0]['unit'], 'Percent'), 'Calculation result has incompatible unit'
                for item in p['inputs']:
                    point(item)
                    assert (item.get('start'), item['end'], item['accession']) == (p.get('start'), p['end'], p['accession'])

        for section in [*company.get('sections', []), *company.get('annual_history', [])]:
            assert len({r['id'] for r in section['rows']}) == len(section['rows'])
            section_anchor = section.get('anchor') or anchor
            for row in section['rows']:
                for name in ('current', 'prior'):
                    p = row.get(name)
                    if p:
                        point(p)
                        assert p['unit'] == row['unit']
                        assert section_anchor, 'Financial value without filing anchor'
                        assert p['accession'] == section_anchor['accession'], 'Value belongs to another filing'
                        assert p['filed'] == section_anchor['filed'] and p['form'] == section_anchor['form']
                        if name == 'current':
                            assert p['end'] == section['end'] == section_anchor['report_period'], 'Value period differs from displayed period'
                            assert p.get('start') == section.get('start'), 'Value duration differs from displayed duration'
                        else:
                            assert p['end'] < section['end'], 'Comparative period must precede current period'
                if row.get('comparison_status') == 'comparable':
                    a, b = row['current'], row['prior']
                    assert a and b and a['concept'] == b['concept'] and a['unit'] == b['unit']
                for p in row.get('conflicts', []):
                    point(p)
