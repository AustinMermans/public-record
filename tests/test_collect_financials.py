import gzip
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect_financials as collector


class CompanyfactsCollectionTests(unittest.TestCase):
    cik = '0000320193'
    raw = b'{"cik":320193,"facts":{"us-gaap":{}}}'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(collector, 'ROOT', self.root),
                        patch.object(collector, 'DATA', self.root / 'data/financials')]
        for p in self.patches:
            p.start()
        self.addCleanup(self.temp.cleanup)
        for p in self.patches:
            self.addCleanup(p.stop)

    def response(self, raw=None, code=0):
        return SimpleNamespace(stdout=self.raw if raw is None else raw,
                               returncode=code, stderr=b'HTTP 403' if code else b'')

    def test_identity_and_schema_required(self):
        self.assertEqual(collector.decode_payload(self.raw, self.cik)['cik'], 320193)
        for raw in (b'{"cik":1,"facts":{}}', b'{"cik":320193,"facts":[]}', b'{}'):
            with self.assertRaises(ValueError):
                collector.decode_payload(raw, self.cik)

    def test_success_is_lossless_content_addressed_and_sec_only(self):
        with patch.object(collector.subprocess, 'run', return_value=self.response()) as run:
            receipt = collector.fetch(self.cik, '2026-09-28T12:00:00+00:00', 'Test test@example.org')
        self.assertEqual(receipt['status'], 'ok')
        self.assertEqual(receipt['sha256'], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(gzip.decompress((self.root / receipt['raw_path']).read_bytes()), self.raw)
        self.assertEqual(collector.load_raw(receipt)['cik'], 320193)
        args = run.call_args.args[0]
        self.assertEqual(args[-1], f'https://data.sec.gov/api/xbrl/companyfacts/CIK{self.cik}.json')
        self.assertEqual(args[args.index('--user-agent')+1], 'Test test@example.org')

    def test_failed_refresh_keeps_last_success_evidence(self):
        with patch.object(collector.subprocess, 'run', return_value=self.response()):
            good = collector.fetch(self.cik, '2026-09-28T12:00:00+00:00', 'Test test@example.org')
        with patch.object(collector.subprocess, 'run', return_value=self.response(code=22)):
            stale = collector.fetch(self.cik, '2026-09-29T12:00:00+00:00', 'Test test@example.org')
        self.assertEqual(stale['status'], 'stale')
        for key in ('raw_path', 'sha256', 'captured_at'):
            self.assertEqual(stale[key], good[key])
        self.assertNotEqual(stale['attempted_at'], stale['captured_at'])
        self.assertEqual(collector.load_raw(stale)['cik'], 320193)

    def test_bad_identity_does_not_replace_good_capture(self):
        with patch.object(collector.subprocess, 'run', return_value=self.response()):
            good = collector.fetch(self.cik, '2026-09-28', 'Test test@example.org')
        with patch.object(collector.subprocess, 'run', return_value=self.response(b'{"cik":1,"facts":{}}')):
            stale = collector.fetch(self.cik, '2026-09-29', 'Test test@example.org')
        self.assertEqual(stale['sha256'], good['sha256'])
        self.assertEqual(stale['status'], 'stale')

    def test_missing_contact_never_requests_or_claims_success(self):
        with patch.object(collector.subprocess, 'run') as run:
            receipt = collector.fetch(self.cik, '2026-09-28', '')
        run.assert_not_called()
        self.assertEqual(receipt['status'], 'unavailable')
        self.assertNotIn('captured_at', receipt)

    def test_corrupt_raw_is_rejected(self):
        with patch.object(collector.subprocess, 'run', return_value=self.response()):
            receipt = collector.fetch(self.cik, '2026-09-28', 'Test test@example.org')
        (self.root / receipt['raw_path']).write_bytes(gzip.compress(b'{}'))
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            collector.load_raw(receipt)

    def test_private_contact_never_enters_error_receipts(self):
        agent = 'Private sentinel-contact@example.test'
        for error in (collector.subprocess.TimeoutExpired(['curl', '--user-agent', agent], 40),
                      OSError('Failure invoking curl '+agent), ValueError(agent)):
            with self.subTest(error=type(error).__name__):
                with patch.object(collector.subprocess, 'run', side_effect=error):
                    receipt = collector.fetch(self.cik, '2026-09-28', agent)
                self.assertNotIn('sentinel-contact', json.dumps(receipt))
                self.assertEqual(receipt['status'], 'unavailable')

    def test_private_contact_in_stderr_is_not_persisted(self):
        response = self.response(code=22)
        response.stderr = b'private-sentinel@example.test'
        with patch.object(collector.subprocess, 'run', return_value=response):
            receipt = collector.fetch(self.cik, '2026-09-28', 'Test test@example.org')
        self.assertNotIn('private-sentinel', json.dumps(receipt))

    def test_processing_does_not_advance_source_clocks(self):
        receipts = [dict(captured_at='2026-09-28', attempted_at='2026-09-29'),
                    dict(captured_at='2026-09-27', attempted_at='2026-09-28')]
        clocks = collector.capture_metadata(receipts, '2026-09-30')
        self.assertEqual(clocks, dict(captured_at='2026-09-28', attempted_at='2026-09-29', processed_at='2026-09-30'))
        self.assertIsNone(collector.capture_metadata([], '2026-09-30')['captured_at'])


if __name__ == '__main__':
    unittest.main()
