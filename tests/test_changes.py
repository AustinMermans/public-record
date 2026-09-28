import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from changes import compare

def snapshot(stamp,values,records=None,status='ok'):
    return {'captured_at':stamp,'sources':[{'id':'s','name':'Source','last_success':stamp,'status':status}],'records':records or [],'events':[],'series':[{'id':'x','source_id':'s','name':'Series','url':'https://source.gov','unit':'Units','observations':values}]}

class ChangeTests(unittest.TestCase):
    def test_revision_and_new_period_are_distinct(self):
        old=snapshot('2026-09-27',[['2026-07-01',100]])
        now=snapshot('2026-09-28',[['2026-07-01',101],['2026-08-01',102]])
        self.assertEqual([x['kind'] for x in compare(old,now)['items']],['Revision to observed value','New observation period'])
    def test_failed_source_not_compared(self):
        old=snapshot('a',[['2026-07-01',100]])
        now=snapshot('b',[['2026-07-01',999]],status='stale')
        self.assertFalse(compare(old,now)['items'])
    def test_departed_record_not_withdrawal(self):
        old=snapshot('a',[['2026-07-01',100]],[{'id':'one','source_id':'s'}])
        now=snapshot('b',[['2026-07-01',100]])
        self.assertFalse(compare(old,now)['items'])
    def test_first_capture_is_baseline(self):
        now=snapshot('b',[['2026-07-01',100]])
        self.assertEqual(compare(None,now)['baselines'],['s'])
    def test_schedule_change_keeps_identity(self):
        old=snapshot('a',[['2026-07-01',100]]);now=snapshot('b',[['2026-07-01',100]])
        old['events']=[{'id':'same','source_id':'s','title':'GDP','url':'https://source.gov','date':'2026-10-01'}]
        now['events']=[dict(old['events'][0],date='2026-10-02')]
        self.assertEqual(compare(old,now)['items'][0]['kind'],'Schedule changed')

if __name__=='__main__':unittest.main()
