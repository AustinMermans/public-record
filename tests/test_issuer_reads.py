"""Curated exhibit interpretation must survive exact-source and event gates."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from earnings_dossiers import assemble_dossiers
from issuer_reads import attach_issuer_reads


class IssuerReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corporate = json.loads((ROOT/'data/corporate/current.json').read_text())
        cls.briefs = json.loads((ROOT/'data/business_briefs/current.json').read_text())
        cls.financials = json.loads((ROOT/'data/financials/current.json').read_text())
        cls.catalogue = json.loads((ROOT/'data/issuer_reads/catalog.json').read_text())

    def assembled(self):
        return assemble_dossiers(self.corporate, self.briefs, self.financials, ROOT)

    def test_six_exact_latest_events_are_attached(self):
        result = attach_issuer_reads(self.assembled(), self.briefs, self.catalogue, ROOT)
        self.assertEqual(result['issuer_reads'], 6)
        attached = {d['cik']: d for d in result['dossiers'] if d.get('issuer_read')}
        self.assertEqual(set(attached), {'0001018724', '0000059478', '0000354950',
                                         '0000019617', '0002115436', '0000018230'})
        for cik, dossier in attached.items():
            read = dossier['issuer_read']
            self.assertEqual(dossier['issuer_read_state'], 'reviewed')
            self.assertEqual(read['exhibit_accession'], dossier['event']['accession'])
            self.assertEqual(read['source_url'], dossier['event']['exhibit_url'])
            self.assertTrue(read['source_url'].startswith('https://www.sec.gov/Archives/edgar/data/'+str(int(cik))+'/'))
            self.assertNotEqual(read['exhibit_accession'], dossier['financial']['anchor']['accession'])

    def test_new_result_supersedes_old_read_without_publishing_it(self):
        dossier = self.assembled()
        target = next(x for x in dossier['dossiers'] if x['cik'] == '0000354950')
        target['event']['accession'] = '0000354950-26-NEWER'
        result = attach_issuer_reads(dossier, self.briefs, self.catalogue, ROOT)
        self.assertEqual(result['issuer_reads'], 5)
        self.assertNotIn('issuer_read', target)
        self.assertEqual(target['issuer_read_state'], 'successor_needs_review')

    def test_reattachment_clears_a_prior_read_after_successor_event(self):
        dossier = attach_issuer_reads(self.assembled(), self.briefs, self.catalogue, ROOT)
        target = next(x for x in dossier['dossiers'] if x['cik'] == '0000354950')
        self.assertIn('issuer_read', target)
        target['event']['accession'] = '0000354950-26-NEWER'
        result = attach_issuer_reads(dossier, self.briefs, self.catalogue, ROOT)
        self.assertEqual(result['issuer_reads'], 5)
        self.assertNotIn('issuer_read', target)
        self.assertEqual(target['issuer_read_state'], 'successor_needs_review')

    def test_changed_source_line_period_or_sha_fail_closed(self):
        for mutation in ('line', 'period', 'source', 'cue'):
            catalogue = copy.deepcopy(self.catalogue)
            item = catalogue['reads'][0]
            if mutation == 'line':
                item['claims'][0]['evidence'][0]['sha256'] = '0'*64
            elif mutation == 'period':
                item['period_end'] = '2026-03-31'
            else:
                if mutation == 'source':
                    item['source_sha256'] = '0'*64
                else:
                    item['claims'][0]['source_cue'] = 'not in the verified SEC exhibit'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                attach_issuer_reads(self.assembled(), self.briefs, catalogue, ROOT)

    def test_unmatched_dossier_never_gets_editorial_read(self):
        dossier = self.assembled()
        target = next(x for x in dossier['dossiers'] if x['cik'] == '0001018724')
        target['status'] = 'period_mismatch'
        result = attach_issuer_reads(dossier, self.briefs, self.catalogue, ROOT)
        self.assertEqual(result['issuer_reads'], 5)
        self.assertNotIn('issuer_read', target)

    def test_matched_without_curated_read_is_marked_unreviewed(self):
        result = attach_issuer_reads(self.assembled(), self.briefs, self.catalogue, ROOT)
        candidates = [d for d in result['dossiers'] if d.get('status') in ('matched', 'stale_matched')
                      and d['cik'] not in {r['cik'] for r in self.catalogue['reads']}]
        self.assertTrue(candidates)
        self.assertTrue(all(d['issuer_read_state'] == 'not_reviewed' and not d.get('issuer_read')
                            for d in candidates))

    def test_new_raw_bytes_need_the_same_entire_visible_exhibit(self):
        item = next(x for x in self.catalogue['reads'] if x['cik'] == '0001018724')
        source = ROOT/'data/business_briefs/raw'/f'{item["source_sha256"]}.html'
        original = source.read_bytes()
        amazon = copy.deepcopy(next(b for b in self.briefs['briefs'] if b['cik'] == item['cik'] and b['accession'] == item['event_accession']))
        dossier = self.assembled()
        with TemporaryDirectory() as directory:
            raw_dir = Path(directory)/'data/business_briefs/raw'
            raw_dir.mkdir(parents=True)
            (raw_dir/source.name).write_bytes(original)
            def check(payload):
                digest = hashlib.sha256(payload).hexdigest()
                path = raw_dir/f'{digest}.html'
                path.write_bytes(payload)
                amazon['source'].update(sha256=digest, raw_path=f'data/business_briefs/raw/{digest}.html')
                return attach_issuer_reads(copy.deepcopy(dossier), {'briefs': [amazon]},
                                           {'schema_version': 1, 'reads': [item]}, Path(directory))
            self.assertEqual(check(original+b'\n')['issuer_reads'], 1)
            changed = original.replace(b'AWS segment sales increased 37%', b'AWS segment sales increased 38%', 1)
            self.assertNotEqual(changed, original)
            with self.assertRaisesRegex(ValueError, 'visible exhibit changed'):
                check(changed)


if __name__ == '__main__':
    unittest.main()
