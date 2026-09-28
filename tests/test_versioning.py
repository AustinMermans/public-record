import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from versioning import validate_release


class VersioningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write('VERSION', '1.3.0\n')
        self.write('CITATION.cff', 'cff-version: 1.2.0\nversion: 1.3.0\ndate-released: 2026-09-28\n')
        self.write('CHANGELOG.md', '# Changelog\n\n## Unreleased\n\n## 1.3.0 — 2026-09-28\n\nRelease notes.\n')

    def write(self, name, value):
        (self.root / name).write_text(value)

    def test_matching_metadata_and_tag(self):
        self.assertEqual(validate_release(self.root, 'v1.3.0'), '1.3.0')

    def test_rejects_malformed_or_unreleased_version(self):
        for value in ('v1.3.0', '01.3.0', '1.3', '1.4.0-dev', '1.3.0\n1.4.0'):
            with self.subTest(value=value):
                self.write('VERSION', value)
                with self.assertRaises(ValueError):
                    validate_release(self.root)

    def test_rejects_stale_citation(self):
        self.write('CITATION.cff', 'version: 1.2.0\ndate-released: 2026-09-28\n')
        with self.assertRaises(ValueError):
            validate_release(self.root)

    def test_rejects_stale_changelog(self):
        self.write('CHANGELOG.md', '## 1.2.0 — 2026-09-28\n')
        with self.assertRaises(ValueError):
            validate_release(self.root)

    def test_rejects_mismatched_date(self):
        self.write('CHANGELOG.md', '## 1.3.0 — 2026-09-27\n')
        with self.assertRaises(ValueError):
            validate_release(self.root)

    def test_rejects_duplicate_release(self):
        self.write('CHANGELOG.md', '## 1.3.0 — 2026-09-28\n\n## 1.3.0 — 2026-09-28\n')
        with self.assertRaises(ValueError):
            validate_release(self.root)

    def test_rejects_wrong_tag(self):
        with self.assertRaises(ValueError):
            validate_release(self.root, 'v1.4.0')

    def test_repository_metadata(self):
        validate_release()


if __name__ == '__main__':
    unittest.main()
