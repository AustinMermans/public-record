"""Edition-aligned Treasury MTS actuals with exact-dollar reconciliation.

Budget estimates are excluded. Table 1's positive deficit is converted to the
signed balance convention of table 3. No different-edition monthly splicing.
"""
import calendar
import copy
import hashlib
import json
import re
import subprocess
import time
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/fiscal'
API = 'https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_'
SOURCE_ID = 'treasury-mts'
PUBLISHER = 'US Treasury · Monthly Treasury Statement'
LANDING = 'https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/'
BASIS = 'Modified cash (including accrual of public-debt interest)'
FIELDS = dict(current_month='current_month_rcpt_outly_amt',
              current_fytd='current_fytd_rcpt_outly_amt', prior_fytd='prior_fytd_rcpt_outly_amt')
MONTH_FIELDS = dict(receipts='current_month_gross_rcpt_amt', outlays='current_month_gross_outly_amt',
                    balance='current_month_dfct_sur_amt')
LABELS = dict(receipts='Receipts', outlays='Outlays', net_interest='Net interest', balance='Signed balance')


class FiscalError(ValueError):
    """A controlled, public-safe diagnostic from the fiscal contract."""


def require(condition, message):
    if not condition:
        raise FiscalError(message)


def amount(value):
    require(isinstance(value, str) and re.fullmatch(r'-?\d{1,20}(?:\.\d{1,2})?', value),
            'Missing, nonfinite, or non-decimal dollar amount')
    return Decimal(value)


def dollars(value):
    return format(value, '.2f')


def month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def fiscal_periods(edition):
    end = date.fromisoformat(edition)
    require(edition == month_end(end.year, end.month), 'MTS edition is not a month end')
    fy = end.year + (end.month >= 10)
    return dict(current_month=dict(start=end.replace(day=1).isoformat(), end=edition),
                current_fytd=dict(start=f'{fy-1}-10-01', end=edition),
                prior_fytd=dict(start=f'{fy-2}-10-01', end=month_end(end.year-1, end.month)))


def endpoint(table, edition=None):
    params = {'filter': 'record_date:eq:' + edition, 'sort': 'src_line_nbr', 'page[size]': 1000} if edition else {
        'fields': 'record_date', 'sort': '-record_date', 'page[size]': 1000}
    return API + str(table) + '?' + urlencode(params)


def _rows(payload, table, edition):
    rows, meta = payload.get('data'), payload.get('meta', {})
    require(isinstance(rows, list) and rows, 'Empty or malformed MTS table')
    require(meta.get('count') == len(rows) and meta.get('total-count') == len(rows)
            and meta.get('total-pages') == 1 and not payload.get('links', {}).get('next'),
            'Incomplete MTS table response')
    columns = MONTH_FIELDS.values() if table == 1 else FIELDS.values()
    for field in columns:
        require(meta.get('dataTypes', {}).get(field) == 'CURRENCY'
                and meta.get('dataFormats', {}).get(field) == '$10.20', 'MTS actual-dollar metadata changed')
    ed = date.fromisoformat(edition)
    fiscal_year = ed.year + (ed.month >= 10)
    ids = []
    for row in rows:
        require(row.get('record_date') == edition and row.get('table_nbr') == str(table), 'Mismatched MTS edition or table')
        require(row.get('record_fiscal_year') == str(fiscal_year)
                and row.get('record_calendar_year') == str(ed.year)
                and row.get('record_calendar_month') == f'{ed.month:02d}'
                and row.get('record_calendar_day') == f'{ed.day:02d}', 'Mismatched MTS reporting metadata')
        require(isinstance(row.get('classification_id'), str) and row['classification_id'].isdigit(), 'Missing MTS row identity')
        ids.append(row['classification_id'])
    require(len(set(ids)) == len(ids), 'Duplicate MTS row identity')
    require(all(r.get('parent_id') == 'null' or r.get('parent_id') in ids for r in rows), 'Missing MTS parent')
    return rows


def _unique(rows, description, parent_description=None):
    matches = [r for r in rows if r.get('classification_desc') == description]
    if parent_description:
        parents = {r['classification_id'] for r in rows if r.get('classification_desc') == parent_description}
        require(len(parents) == 1, 'Missing or ambiguous MTS parent label')
        matches = [r for r in matches if r.get('parent_id') in parents]
    require(len(matches) == 1, 'Missing or duplicate MTS metric: ' + description)
    return matches[0]


def _evidence(row, table, edition):
    return dict(table=table, edition=edition, classification_id=row['classification_id'],
                parent_id=row['parent_id'], classification_desc=row['classification_desc'],
                data_type_cd=row['data_type_cd'], record_type_cd=row['record_type_cd'],
                url=endpoint(table, edition))


def _bridge(metrics):
    values = {m['id']: {p: amount(m[p]) for p in FIELDS} for m in metrics}
    change = lambda metric: values[metric]['current_fytd'] - values[metric]['prior_fytd']
    interest = change('net_interest'); receipts = change('receipts')
    other = change('outlays') - interest
    deficit = -change('balance')
    result = dict(status='reconciled', unit='USD', current_deficit=-values['balance']['current_fytd'],
                  prior_deficit=-values['balance']['prior_fytd'], deficit_change=deficit,
                  net_interest_change=interest, other_outlays_change=other, receipts_change=receipts,
                  receipts_contribution=-receipts, component_sum=interest+other-receipts,
                  residual=interest+other-receipts-deficit)
    require(result['residual'] == 0, 'Fiscal change bridge does not reconcile')
    return {k: dollars(v) if isinstance(v, Decimal) else v for k, v in result.items()}


def normalize_fiscal(payloads, receipts, captured_at):
    """Normalize complete tables 1/3/9 from one edition; no network or writes."""
    with localcontext() as ctx:
        ctx.prec = 40
        require(set(payloads) == {1, 3, 9}, 'Required MTS tables missing')
        require(len(receipts) == 3 and {r['table'] for r in receipts} == {1, 3, 9}, 'Required MTS receipts missing')
        editions = {r['edition'] for r in receipts}
        require(len(editions) == 1, 'Mismatched receipt editions')
        edition = editions.pop()
        require(edition <= captured_at[:10], 'Future MTS edition')
        periods = fiscal_periods(edition)
        tables = {t: _rows(payloads[t], t, edition) for t in payloads}
        for receipt in receipts:
            require(receipt['url'] == endpoint(receipt['table'], edition), 'MTS receipt URL does not identify table edition')
        selection = [('receipts', 3, 'Total Receipts', 'Budget Receipts', 'T'),
                     ('outlays', 3, 'Total Outlays', 'Budget Outlays', 'T'),
                     ('net_interest', 9, 'Net Interest', 'Net Outlays', 'D'),
                     ('balance', 3, 'Surplus (+) or Deficit (-)', 'Budget Outlays', 'T')]
        metrics = []
        for mid, table, label, parent, kind in selection:
            row = _unique(tables[table], label, parent)
            require(row.get('data_type_cd') == kind and row.get('sequence_level_nbr') == '2', 'MTS metric is not an expected actual row')
            if mid == 'net_interest':
                require(row.get('record_type_cd') == 'F', 'Net interest is not the budget function')
            metrics.append(dict(id=mid, label=LABELS[mid], unit='USD', basis=BASIS,
                                source_fields=FIELDS.copy(), **_evidence(row, table, edition),
                                **{period: dollars(amount(row.get(field))) for period, field in FIELDS.items()}))
        by_id = {m['id']: m for m in metrics}
        for period, field in FIELDS.items():
            require(amount(by_id['receipts'][period]) - amount(by_id['outlays'][period]) == amount(by_id['balance'][period]),
                    'Table 3 receipts less outlays does not equal signed balance')
            for mid, parent in [('receipts', 'Receipts'), ('outlays', 'Net Outlays')]:
                row = _unique(tables[9], 'Total', parent)
                require(row.get('data_type_cd') == 'T' and amount(row.get(field)) == amount(by_id[mid][period]),
                        'Tables 3 and 9 totals differ')
        edition_date = date.fromisoformat(edition); fy = edition_date.year + (edition_date.month >= 10)
        year_headers = [r for r in tables[1] if r.get('parent_id') == 'null']
        require(len(year_headers) == 2 and {r['classification_desc'] for r in year_headers} == {f'FY {fy-1}', f'FY {fy}'},
                'Unexpected table 1 fiscal-year hierarchy')
        monthly = []
        for header in year_headers:
            require(header.get('data_type_cd') == 'S' and header.get('sequence_level_nbr') == '1', 'Invalid fiscal-year header')
            year = int(header['classification_desc'][3:])
            children = [r for r in tables[1] if r['parent_id'] == header['classification_id']]
            month_rows = [r for r in children if r.get('record_type_cd') == 'MTH']
            expected_count = 12 if year == fy-1 else (edition_date.month-10) % 12 + 1
            expected_months = [(i+9) % 12 + 1 for i in range(expected_count)]
            require(len(month_rows) == expected_count, 'Missing or duplicate table 1 month')
            month_numbers = []
            for row in month_rows:
                require(row.get('data_type_cd') == 'D' and row.get('sequence_level_nbr') == '2', 'Invalid actual monthly row')
                require(row['classification_desc'] in calendar.month_name[1:], 'Unknown table 1 month name')
                month = list(calendar.month_name).index(row['classification_desc']); month_numbers.append(month)
                end = month_end(year-(month >= 10), month)
                values = {mid: amount(row.get(field)) for mid, field in MONTH_FIELDS.items()}
                require(values['outlays']-values['receipts'] == values['balance'], 'Table 1 deficit sign or arithmetic mismatch')
                monthly.append(dict(date=end, fiscal_year=year, receipts=dollars(values['receipts']),
                    outlays=dollars(values['outlays']), balance=dollars(-values['balance']),
                    source_balance=dollars(values['balance']), source_balance_convention='Deficit positive; surplus negative',
                    unit='USD', source_fields=MONTH_FIELDS.copy(), **_evidence(row, 1, edition)))
            require(sorted(month_numbers) == sorted(expected_months), 'Table 1 monthly coverage mismatch')
            totals = [r for r in children if r.get('classification_desc') == 'Year-to-Date']
            require(len(children) == len(month_rows)+1 and len(totals) == 1 and totals[0].get('data_type_cd') == 'T',
                    'Unexpected table 1 total or child')
            for mid, field in MONTH_FIELDS.items():
                summed = sum(amount(r[field]) for r in month_rows)
                require(summed == amount(totals[0].get(field)), 'Table 1 fiscal-year sum does not reconcile')
        monthly.sort(key=lambda row: row['date'])
        for period, span in periods.items():
            selected = [r for r in monthly if span['start'] <= r['date'] <= span['end']]
            for mid in MONTH_FIELDS:
                require(sum(amount(r[mid]) for r in selected) == amount(by_id[mid][period]),
                        'Table 1 economic-period sum differs from table 3')
        bridge = _bridge(metrics)
        bridge['sources'] = [endpoint(3, edition), endpoint(9, edition)]
        result = dict(schema_version=1, status='ok', source_id=SOURCE_ID, publisher=PUBLISHER, url=LANDING,
            captured_at=captured_at, last_success=captured_at, attempted_at=captured_at,
            edition=edition, publication_date=None, unit='USD', basis=BASIS,
            adjustment='Not seasonally adjusted', price_basis='Nominal USD',
            receipts=copy.deepcopy(receipts), periods=periods, metrics=metrics, bridge=bridge,
            monthly=monthly, monthly_status='ok', monthly_coverage=dict(start=monthly[0]['date'], end=monthly[-1]['date'],
                edition=edition, note='Prior fiscal year and current FYTD, all restated as supplied in this single statement edition; not original-release vintages.'),
            validation=dict(status='reconciled', checks=['Table 3 signed balances', 'Table 3/table 9 actual totals',
                'Table 1 parent-year monthly coverage', 'Table 1 year totals', 'Table 1/table 3 matched economic periods', 'FYTD deficit-change bridge']),
            method_note='Actual nominal dollars, not budget estimates. Modified cash reporting includes accrual of public-debt interest. Payment timing can shift single-month values. The bridge is an accounting identity, not policy causality; deficit is not debt growth.')
        validate_fiscal(result)
        return result


def validate_fiscal(bundle, raw_root=None):
    """Validate the embedded screen without converting dollar strings to floats."""
    require(bundle.get('schema_version') == 1 and bundle.get('source_id') == SOURCE_ID, 'Invalid fiscal bundle identity')
    require(bundle.get('status') in ('ok', 'stale', 'unavailable'), 'Invalid fiscal source status')
    if bundle['status'] == 'unavailable':
        require(not bundle.get('metrics') and not bundle.get('monthly'), 'Unavailable fiscal data contains unverified values')
        return
    with localcontext() as ctx:
        ctx.prec = 40
        require(bundle.get('captured_at') and bundle.get('last_success') == bundle['captured_at'], 'Missing fiscal successful-capture clock')
        captured = datetime.fromisoformat(bundle['captured_at'])
        attempted = datetime.fromisoformat(bundle['attempted_at'])
        require(captured.tzinfo and attempted.tzinfo and captured <= attempted, 'Invalid fiscal capture/attempt clocks')
        require(bundle['edition'] <= bundle['captured_at'][:10], 'Future fiscal edition')
        require(bundle.get('periods') == fiscal_periods(bundle['edition']), 'Fiscal period boundary mismatch')
        require(bundle.get('unit') == 'USD' and bundle.get('basis') == BASIS, 'Fiscal units or accounting basis mismatch')
        metrics = bundle.get('metrics', [])
        require(len(metrics) == 4 and {m['id'] for m in metrics} == set(LABELS), 'Missing or duplicate fiscal metric')
        values = {m['id']: m for m in metrics}
        receipts = bundle.get('receipts', [])
        require(len(receipts) == 3 and {r['table'] for r in receipts} == {1, 3, 9}, 'Fiscal source receipts missing')
        for receipt in receipts:
            require(receipt.get('edition') == bundle['edition'] and receipt.get('url') == endpoint(receipt['table'], bundle['edition'])
                    and receipt.get('captured_at') == bundle['captured_at']
                    and re.fullmatch(r'[a-f0-9]{64}', receipt.get('sha256', '')) and receipt.get('raw_path'), 'Invalid fiscal receipt provenance')
        for m in metrics:
            table = 9 if m['id'] == 'net_interest' else 3
            require(m.get('unit') == 'USD' and m.get('basis') == BASIS and m.get('table') == table
                    and m.get('edition') == bundle['edition'] and m.get('url') == endpoint(table, bundle['edition'])
                    and m.get('classification_id') and m.get('parent_id') and m.get('source_fields') == FIELDS, 'Invalid fiscal metric provenance')
            for period in FIELDS:
                amount(m.get(period))
        for period in FIELDS:
            require(amount(values['receipts'][period])-amount(values['outlays'][period]) == amount(values['balance'][period]), 'Fiscal balance mismatch')
        expected_bridge = _bridge(metrics)
        require(all(bundle.get('bridge', {}).get(k) == v for k, v in expected_bridge.items()), 'Fiscal bridge mismatch')
        require(bundle['bridge'].get('sources') == [endpoint(3, bundle['edition']), endpoint(9, bundle['edition'])], 'Fiscal bridge evidence mismatch')
        require(bundle.get('validation', {}).get('status') == 'reconciled' and bundle.get('monthly_status') == 'ok', 'Fiscal validation gate missing')
        monthly = bundle.get('monthly', [])
        require(monthly and monthly == sorted(monthly, key=lambda r: r['date'])
                and len({r['date'] for r in monthly}) == len(monthly), 'Fiscal monthly dates missing or duplicated')
        first = date.fromisoformat(bundle['periods']['prior_fytd']['start'])
        year, month = first.year, first.month
        expected_dates = []
        while month_end(year, month) <= bundle['edition']:
            expected_dates.append(month_end(year, month))
            year, month = (year+1, 1) if month == 12 else (year, month+1)
        require([r['date'] for r in monthly] == expected_dates, 'Fiscal monthly coverage has missing or extra periods')
        coverage = bundle.get('monthly_coverage', {})
        require(coverage.get('start') == expected_dates[0] and coverage.get('end') == expected_dates[-1]
                and coverage.get('edition') == bundle['edition'], 'Fiscal monthly coverage metadata mismatch')
        for row in monthly:
            end = date.fromisoformat(row['date'])
            require(row['date'] == month_end(end.year, end.month) and row.get('fiscal_year') == end.year+(end.month>=10), 'Fiscal monthly year mismatch')
            require(row.get('edition') == bundle['edition'] and row.get('unit') == 'USD'
                    and row.get('url') == endpoint(1, bundle['edition']) and row.get('table') == 1
                    and row.get('classification_id') and row.get('parent_id'), 'Fiscal monthly evidence mismatch')
            require(amount(row['receipts'])-amount(row['outlays']) == amount(row['balance']) == -amount(row['source_balance']), 'Fiscal monthly balance mismatch')
        for period, span in bundle['periods'].items():
            for mid in MONTH_FIELDS:
                total = sum(amount(r[mid]) for r in monthly if span['start'] <= r['date'] <= span['end'])
                require(total == amount(values[mid][period]), 'Fiscal monthly/aggregate mismatch')
    if raw_root is not None:
        root = Path(raw_root).resolve()
        payloads = {}
        for receipt in bundle['receipts']:
            relative = Path('data/fiscal/raw') / (receipt['sha256']+'.json')
            require(receipt['raw_path'] == relative.as_posix(), 'Fiscal raw path is not content-addressed in the allowed directory')
            path = root / relative
            require(not path.is_symlink() and path.resolve().is_relative_to((root / 'data/fiscal/raw').resolve()), 'Fiscal raw evidence path escapes its directory')
            body = path.read_bytes()
            require(hashlib.sha256(body).hexdigest() == receipt['sha256'], 'Fiscal raw evidence hash mismatch')
            payloads[receipt['table']] = json.loads(body)
        rebuilt = normalize_fiscal(payloads, bundle['receipts'], bundle['captured_at'])
        for key in rebuilt:
            if key not in ('status', 'attempted_at'):
                require(bundle.get(key) == rebuilt[key], 'Fiscal normalized evidence differs from raw source: '+key)


def _points(bundle):
    points = {}
    for row in bundle.get('monthly', []):
        for mid in MONTH_FIELDS:
            points[(mid, 'month', row['date'][:7]+'-01', row['date'])] = dict(value=row[mid], url=row['url'])
    for metric in bundle.get('metrics', []):
        for period, span in bundle['periods'].items():
            frequency = 'month' if period == 'current_month' else 'fytd'
            points[(metric['id'], frequency, span['start'], span['end'])] = dict(value=metric[period], url=metric['url'])
    return points


def compare_fiscal(previous, current):
    old_capture = (previous or {}).get('captured_at'); current_capture = current.get('captured_at')
    status = 'unavailable' if current.get('status') != 'ok' else 'baseline' if not old_capture or not (previous or {}).get('metrics') else 'compared'
    result = dict(from_capture=old_capture, to_capture=current_capture, items=[],
        baselines=[SOURCE_ID] if status == 'baseline' else [], skipped=[SOURCE_ID] if status == 'unavailable' else [],
        channels=[dict(id=SOURCE_ID, label=PUBLISHER, status=status, from_capture=old_capture,
                       to_capture=current_capture, attempted_at=current.get('attempted_at'),
                       error=current.get('error') if status == 'unavailable' else None)])
    if status != 'compared':
        return result
    context = dict(source_id=SOURCE_ID, publisher=PUBLISHER, from_capture=old_capture, to_capture=current_capture,
                   edition=current['edition'], previous_edition=previous['edition'], unit='USD')
    definition_fields = ('unit', 'basis', 'adjustment', 'price_basis')
    if any(previous.get(k) != current.get(k) for k in definition_fields):
        result['items'].append(dict(context, kind='Fiscal definition changed', title='Treasury fiscal accounting definition',
            url=current['url'], previous_url=previous['url'], comparison_boundary=True,
            before=json.dumps({k: previous.get(k) for k in definition_fields}, sort_keys=True),
            after=json.dumps({k: current.get(k) for k in definition_fields}, sort_keys=True)))
        return result
    prior = _points(previous)
    for key, point in sorted(_points(current).items()):
        mid, frequency, start, end = key
        old = prior.get(key)
        item = dict(context, metric_id=mid, title=LABELS[mid]+' · '+('monthly' if frequency=='month' else 'FYTD'),
                    period_type=frequency, start=start, date=end, url=point['url'])
        if old and amount(old['value']) != amount(point['value']):
            result['items'].append(dict(item, kind='Revised fiscal value', before=old['value'], after=point['value'], previous_url=old['url']))
        elif not old:
            ends = [k[3] for k in prior if k[:2] == key[:2]]
            kind = 'New fiscal reporting period' if ends and end > max(ends) else 'Newly available fiscal period'
            result['items'].append(dict(item, kind=kind, before=None, after=point['value'], comparison_boundary=True))
    return result


def fetch(url, table, data_dir, stamp, edition=None):
    response = subprocess.run(['curl', '--http1.1', '--fail', '--silent', '--show-error', '--max-time', '35',
        '--user-agent', 'PublicRecord/1.6 github.com/AustinMermans/public-record', url], capture_output=True, timeout=45)
    require(response.returncode == 0, 'Treasury request failed (HTTP or network error)')
    digest = hashlib.sha256(response.stdout).hexdigest()
    raw = data_dir / 'raw' / (digest+'.json'); raw.parent.mkdir(parents=True, exist_ok=True)
    if not raw.exists():
        raw.write_bytes(response.stdout)
    try:
        path = str(raw.relative_to(ROOT))
    except ValueError:
        path = str(raw)
    receipt = dict(table=table, url=url, sha256=digest, raw_path=path, captured_at=stamp, edition=edition)
    return json.loads(response.stdout), receipt


def collect_fiscal(previous, stamp, data_dir=DATA, fetcher=fetch):
    """Serialized six-request collection, retaining old successful data on failure."""
    receipts, discoveries = [], []
    try:
        candidates = []
        for table in (3, 9, 1):
            payload, receipt = fetcher(endpoint(table), table, data_dir, stamp)
            discoveries.append(receipt)
            rows = payload.get('data', [])
            require(rows and len(rows) <= 1000, 'Treasury edition discovery failed')
            dates = set()
            for row in rows:
                value = row.get('record_date', '')
                date.fromisoformat(value)
                require(value == month_end(int(value[:4]), int(value[5:7])) and value <= stamp[:10], 'Invalid discovery edition')
                dates.add(value)
            candidates.append(dates)
            time.sleep(.25)
        common = set.intersection(*candidates)
        require(common, 'No common Treasury edition in bounded discovery')
        edition = max(common); payloads = {}
        for table in (3, 9, 1):
            payloads[table], receipt = fetcher(endpoint(table, edition), table, data_dir, stamp, edition)
            receipts.append(receipt)
            time.sleep(.25)
        bundle = normalize_fiscal(payloads, receipts, stamp)
        bundle['discovery_receipts'] = discoveries
    except Exception as error:
        # Never echo arbitrary curl commands, response bodies, or subprocess stderr.
        message = str(error) if isinstance(error, FiscalError) else 'Treasury collection or normalization failed'
        bundle = copy.deepcopy(previous) if previous and previous.get('metrics') else dict(
            schema_version=1, source_id=SOURCE_ID, publisher=PUBLISHER, url=LANDING, metrics=[], monthly=[], captured_at=None)
        bundle.update(status='stale' if bundle.get('metrics') else 'unavailable', attempted_at=stamp, error=message)
    bundle['changes'] = compare_fiscal(previous, bundle)
    attempt = dict(attempted_at=stamp, status=bundle['status'], error=bundle.get('error'),
                   discovery_receipts=discoveries, receipts=receipts)
    return bundle, attempt


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    current = DATA / 'current.json'
    previous = json.loads(current.read_text()) if current.exists() else None
    (DATA / 'comparison-baseline.json').write_text(json.dumps(previous, separators=(',', ':')))
    bundle, attempt = collect_fiscal(previous, stamp)
    validate_fiscal(bundle)
    text = json.dumps(bundle, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    current.write_text(text)
    suffix = stamp[:19].replace(':', '')
    (DATA / ('capture-'+suffix+'.json')).write_text(text)
    (DATA / ('attempt-'+suffix+'.json')).write_text(json.dumps(attempt, allow_nan=False, separators=(',', ':')))
    print('Treasury MTS', bundle['status'], bundle.get('edition'), len(bundle.get('monthly', [])), 'monthly observations')
    if bundle.get('error'):
        print(bundle['error'])


if __name__ == '__main__':
    main()
