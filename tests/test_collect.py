import json, sys, unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect as c
from build import validate

class CollectTests(unittest.TestCase):
    def setUp(self): self.s=c.SOURCES[0]
    def test_ics_unfold_and_dst(self):
        body='BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:a\nSUMMARY:Employment\\, Situa\n tion\nDTSTART;TZID=America/New_York:20261106T083000\nEND:VEVENT\nEND:VCALENDAR'
        result=c.parse_ics(body,self.s)['events'][0]
        self.assertEqual(result['title'],'Employment, Situation')
        self.assertEqual(result['date'],'2026-11-06T08:30:00-05:00')
    def test_ics_date_only(self):
        body='BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Date only\nDTSTART;VALUE=DATE:20261002\nEND:VEVENT\nEND:VCALENDAR'
        self.assertEqual(c.parse_ics(body,self.s)['events'][0]['date'],'2026-10-02')
    def test_200_html_not_success(self):
        with self.assertRaises(ValueError):c.parse_ics('<html>Access denied</html>',self.s)
        with self.assertRaises(ValueError):c.parse_fred('<html>Oops</html>',c.SOURCES[-1])
    def test_fred_missing_not_zero(self):
        s=c.SOURCES[-1]
        rows=c.parse_fred('observation_date,DFF\n2026-09-01,3.5\n2026-09-02,.\n2026-09-03,3.6',s)['series'][0]['observations']
        self.assertEqual(rows,[['2026-09-01',3.5],['2026-09-03',3.6]])
    def test_inspection_date_not_publication(self):
        s=next(x for x in c.SOURCES if x['id']=='inspection')
        result=c.parse_register(json.dumps({'results':[{'title':'A rule','type':'Rule','document_number':'1','html_url':'https://example.gov/1','filed_at':'2026-09-28T08:45:00-04:00','publication_date':'2026-09-29'}]}),s)
        self.assertEqual(result['records'][0]['date'],'2026-09-28T08:45:00-04:00')
        self.assertEqual(result['events'][0]['date'],'2026-09-29')
        self.assertEqual(result['records'][0]['kind'],'Public inspection')
    def test_unsafe_url_rejected(self): self.assertEqual(c.safe_url('javascript:alert(1)'), '')
    def test_failure_retains_last_good_timestamp(self):
        with TemporaryDirectory() as tmp,patch.object(c,'DATA',Path(tmp)),patch.object(c.subprocess,'run',side_effect=ValueError('timeout')):
            cache=Path(tmp)/'cache';cache.mkdir()
            (cache/(self.s['id']+'.json')).write_text(json.dumps({'source':{'last_success':'2026-09-27T00:00:00+00:00','count':1},'events':[{'id':'old','captured_at':'2026-09-27T00:00:00+00:00'}]}))
            result=c.collect(self.s)
            self.assertEqual(result['source']['status'],'stale')
            self.assertEqual(result['events'][0]['captured_at'],'2026-09-27T00:00:00+00:00')
            self.assertEqual(result['source']['last_success'],'2026-09-27T00:00:00+00:00')
    def test_first_failure_is_unavailable(self):
        with TemporaryDirectory() as tmp,patch.object(c,'DATA',Path(tmp)),patch.object(c.subprocess,'run',side_effect=ValueError('timeout')):
            self.assertEqual(c.collect(self.s)['source']['status'],'unavailable')
    def test_snapshot_contract(self):
        p=Path(__file__).resolve().parents[1]/'data/current.json'
        if p.exists():validate(json.loads(p.read_text()))

if __name__=='__main__':unittest.main()
