import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from fiscal import (BASIS, FIELDS, MONTH_FIELDS, FiscalError, amount, collect_fiscal,
                    compare_fiscal, dollars, endpoint, fiscal_periods, normalize_fiscal, validate_fiscal)

STAMP = '2025-12-10T12:00:00+00:00'
EDITION = '2025-11-30'


def fixture():
    """Two current FY months; full prior FY with a surplus in April."""
    counter = 0
    def row(table, label, parent='null', dtype='S', rtype='SL', **extra):
        nonlocal counter
        counter += 1
        return dict(record_date=EDITION, table_nbr=str(table), classification_id=str(counter),
            classification_desc=label, parent_id=parent, data_type_cd=dtype, record_type_cd=rtype,
            sequence_level_nbr='1' if parent=='null' else '2', record_fiscal_year='2026',
            record_calendar_year='2025', record_calendar_month='11', record_calendar_day='30', **extra)
    def actuals(month, current, prior):
        return dict(zip(FIELDS.values(), map(lambda v: dollars(amount(str(v))), [month, current, prior])))
    tables = {1: [], 3: [], 9: []}
    r = row(3, 'Budget Receipts'); o = row(3, 'Budget Outlays'); tables[3].extend([r, o])
    tables[3].extend([
        row(3, 'Total Receipts', r['classification_id'], 'T', **actuals(120, 240, 200)),
        row(3, 'Total Outlays', o['classification_id'], 'T', **actuals(150, 300, 260)),
        row(3, 'Surplus (+) or Deficit (-)', o['classification_id'], 'T', **actuals(-30, -60, -60)),
        row(3, 'Interest on Treasury Debt Securities (Gross)', o['classification_id'], 'D', **actuals(999, 9999, 8888))])
    r = row(9, 'Receipts'); o = row(9, 'Net Outlays'); tables[9].extend([r, o])
    tables[9].extend([
        row(9, 'Total', r['classification_id'], 'T', **actuals(120, 240, 200)),
        row(9, 'Total', o['classification_id'], 'T', **actuals(150, 300, 260)),
        row(9, 'Net Interest', o['classification_id'], 'D', 'F', **actuals(20, 40, 30))])
    names = ['October', 'November', 'December', 'January', 'February', 'March',
             'April', 'May', 'June', 'July', 'August', 'September']
    for year, names_used in [(2025, names), (2026, names[:2])]:
        parent = row(1, 'FY '+str(year)); tables[1].append(parent)
        sums = dict(receipts=0, outlays=0, balance=0)
        for name in names_used:
            receipts, outlays = (120, 150) if year == 2026 else (200 if name=='April' else 100, 130)
            amounts = dict(receipts=receipts, outlays=outlays, balance=outlays-receipts)
            for k, v in amounts.items(): sums[k] += v
            tables[1].append(row(1, name, parent['classification_id'], 'D', 'MTH',
                **{MONTH_FIELDS[k]: dollars(amount(str(v))) for k, v in amounts.items()}))
        tables[1].append(row(1, 'Year-to-Date', parent['classification_id'], 'T',
            **{MONTH_FIELDS[k]: dollars(amount(str(v))) for k, v in sums.items()}))
    payloads = {}
    receipts = []
    for table, rows in tables.items():
        fields = MONTH_FIELDS.values() if table == 1 else FIELDS.values()
        payloads[table] = dict(data=rows, meta={'count': len(rows), 'total-count': len(rows), 'total-pages': 1,
            'dataTypes': dict.fromkeys(fields, 'CURRENCY'), 'dataFormats': dict.fromkeys(fields, '$10.20')}, links={'next': None})
        body = json.dumps(payloads[table]).encode()
        digest = hashlib.sha256(body).hexdigest()
        receipts.append(dict(table=table, edition=EDITION, captured_at=STAMP, url=endpoint(table, EDITION),
            sha256=digest, raw_path='data/fiscal/raw/'+digest+'.json'))
    return payloads, receipts


def screen():
    return normalize_fiscal(*fixture(), STAMP)


class FiscalNormalizationTests(unittest.TestCase):
    def test_exact_dollars_and_matched_prior_period_not_full_prior_year(self):
        data = screen(); metrics = {m['id']: m for m in data['metrics']}
        self.assertEqual(metrics['receipts']['current_month'], '120.00')
        self.assertEqual(metrics['receipts']['prior_fytd'], '200.00')
        self.assertEqual(metrics['balance']['current_fytd'], '-60.00')
        self.assertEqual(metrics['net_interest']['current_fytd'], '40.00')
        self.assertEqual(data['periods']['prior_fytd'], {'start':'2024-10-01', 'end':'2024-11-30'})
        self.assertEqual(data['monthly'][0]['date'], '2024-10-31')
        self.assertEqual(data['monthly'][-1]['date'], '2025-11-30')
        self.assertEqual(len(data['monthly']), 14)
        self.assertIsNone(data['publication_date'])
        self.assertEqual(data['basis'], BASIS)

    def test_bridge_exact_and_balance_sign_preserves_surpluses(self):
        data = screen(); b = data['bridge']
        self.assertEqual([b[k] for k in ['net_interest_change','other_outlays_change','receipts_contribution','deficit_change','residual']],
                         ['10.00','30.00','-40.00','0.00','0.00'])
        april = next(r for r in data['monthly'] if r['date']=='2025-04-30')
        self.assertEqual((april['balance'], april['source_balance']), ('70.00','-70.00'))

    def test_decimal_cents_not_binary_float_and_bad_amounts_rejected(self):
        self.assertEqual(amount('0.10')+amount('0.20'), amount('0.30'))
        for bad in [None, 'null', 'NaN', 'Infinity', '1e6', '1.001', 1, 1.2, True, '']:
            with self.subTest(value=bad), self.assertRaises(FiscalError): amount(bad)

    def test_budget_estimates_do_not_enter_actuals(self):
        p, receipts = fixture()
        for row in p[3]['data']: row['current_year_budget_est_amt'] = '99999999999999999.00'
        self.assertEqual(normalize_fiscal(p, receipts, STAMP)['metrics'], screen()['metrics'])

    def test_missing_duplicate_or_wrong_parent_metrics_rejected(self):
        for mode in ['missing', 'duplicate', 'parent', 'header']:
            p, receipts = fixture(); rows = p[3]['data']; target = next(r for r in rows if r['classification_desc']=='Total Receipts')
            if mode=='missing': rows.remove(target)
            elif mode=='duplicate': rows.append(dict(target, classification_id='999'))
            elif mode=='parent': target['parent_id'] = 'nonexistent'
            else: target['data_type_cd'] = 'S'
            p[3]['meta'].update(count=len(rows), **{'total-count':len(rows)})
            with self.subTest(mode=mode), self.assertRaises(FiscalError): normalize_fiscal(p, receipts, STAMP)

    def test_edition_table_currency_metadata_and_incomplete_pages_rejected(self):
        for mode in ['edition','table','year','currency','format','page','duplicateid']:
            p, receipts = fixture()
            if mode=='edition': p[9]['data'][0]['record_date'] = '2025-10-31'
            elif mode=='table': p[9]['data'][0]['table_nbr'] = '3'
            elif mode=='year': p[9]['data'][0]['record_fiscal_year'] = '2025'
            elif mode=='currency': p[9]['meta']['dataTypes'][FIELDS['current_month']] = 'NUMBER'
            elif mode=='format': p[9]['meta']['dataFormats'][FIELDS['current_month']] = 'Millions'
            elif mode=='page': p[9]['meta']['total-pages'] = 2
            else: p[9]['data'][1]['classification_id'] = p[9]['data'][0]['classification_id']
            with self.subTest(mode=mode), self.assertRaises(FiscalError): normalize_fiscal(p, receipts, STAMP)

    def test_balance_total_and_net_interest_identity_fail_closed(self):
        for mode in ['balance','total9','interest']:
            p, receipts = fixture()
            if mode=='balance': next(r for r in p[3]['data'] if r['classification_desc'].startswith('Surplus'))[FIELDS['current_month']] = '30.00'
            elif mode=='total9': next(r for r in p[9]['data'] if r['classification_desc']=='Total')[FIELDS['current_month']] = '1.00'
            else: next(r for r in p[9]['data'] if r['classification_desc']=='Net Interest')['record_type_cd'] = 'P'
            with self.subTest(mode=mode), self.assertRaises(FiscalError): normalize_fiscal(p, receipts, STAMP)

    def test_month_hierarchy_missing_or_repeated_month_and_source_sign_rejected(self):
        for mode in ['year','month','missing','sign']:
            p, receipts = fixture(); rows = p[1]['data']
            monthly = next(r for r in rows if r.get('record_type_cd')=='MTH')
            if mode=='year': rows[0]['classification_desc']='FY 2024'
            elif mode=='month': monthly['classification_desc']='November'
            elif mode=='missing': rows.remove(monthly)
            else: monthly['current_month_dfct_sur_amt']='-30.00'
            p[1]['meta'].update(count=len(rows), **{'total-count':len(rows)})
            with self.subTest(mode=mode), self.assertRaises(FiscalError): normalize_fiscal(p, receipts, STAMP)

    def test_receipt_edition_and_url_must_match(self):
        p, receipts=fixture(); receipts[0]['edition']='2025-10-31'
        with self.assertRaises(FiscalError): normalize_fiscal(p, receipts, STAMP)
        p, receipts=fixture(); receipts[0]['url']=endpoint(9,EDITION)
        with self.assertRaises(FiscalError): normalize_fiscal(p, receipts, STAMP)

    def test_february_leap_day_prior_cutoff(self):
        p=fiscal_periods('2024-02-29')
        self.assertEqual(p['prior_fytd']['end'], '2023-02-28')
        with self.assertRaises(FiscalError): fiscal_periods('2024-02-28')

    def test_validator_rejects_extra_month_missing_zero_month_or_bad_bridge(self):
        for mode in ['future','zero','bridge']:
            data=screen()
            if mode=='future': data['monthly'].append(dict(data['monthly'][-1], date='2025-12-31'))
            elif mode=='zero':
                # A missing zero-valued older month cannot hide behind aggregate sums.
                data['monthly'][4].update(receipts='0.00',outlays='0.00',balance='0.00',source_balance='0.00')
                del data['monthly'][4]
            else: data['bridge']['net_interest_change']='11.00'
            with self.subTest(mode=mode), self.assertRaises(FiscalError): validate_fiscal(data)

    def test_raw_binding_rejects_balanced_tampering_and_fake_identity(self):
        payloads, receipts=fixture(); original=normalize_fiscal(payloads,receipts,STAMP)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for receipt in receipts:
                path=root/receipt['raw_path']; path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps(payloads[receipt['table']]))
            validate_fiscal(original,raw_root=root)
            stale=copy.deepcopy(original); stale.update(status='stale', attempted_at='2025-12-11T12:00:00+00:00')
            validate_fiscal(stale,raw_root=root)
            for mode in ['identity','balanced','path','hash']:
                data=copy.deepcopy(original)
                if mode=='identity': data['metrics'][0]['classification_id']='999'
                elif mode=='balanced':
                    # Offset two older months outside both matched FYTD spans.
                    for index,delta in [(4,1),(5,-1)]:
                        for mid in ['receipts','outlays']:
                            data['monthly'][index][mid]=dollars(amount(data['monthly'][index][mid])+delta)
                elif mode=='path': data['receipts'][0]['raw_path']='../../elsewhere.json'
                else: (root/data['receipts'][0]['raw_path']).write_text('{}')
                with self.subTest(mode=mode), self.assertRaises(FiscalError): validate_fiscal(data,raw_root=root)


class FiscalChangeAndCollectionTests(unittest.TestCase):
    def test_baseline_unchanged_and_definition_boundary(self):
        original=screen()
        self.assertEqual(compare_fiscal(None,original)['baselines'], ['treasury-mts'])
        self.assertEqual(compare_fiscal(original,copy.deepcopy(original))['items'], [])
        changed=copy.deepcopy(original); changed['basis']='Different accounting'
        item=compare_fiscal(original,changed)['items'][0]
        self.assertTrue(item['comparison_boundary']);self.assertEqual(item['kind'],'Fiscal definition changed')

    def test_revision_exact_spans_and_new_period_not_revision(self):
        original=screen(); changed=copy.deepcopy(original)
        changed['metrics'][0]['current_fytd']='241.00'
        item=compare_fiscal(original,changed)['items'][0]
        self.assertEqual((item['kind'],item['start'],item['date']), ('Revised fiscal value','2025-10-01','2025-11-30'))
        changed=copy.deepcopy(original)
        changed['periods']['current_fytd']['end']='2025-12-31'
        items=compare_fiscal(original,changed)['items']
        self.assertTrue(items and all(i['kind']=='New fiscal reporting period' and i['comparison_boundary'] for i in items))

    def test_classification_ids_are_edition_local_not_definition_boundaries(self):
        original=screen(); changed=copy.deepcopy(original)
        for m in changed['metrics']: m['classification_id']='new-'+m['classification_id']
        self.assertEqual(compare_fiscal(original,changed)['items'], [])

    def test_failed_capture_preserves_last_success_then_resumes(self):
        original=screen()
        def failure(*args): raise RuntimeError('sentinel-not-for-publication')
        failed, attempt=collect_fiscal(original,'2025-12-11T12:00:00+00:00',fetcher=failure)
        self.assertEqual(failed['status'],'stale')
        self.assertEqual(failed['captured_at'], original['captured_at'])
        self.assertEqual(failed['metrics'], original['metrics'])
        self.assertEqual(failed['changes']['skipped'], ['treasury-mts'])
        self.assertNotIn('sentinel',json.dumps(failed));self.assertNotIn('sentinel',json.dumps(attempt))
        resumed=copy.deepcopy(original); resumed.update(captured_at='2025-12-12T12:00:00+00:00')
        resumed['metrics'][0]['current_month']='121.00'
        change=compare_fiscal(failed,resumed)['items'][0]
        self.assertEqual(change['from_capture'], original['captured_at'])
        empty,_=collect_fiscal(None,'2025-12-11T12:00:00+00:00',fetcher=failure)
        self.assertEqual(empty['status'],'unavailable');validate_fiscal(empty)

    def test_latest_common_edition_and_six_serial_fetches(self):
        payloads,receipts=fixture(); by_table={r['table']:r for r in receipts};calls=[]
        def fake(url,table,data_dir,stamp,edition=None):
            calls.append((table,edition))
            if edition is None:
                dates=[EDITION,'2025-10-31']+(['2025-12-31'] if table!=9 else [])
                return {'data':[{'record_date':d} for d in dates]},dict(table=table,url=url)
            self.assertEqual(edition,EDITION)
            return payloads[table],dict(by_table[table],captured_at=stamp)
        with patch('fiscal.time.sleep'):
            result,_=collect_fiscal(None,'2026-01-12T12:00:00+00:00',fetcher=fake)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(calls,[(3,None),(9,None),(1,None),(3,EDITION),(9,EDITION),(1,EDITION)])


if __name__=='__main__':
    unittest.main()
