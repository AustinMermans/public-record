"""Fail publication when the release version, citation and changelog diverge."""
import argparse
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STABLE_VERSION = r'(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)'


def validate_release(root=ROOT, tag=None):
    version = (root / 'VERSION').read_text().strip()
    if not re.fullmatch(STABLE_VERSION, version):
        raise ValueError('VERSION must be a stable MAJOR.MINOR.PATCH without a v prefix')
    citation = (root / 'CITATION.cff').read_text()
    versions = re.findall(r'^version:\s*(\S+)\s*$', citation, re.M)
    dates = re.findall(r'^date-released:\s*(\S+)\s*$', citation, re.M)
    if versions != [version] or len(dates) != 1:
        raise ValueError('CITATION.cff must contain the VERSION and one release date')
    date.fromisoformat(dates[0])
    entries = re.findall(r'^## (' + STABLE_VERSION + r') — (\d{4}-\d{2}-\d{2})\s*$',
                         (root / 'CHANGELOG.md').read_text(), re.M)
    if not entries or entries[0] != (version, dates[0]):
        raise ValueError('Latest released changelog entry must match VERSION and citation date')
    if len({v for v, _ in entries}) != len(entries):
        raise ValueError('Changelog contains duplicate release versions')
    for _, released in entries:
        date.fromisoformat(released)
    if tag is not None and tag != f'v{version}':
        raise ValueError(f'Release tag must be v{version}, not {tag}')
    return version


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', help='Also validate a proposed release tag')
    args = parser.parse_args()
    print(f'Release metadata consistent: v{validate_release(tag=args.tag)}')
