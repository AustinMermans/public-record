import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from changes import compare,DEFINITION_FIELDS

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
    def test_changed_unit_rebaselines_instead_of_reporting_numerical_changes(self):
        old=snapshot('a',[['2026-07-01',100]])
        now=snapshot('b',[['2026-07-01',0.1],['2026-08-01',0.2]])
        now['series'][0]['unit']='Thousands of units'
        items=compare(old,now)['items']
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['kind'],'Series definition changed')
        self.assertEqual(items[0]['changed_fields'],['unit'])
        self.assertTrue(items[0]['comparison_boundary'])
        self.assertEqual(items[0]['before'],'unit: Units')
        self.assertEqual(items[0]['after'],'unit: Thousands of units')
        self.assertEqual(items[0]['from_capture'],'a')
        self.assertEqual(items[0]['to_capture'],'b')
        self.assertIn('new definition baseline',items[0]['summary'])
    def test_changed_measurement_definitions_require_baseline(self):
        for field in DEFINITION_FIELDS:
            with self.subTest(field=field):
                old=snapshot('a',[['2026-07-01',100]])
                now=snapshot('b',[['2026-07-01',101]])
                old['series'][0][field]='old'
                now['series'][0][field]='new'
                items=compare(old,now)['items']
                self.assertEqual([x['kind'] for x in items],['Series definition changed'])
                self.assertEqual(items[0]['changed_fields'],[field])
    def test_added_definition_metadata_is_explicit_boundary(self):
        old=snapshot('a',[['2026-07-01',100]])
        now=snapshot('b',[['2026-07-01',100]])
        now['series'][0]['universe']='FDIC-insured institutions'
        item=compare(old,now)['items'][0]
        self.assertEqual(item['before'],'universe: not specified')
        self.assertTrue(item['comparison_boundary'])
    def test_unchanged_definition_resumes_comparison_after_rebaseline(self):
        old=snapshot('a',[['2026-07-01',100]])
        boundary=snapshot('b',[['2026-07-01',0.1]])
        boundary['series'][0]['unit']='Thousands of units'
        self.assertTrue(compare(old,boundary)['items'][0]['comparison_boundary'])
        now=snapshot('c',[['2026-07-01',0.2]])
        now['series'][0]['unit']='Thousands of units'
        self.assertEqual(compare(boundary,now)['items'][0]['kind'],'Revision to observed value')
    def test_retrieval_metadata_is_not_a_definition_change(self):
        old=snapshot('a',[['2026-07-01',100]])
        now=snapshot('b',[['2026-07-01',101]])
        old['series'][0].update(captured_at='a',download_url='https://old.source.gov')
        now['series'][0].update(captured_at='b',download_url='https://new.source.gov')
        self.assertEqual(compare(old,now)['items'][0]['kind'],'Revision to observed value')
    def test_rebaseline_does_not_suppress_another_series_from_same_source(self):
        old=snapshot('a',[['2026-07-01',100]])
        now=snapshot('b',[['2026-07-01',0.1]])
        old['series'].append(dict(old['series'][0],id='y'))
        now['series'].append(dict(now['series'][0],id='y',observations=[['2026-07-01',101]]))
        now['series'][0]['unit']='Thousands of units'
        items=compare(old,now)['items']
        self.assertEqual([(x['series_id'],x['kind']) for x in items],
                         [('x','Series definition changed'),('y','Revision to observed value')])
    def test_structured_definition_equality_does_not_depend_on_key_order(self):
        old=snapshot('a',[['2026-07-01',100]])
        now=snapshot('b',[['2026-07-01',101]])
        old['series'][0]['definition']={'basis':'Quarterly','scope':'All institutions'}
        now['series'][0]['definition']={'scope':'All institutions','basis':'Quarterly'}
        self.assertEqual(compare(old,now)['items'][0]['kind'],'Revision to observed value')

if __name__=='__main__':unittest.main()
