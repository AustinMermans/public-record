import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect
import corporate
from collection_errors import safe_sec_error


class PrivateRequestIdentityTests(unittest.TestCase):
    sentinel = 'Secret sentinel-contact@example.test'

    def test_safe_message_never_serializes_exception_arguments(self):
        for error in (subprocess.TimeoutExpired(['curl', self.sentinel], 40),
                      OSError(self.sentinel), ValueError(self.sentinel)):
            self.assertNotIn('sentinel-contact', safe_sec_error(error))

    def test_sec_rolling_feed_error_is_sanitized(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(collect, 'DATA', Path(temp)), \
             patch.dict(os.environ, SEC_USER_AGENT=self.sentinel), \
             patch.object(collect.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['curl', self.sentinel], 90)):
            result = collect.collect(next(s for s in collect.SOURCES if s['id'] == 'sec'))
        self.assertNotIn('sentinel-contact', json.dumps(result))
        self.assertEqual(result['source']['status'], 'unavailable')

    def test_company_submissions_timeout_is_sanitized(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(corporate, 'DATA', Path(temp)), \
             patch.object(corporate, 'UNIVERSE', ['0000320193']), patch.object(corporate.time, 'sleep'), \
             patch.dict(os.environ, SEC_USER_AGENT=self.sentinel), \
             patch.object(corporate.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['curl', self.sentinel], 40)):
            corporate.main()
            text = (Path(temp) / 'current.json').read_text()
        self.assertNotIn('sentinel-contact', text)
        self.assertEqual(json.loads(text)['companies'][0]['status'], 'unavailable')
