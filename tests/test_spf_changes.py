import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publication_changes import SPF_MEASURES, compare_spf


def point(survey, target, value, cell='RGDP!C2'):
    year, quarter = int(survey[:4]), int(survey[-1])
    return dict(survey=survey, target=target, value=value, cell=cell,
                released={1:'2026-02-13',2:'2026-05-15',3:'2026-08-14'}[quarter])


def capture():
    return dict(status='ok',captured_at='2026-08-15T12:00:00Z',
        sources={key:dict(url='https://www.philadelphiafed.org/'+key+'.xlsx',sha256='a'*64)
                   for key in ('medianGrowth','medianLevel','release_dates')},
        series={m:dict(unit='percent annualized q/q' if m!='UNEMP' else 'percent quarterly average',
                       points=[point('2026Q2','2026Q4',1.6,m+'!D2')]) for m in SPF_MEASURES})


class SPFChangeTests(unittest.TestCase):
    def test_fixed_target_revision_and_new_horizon_are_distinct(self):
        old=capture();new=copy.deepcopy(old);new['captured_at']='2026-08-16T12:00:00Z'
        for m in SPF_MEASURES:
            new['series'][m]['points'].extend([point('2026Q3','2026Q4',2.3,m+'!C3'),
                                               point('2026Q3','2027Q3',2.2,m+'!D3')])
        changes=compare_spf(old,new)
        matched=[x for x in changes['items'] if x['metric_id']=='RGDP']
        self.assertEqual([(x['target'],x['kind']) for x in matched],
                         [('2026Q4','Updated forecast projection'),('2027Q3','New forecast horizon')])
        self.assertEqual(matched[0]['previous_survey'],'2026Q2')
        self.assertIsNone(matched[1]['before'])
        self.assertEqual(changes['channels'][0]['status'],'compared')

    def test_same_survey_workbook_correction_is_not_new_forecaster_revision(self):
        old=capture();new=copy.deepcopy(old);new['captured_at']='2026-08-16T12:00:00Z'
        new['series']['RGDP']['points'][0]['value']=1.7
        changes=compare_spf(old,new)
        self.assertEqual(len(changes['items']),1)
        self.assertEqual(changes['items'][0]['kind'],'Historical survey value changed')

    def test_missed_release_cycle_retains_each_intervening_survey(self):
        old=capture()
        for series in old['series'].values():
            series['points'][0]=point('2026Q1','2026Q4',1.0,'RGDP!E1')
        new=copy.deepcopy(old)
        new['captured_at']='2026-08-16T12:00:00Z'
        for metric in SPF_MEASURES:
            new['series'][metric]['points'].extend([
                point('2026Q2','2026Q4',1.6,metric+'!D2'),
                point('2026Q3','2026Q4',2.3,metric+'!C3'),
                point('2026Q3','2027Q3',2.2,metric+'!D3')])
        rows=[x for x in compare_spf(old,new)['items'] if x['metric_id']=='RGDP']
        self.assertEqual([(x['survey'],x['target'],x['kind']) for x in rows],
                         [('2026Q2','2026Q4','Updated forecast projection'),
                          ('2026Q3','2026Q4','Updated forecast projection'),
                          ('2026Q3','2027Q3','New forecast horizon')])
        self.assertEqual([x['previous_survey'] for x in rows[:2]],['2026Q1','2026Q2'])

    def test_stale_and_first_capture_never_invent_numeric_change(self):
        current=capture()
        self.assertEqual(compare_spf(None,current)['baselines'],['research-spf'])
        stale=copy.deepcopy(current);stale['status']='stale';stale['attempted_at']='2026-08-20T12:00:00Z'
        self.assertEqual(compare_spf(current,stale)['skipped'],['research-spf'])
        self.assertFalse(compare_spf(current,stale)['items'])

    def test_malformed_duplicate_points_skip_comparison(self):
        old=capture();new=copy.deepcopy(old);new['series']['RGDP']['points'].append(new['series']['RGDP']['points'][0])
        self.assertEqual(compare_spf(old,new)['skipped'],['research-spf'])


if __name__=='__main__':unittest.main()
