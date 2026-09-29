import json, sys, unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect as c
from build import event_order, validate

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
    def test_rss_guid_identity_and_merged_descriptions(self):
        s=next(x for x in c.SOURCES if x['id']=='cand')
        def item(guid,desc): return f'<item><title>Same case</title><link>https://court.gov/docket</link><guid>{guid}</guid><description><![CDATA[{desc}]]></description><pubDate>Mon, 28 Sep 2026 16:24:32 GMT</pubDate></item>'
        xml='<rss><channel>'+item('one','Notice &lt;a href="https://court.gov/doc1/1"&gt;1&lt;/a&gt;')+item('two','Summons')+item('one','Clerk notice')+'</channel></rss>'
        rows=c.parse_rss(xml,s)['records']
        self.assertEqual(len(rows),2)
        self.assertEqual(len(rows[0]['entry_descriptions']),2)
    def test_schedule_identity_survives_rescheduling(self):
        template='BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:stable\nSUMMARY:Report\nDTSTART:{}\nEND:VEVENT\nEND:VCALENDAR'
        first=c.parse_ics(template.format('20261001T123000Z'),self.s)['events'][0]
        second=c.parse_ics(template.format('20261002T123000Z'),self.s)['events'][0]
        self.assertEqual(first['id'],second['id'])
        self.assertNotEqual(first['date'],second['date'])
    def test_mixed_offset_chronology(self):
        self.assertLess(c.date_order('2026-03-12T12:30:00+00:00'),c.date_order('2026-03-12T11:30:00-04:00'))
    def test_treasury_direct_link_and_missing_amount(self):
        s=next(x for x in c.SOURCES if x['id']=='treasury')
        row={'auctionDate':'2026-09-29T00:00:00','announcementDate':'2026-09-24','issueDate':'2026-10-01','securityTerm':'6-Week','securityType':'Bill','cusip':'123','pdfFilenameAnnouncement':'A_20260924_1.pdf','offeringAmount':''}
        r=c.parse_treasury(json.dumps([row]),s)['events'][0]
        self.assertEqual(r['url'],'https://www.treasurydirect.gov/instit/annceresult/press/preanre/2026/A_20260924_1.pdf')
        self.assertIsNone(r['offering_billions'])
        self.assertIn('not supplied',r['summary'])
    def test_failure_retains_last_good_timestamp(self):
        with TemporaryDirectory() as tmp,patch.object(c,'DATA',Path(tmp)),patch.object(c.subprocess,'run',side_effect=ValueError('timeout')):
            cache=Path(tmp)/'cache';cache.mkdir()
            (cache/(self.s['id']+'.json')).write_text(json.dumps({'source':{'last_success':'2026-09-27T00:00:00+00:00','count':1,'sha256':'abc','raw_path':'data/raw/old.txt'},'events':[{'id':'old','captured_at':'2026-09-27T00:00:00+00:00'}]}))
            result=c.collect(self.s)
            self.assertEqual(result['source']['status'],'stale')
            self.assertEqual(result['events'][0]['captured_at'],'2026-09-27T00:00:00+00:00')
            self.assertEqual(result['source']['last_success'],'2026-09-27T00:00:00+00:00')
            self.assertEqual(result['source']['sha256'],'abc')
            self.assertEqual(result['source']['raw_path'],'data/raw/old.txt')
    def test_first_failure_is_unavailable(self):
        with TemporaryDirectory() as tmp,patch.object(c,'DATA',Path(tmp)),patch.object(c.subprocess,'run',side_effect=ValueError('timeout')):
            self.assertEqual(c.collect(self.s)['source']['status'],'unavailable')
    def test_snapshot_contract(self):
        p=Path(__file__).resolve().parents[1]/'data/current.json'
        if p.exists():validate(json.loads(p.read_text()))
    def test_eia_release_window_orders_between_timed_events(self):
        events=[{'id':'treasury','date':'2026-09-30T11:30:00-04:00'},
            {'id':'eia','date':'2026-09-30','time_window':'After 10:30 a.m. ET'},
            {'id':'bea','date':'2026-09-30T12:30:00+00:00'}]
        self.assertEqual([row['id'] for row in sorted(events,key=event_order)],
            ['bea','eia','treasury'])

if __name__=='__main__':unittest.main()
