"""Source-bound EIA weekly petroleum stocks; levels are not production flows.

The JSON is the current six-year rolling edition, not an archive of what each
week's report originally said. Table 4 controls the three current stock rows.
"""
import copy
import csv
import hashlib
import io
import json
import re
import subprocess
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'energy'
JSON_URL = 'https://ir.eia.gov/wpsr/psw00.json'
TABLE_URL = 'https://ir.eia.gov/wpsr/table4.csv'
SCHEDULE_URL = 'https://www.eia.gov/petroleum/supply/weekly/schedule.php'
SOURCE_ID = 'eia-wpsr'
PUBLISHER = 'U.S. Energy Information Administration'
ROWS = (('crude', 'Commercial (Excluding SPR)', 'Commercial crude, excluding SPR'),
        ('gasoline', 'Total Motor Gasoline', 'Motor gasoline'),
        ('distillate', 'Distillate Fuel Oil', 'Distillate fuel oil'))


class EnergyError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise EnergyError(reason)


def _number(value):
    require(isinstance(value, str) and re.fullmatch(r'-?\d+(?:\.\d{1,3})?', value),
            'Invalid EIA stock value')
    return Decimal(value)


def _day(label):
    match = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{2})', label)
    require(match is not None, 'EIA table date header changed')
    return date(2000 + int(match[3]), int(match[1]), int(match[2])).isoformat()


def parse_sources(json_body, csv_body, stamp):
    require(isinstance(json_body, bytes) and 100 < len(json_body) < 5_000_000,
            'EIA crude JSON absent or oversized')
    require(isinstance(csv_body, bytes) and 100 < len(csv_body) < 1_000_000,
            'EIA stock CSV absent or oversized')
    try:
        source = json.loads(json_body.decode('utf-8-sig'))
        table = list(csv.reader(io.StringIO(csv_body.decode('utf-8-sig'))))
    except (UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        raise EnergyError('EIA source encoding or structure invalid') from exc
    metadata = source['metadata']
    require(metadata['source'] == PUBLISHER and metadata['release_name'] == 'Weekly Petroleum Status Report'
            and metadata['data_description'] == 'Commercial Crude Oil Stocks (Excluding SPR)'
            and metadata['periodicity'] == 'Weekly', 'EIA JSON identity changed')
    series = source['data']['U.S.']
    require(series['sourcekey'] == 'WCESTUS1' and series['units'] == 'thousand barrels',
            'EIA crude series key or units changed')
    history = []
    for point in series['time_series']:
        require(point.get('suppression_flag') is None and point.get('value') is not None,
                'EIA crude history includes suppressed or missing value')
        value = Decimal(str(point['value']))
        require(value == value.to_integral_value() and 0 < value < 2_000_000,
                'EIA crude history has invalid thousand-barrel level')
        date.fromisoformat(point['date'])
        history.append([point['date'], int(value)])
    require(len(history) >= 50 and history == sorted(history)
            and len({point[0] for point in history}) == len(history),
            'EIA crude history is missing, unordered or duplicated')
    week = history[-1][0]
    published = metadata['release_date']
    require(metadata['time_period']['end_date'] == week and week <= published <= stamp[:10],
            'EIA release, report week and capture dates disagree')
    require(table and table[0] and table[0][0] == 'STUB_1',
            'EIA Table 4 header missing')
    columns = table[0]
    require(len(columns) == 8 and columns[3] == 'Difference' and columns[5] == 'Percent Change',
            'EIA Table 4 columns changed')
    current_day, prior_day, year_day = map(_day, (columns[1], columns[2], columns[4]))
    year_gap = (date.fromisoformat(current_day) - date.fromisoformat(year_day)).days
    require(current_day == week and prior_day == history[-2][0] and 350 <= year_gap <= 378,
            'EIA CSV periods disagree with JSON')
    metrics = []
    for key, row_name, label in ROWS:
        matches = [row for row in table[1:] if row and row[0].strip() == row_name]
        require(len(matches) == 1, 'Missing or ambiguous EIA Table 4 row: ' + row_name)
        row = matches[0]
        require(len(row) == len(columns), 'EIA Table 4 row width changed')
        current, prior, difference, year_ago, year_pct = [_number(value) for value in row[1:6]]
        # EIA notes that displayed stocks and difference are independently
        # rounded; one thousandth of a million barrels can be legitimate.
        require(current > 0 and prior > 0 and year_ago > 0
                and abs(current - prior - difference) <= Decimal('.001'),
                'EIA stock change does not reconcile: ' + row_name)
        # Year-ago percent is published to one decimal, even if its CSV cell
        # carries three places. Check its rounded value without replacing it.
        calculated = (current / year_ago - 1) * 100
        require(abs(calculated - year_pct) <= Decimal('.051'),
                'EIA year-ago percent does not reconcile: ' + row_name)
        metrics.append(dict(id=key, label=label, source_row=row_name,
            current=format(current, '.3f'), prior=format(prior, '.3f'),
            weekly_change=format(difference, '.3f'), year_ago=format(year_ago, '.3f'),
            year_change_pct=format(year_pct, '.1f'), unit='million barrels',
            current_week=week, prior_week=prior_day, year_ago_week=year_day,
            url=TABLE_URL))
    crude = metrics[0]
    require(Decimal(crude['current']) * 1000 == history[-1][1]
            and Decimal(crude['prior']) * 1000 == history[-2][1],
            'EIA CSV crude levels disagree with JSON history')
    return dict(schema_version=1, source_id=SOURCE_ID, publisher=PUBLISHER,
        status='ok', captured_at=stamp, attempted_at=stamp, published_at=published,
        week_end=week, metrics=metrics, crude_history=history,
        history_basis='Current EIA rolling JSON edition; not original-release vintages',
        json_url=JSON_URL, table_url=TABLE_URL, schedule_url=SCHEDULE_URL)


def _fetch(url):
    version = (ROOT / 'VERSION').read_text().strip()
    result = subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
        '--max-time', '50', '--user-agent',
        f'PublicRecord/{version} (+https://github.com/AustinMermans/public-record/issues)', url],
        capture_output=True, timeout=55)
    require(result.returncode == 0 and result.stdout, 'EIA request failed: ' + url)
    return result.stdout


def _raw(data_dir, body, extension):
    sha = hashlib.sha256(body).hexdigest()
    path = data_dir / 'raw' / (sha + '.' + extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(body)
    root = data_dir.parent.parent if data_dir.parent.name == 'data' else data_dir.parent
    return dict(sha256=sha, raw_path=str(path.relative_to(root)))


def compare_energy(previous, current):
    old_stamp = (previous or {}).get('captured_at')
    stamp = current.get('captured_at')
    state = ('unavailable' if current.get('status') != 'ok' else
             'baseline' if not previous or not previous.get('metrics') else 'compared')
    changes = dict(items=[], channels=[dict(id=SOURCE_ID, label=PUBLISHER, status=state,
        from_capture=old_stamp, to_capture=stamp, attempted_at=current.get('attempted_at'),
        error=current.get('error') if state == 'unavailable' else None)])
    if state != 'compared':
        return changes
    old = {m['id']: m for m in previous['metrics']}
    for metric in current['metrics']:
        before = old.get(metric['id'])
        if not before:
            continue
        context = dict(source_id=SOURCE_ID, publisher=PUBLISHER, metric_id=metric['id'],
            title=metric['label'], url=TABLE_URL, date=current['week_end'],
            from_capture=old_stamp, to_capture=stamp, unit=metric['unit'])
        if before['unit'] != metric['unit'] or before['source_row'] != metric['source_row']:
            changes['items'].append(dict(context, kind='Energy definition changed',
                comparison_boundary=True, before=before['source_row'], after=metric['source_row']))
        elif previous['week_end'] != current['week_end']:
            changes['items'].append(dict(context, kind='New petroleum reporting week',
                before=before['current'], after=metric['current']))
        else:
            fields = (('current', 'Revised petroleum stock', metric['unit']),
                ('prior', 'Revised prior-week petroleum stock', metric['unit']),
                ('weekly_change', 'Revised published weekly change', metric['unit']),
                ('year_ago', 'Revised year-ago petroleum stock', metric['unit']),
                ('year_change_pct', 'Revised published year-ago change', 'percent'))
            for field, kind, unit in fields:
                if before[field] != metric[field]:
                    changes['items'].append(dict(context, kind=kind, field=field,
                        unit=unit, before=before[field], after=metric[field]))
    if previous.get('crude_history') and current.get('crude_history'):
        old_history = dict(previous['crude_history'])
        # Table 4 and JSON can describe the same crude stock observation.
        # A same-week Table 4 revision already supplies its change event.
        represented = set()
        if previous['week_end'] == current['week_end']:
            old_crude = next(m for m in previous['metrics'] if m['id'] == 'crude')
            new_crude = next(m for m in current['metrics'] if m['id'] == 'crude')
            for field, day_field in (('current', 'current_week'),
                                     ('prior', 'prior_week'),
                                     ('year_ago', 'year_ago_week')):
                if old_crude[field] != new_crude[field]:
                    represented.add(new_crude[day_field])
        for day, value in current['crude_history']:
            if day in old_history and value != old_history[day] and day not in represented:
                changes['items'].append(dict(source_id=SOURCE_ID, publisher=PUBLISHER,
                    metric_id='crude', title='Commercial crude history',
                    kind='Revised crude history', date=day, from_capture=old_stamp,
                    to_capture=stamp, url=JSON_URL, unit='thousand barrels',
                    before=old_history[day], after=value))
    return changes


def validate_capture(bundle, root=ROOT):
    require(bundle.get('schema_version') == 1 and bundle.get('source_id') == SOURCE_ID,
            'Invalid EIA capture identity')
    require(bundle.get('status') in ('ok', 'stale', 'unavailable'), 'Invalid EIA status')
    if bundle['status'] == 'unavailable':
        require(not bundle.get('metrics'), 'Unavailable EIA capture has figures')
        return
    captured = datetime.fromisoformat(bundle['captured_at'].replace('Z', '+00:00'))
    attempted = datetime.fromisoformat(bundle['attempted_at'].replace('Z', '+00:00'))
    require(captured.tzinfo is not None and attempted.tzinfo is not None and captured <= attempted,
            'Invalid EIA capture clocks')
    require(bundle['json_url'] == JSON_URL and bundle['table_url'] == TABLE_URL,
            'EIA source URLs changed')
    if root is not None:
        bodies = []
        for name in ('json', 'table'):
            receipt = bundle['receipts'][name]
            body = (root / receipt['raw_path']).read_bytes()
            require(hashlib.sha256(body).hexdigest() == receipt['sha256'],
                    'EIA raw hash mismatch')
            bodies.append(body)
        replay = parse_sources(*bodies, bundle['captured_at'])
        for key, value in replay.items():
            if key in ('status', 'attempted_at'):
                continue
            require(bundle.get(key) == value, 'EIA derived value differs from raw: ' + key)


def collect(previous, stamp, data_dir=DATA, fetch=_fetch):
    try:
        json_body = fetch(JSON_URL)
        csv_body = fetch(TABLE_URL)
        bundle = parse_sources(json_body, csv_body, stamp)
        bundle['receipts'] = dict(json=_raw(data_dir, json_body, 'json'),
                                  table=_raw(data_dir, csv_body, 'csv'))
    except Exception as error:
        message = str(error) if isinstance(error, EnergyError) else 'EIA capture or normalization failed'
        bundle = copy.deepcopy(previous) if previous and previous.get('metrics') else dict(
            schema_version=1, source_id=SOURCE_ID, publisher=PUBLISHER, metrics=[],
            captured_at=None, json_url=JSON_URL, table_url=TABLE_URL, schedule_url=SCHEDULE_URL)
        bundle.update(status='stale' if bundle.get('metrics') else 'unavailable',
                      attempted_at=stamp, error=message)
    bundle['changes'] = compare_energy(previous, bundle)
    return bundle


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    current = DATA / 'current.json'
    previous = json.loads(current.read_text()) if current.exists() else None
    bundle = collect(previous, stamp)
    validate_capture(bundle)
    text = json.dumps(bundle, allow_nan=False, separators=(',', ':'))
    current.write_text(text + '\n')
    suffix = stamp[:19].replace(':', '')
    (DATA / ('capture-' + suffix + '.json')).write_text(text + '\n')
    print('EIA WPSR', bundle['status'], bundle.get('week_end'))
    if bundle.get('error'):
        print(bundle['error'])


if __name__ == '__main__':
    main()
