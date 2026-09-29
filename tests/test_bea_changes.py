import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bea_changes import compare_bea_releases


def release(quarter, stage, value):
    return dict(quarter=quarter, stage=stage, value=value, display_value=f'{value:.1f}', published_at='2026-08-26',
                url='https://www.bea.gov/news/2026/gdp-second-estimate-2nd-quarter-2026')


def capture(rows, stamp='2026-08-26T14:00:00Z', status='ok'):
    return dict(status=status, captured_at=stamp, releases=rows)


class BEAChangesTests(unittest.TestCase):
    def test_first_capture_is_baseline(self):
        result = compare_bea_releases(None, capture([release('2026Q2','advance',1.5)]))
        self.assertEqual(result['baselines'], ['bea-gdp-releases'])
        self.assertEqual(result['items'], [])

    def test_new_stage_is_one_item_and_repoll_is_not_news(self):
        old = capture([release('2026Q2','advance',1.5)])
        new = capture([*old['releases'],release('2026Q2','second',1.5)], '2026-08-27T14:00:00Z')
        diff = compare_bea_releases(old,new)
        self.assertEqual(len(diff['items']),1)
        self.assertEqual(diff['items'][0]['target'],'2026Q2')
        self.assertEqual(diff['items'][0]['before'],1.5)
        self.assertEqual(diff['items'][0]['after'],1.5)
        self.assertIn('hidden by rounding',diff['items'][0]['summary'])
        self.assertEqual(compare_bea_releases(new,capture(new['releases'],'2026-08-28T14:00:00Z'))['items'],[])

    def test_stale_check_skips_comparison(self):
        old = capture([release('2026Q2','advance',1.5)])
        stale = capture([*old['releases'],release('2026Q2','second',1.5)],status='stale')
        result = compare_bea_releases(old,stale)
        self.assertEqual(result['skipped'],['bea-gdp-releases'])
        self.assertEqual(result['items'],[])


if __name__ == '__main__':
    unittest.main()
