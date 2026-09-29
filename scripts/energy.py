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
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'energy'
JSON_URL = 'https://ir.eia.gov/wpsr/psw00.json'
TABLE_URL = 'https://ir.eia.gov/wpsr/table4.csv'
SCHEDULE_URL = 'https://www.eia.gov/petroleum/supply/weekly/schedule.php'
HISTORY_URLS = {
    'gasoline': 'https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WGTSTUS1&f=W',
    'distillate': 'https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WDISTUS1&f=W',
}
HISTORY_IDENTITIES = {
    'gasoline': ('Weekly U.S. Ending Stocks of Total Gasoline  (Thousand Barrels)', 'WGTSTUS1w.xls'),
    'distillate': ('Weekly U.S. Ending Stocks of Distillate Fuel Oil  (Thousand Barrels)', 'WDISTUS1w.xls'),
}
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


class _HistoryTable(HTMLParser):
    """Read only the weekly EIA data table, not navigation or referring pages."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = 0
        self.active = False
        self.body = False
        self.row = None
        self.cell = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table' and dict(attrs).get('class') == 'FloatTitle':
            self.tables += 1
            self.active = True
        elif self.active and tag == 'tbody':
            self.body = True
        elif self.body and tag == 'tr':
            self.row = []
        elif self.row is not None and tag in ('td', 'th'):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == 'tbody' and self.body:
            self.body = False
        elif tag == 'table' and self.active:
            self.active = False


class _ScheduleTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = 0
        self.active = False
        self.row = None
        self.cell = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table' and 'schedule' in dict(attrs).get('class', '').split():
            self.tables += 1
            self.active = True
        elif self.active and tag == 'tr':
            self.row = []
        elif self.row is not None and tag in ('th', 'td'):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('th', 'td') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == 'table' and self.active:
            self.active = False


def parse_schedule(body, stamp, latest_week):
    require(isinstance(body, bytes) and 5_000 < len(body) < 1_000_000,
            'EIA release schedule absent or oversized')
    try:
        page = body.decode('utf-8-sig')
    except UnicodeError as exc:
        raise EnergyError('EIA release schedule encoding changed') from exc
    require('Weekly Petroleum Status Report Schedule' in page
            and 'after 10:30 a.m. eastern time on Wednesday' in page
            and 'Holiday Release Schedule' in page,
            'EIA default release schedule identity changed')
    parser = _ScheduleTable()
    parser.feed(page)
    require(parser.tables == 1 and parser.rows
            and parser.rows[0][:4] == ['Data for the week ending', 'Alternate release date',
                                      'Release day', 'Release time'],
            'EIA holiday schedule table changed')
    exceptions = {}
    for row in parser.rows[1:]:
        require(len(row) == 5, 'EIA holiday schedule row changed')
        week = datetime.strptime(row[0], '%B %d, %Y').date()
        release = datetime.strptime(row[1], '%B %d, %Y').date()
        require(week.weekday() == 4 and release.strftime('%A') == row[2]
                and 3 <= (release - week).days <= 14
                and re.fullmatch(r'\d{1,2}:\d{2} [ap]\.m\.', row[3])
                and week not in exceptions,
                'EIA holiday schedule date, day or time changed')
        exceptions[week] = (release, row[3], row[4])
    latest = date.fromisoformat(latest_week)
    require(latest.weekday() == 4 and latest <= date.fromisoformat(stamp[:10]),
            'EIA schedule anchor week invalid')
    # EIA explicitly states the Wednesday default plus listed exceptions.
    # Honor that rule in the latest exception year, but never project into a
    # later year's holiday cycle before that year's exceptions are published.
    supported_through = date(max(exceptions).year, 12, 31)
    schedule = []
    for offset in range(1, 9):
        week = latest + timedelta(weeks=offset)
        if week > supported_through:
            break
        release, clock, holiday = exceptions.get(
            week, (week + timedelta(days=5), '10:30 a.m.', None))
        if release < date.fromisoformat(stamp[:10]):
            continue
        schedule.append(dict(report_week=week.isoformat(), date=release.isoformat(),
            time_window='After ' + clock + ' ET', holiday=holiday, url=SCHEDULE_URL))
    require(schedule and schedule == sorted(schedule, key=lambda row: row['date']),
            'EIA future release schedule missing, unsupported or unordered')
    return schedule


def parse_product_history(body, product, bundle):
    require(product in HISTORY_URLS and isinstance(body, bytes) and 5_000 < len(body) < 5_000_000,
            'EIA product history absent or oversized')
    try:
        page = body.decode('utf-8-sig')
    except UnicodeError as exc:
        raise EnergyError('EIA product history encoding changed') from exc
    title, workbook = HISTORY_IDENTITIES[product]
    require('<title>' + title + '</title>' in page and "hist_xls/" + workbook in page,
            'EIA product history identity or units changed: ' + product)
    match = re.search(r'Release Date:\s*(\d{1,2}/\d{1,2}/\d{4})', page)
    require(match is not None and datetime.strptime(match[1], '%m/%d/%Y').date().isoformat()
            == bundle['published_at'], 'EIA product history release date disagrees')
    parser = _HistoryTable()
    parser.feed(page)
    require(parser.tables == 1 and len(parser.rows) >= 12,
            'EIA product history table missing or ambiguous')
    observations = []
    for row in parser.rows:
        if row == ['']:
            continue  # EIA separates calendar years with an empty spacer row.
        require(len(row) == 11 and re.fullmatch(r'\d{4}-[A-Z][a-z]{2}', row[0]),
                'EIA product history row structure changed')
        month = datetime.strptime(row[0], '%Y-%b').date()
        for day, amount in zip(row[1::2], row[2::2]):
            require(bool(day) == bool(amount), 'EIA product history has partial week')
            if not day:
                continue
            require(re.fullmatch(r'\d{2}/\d{2}', day) is not None
                    and re.fullmatch(r'\d{1,3}(?:,\d{3})*', amount) is not None,
                    'EIA product history date or value changed')
            observed = date(month.year, *map(int, day.split('/')))
            require(observed.month == month.month, 'EIA product history month disagrees')
            value = int(amount.replace(',', ''))
            require(0 < value < 1_000_000, 'EIA product history level out of bounds')
            observations.append([observed.isoformat(), value])
    require(len(observations) >= 50 and observations == sorted(observations)
            and len({row[0] for row in observations}) == len(observations),
            'EIA product history missing, unordered or duplicated')
    gaps = [(date.fromisoformat(b[0]) - date.fromisoformat(a[0])).days
            for a, b in zip(observations, observations[1:])]
    # Distillate's earliest EIA history has four gaps covering six absent
    # observations in 1982–83. Keep them, but require a complete recent window.
    require(all(gap in (7, 14, 21, 28) for gap in gaps)
            and all(gap == 7 for gap in gaps[-260:]),
            'EIA product history weekly spacing changed')
    metric = next(m for m in bundle['metrics'] if m['id'] == product)
    require(observations[-1] == [bundle['week_end'], int(Decimal(metric['current']) * 1000)]
            and observations[-2] == [metric['prior_week'], int(Decimal(metric['prior']) * 1000)],
            'EIA product history disagrees with Table 4: ' + product)
    year_ago = dict(observations).get(metric['year_ago_week'])
    require(year_ago is None or year_ago == int(Decimal(metric['year_ago']) * 1000),
            'EIA product history year-ago level disagrees with Table 4: ' + product)
    return observations


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
    return dict(schema_version=2, source_id=SOURCE_ID, publisher=PUBLISHER,
        status='ok', captured_at=stamp, attempted_at=stamp, published_at=published,
        week_end=week, metrics=metrics, crude_history=history,
        history_basis='Current EIA rolling JSON edition; not original-release vintages',
        json_url=JSON_URL, table_url=TABLE_URL, schedule_url=SCHEDULE_URL,
        history_urls=HISTORY_URLS)


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
    for product, url in HISTORY_URLS.items():
        before_points = previous.get('product_history', {}).get(product)
        after_points = current.get('product_history', {}).get(product)
        if not before_points or not after_points:
            continue
        old_history = dict(before_points)
        represented = set()
        if previous['week_end'] == current['week_end']:
            old_metric = next(m for m in previous['metrics'] if m['id'] == product)
            new_metric = next(m for m in current['metrics'] if m['id'] == product)
            for field, day_field in (('current', 'current_week'), ('prior', 'prior_week'),
                                     ('year_ago', 'year_ago_week')):
                if old_metric[field] != new_metric[field]:
                    represented.add(new_metric[day_field])
        for day, value in after_points:
            if day in old_history and old_history[day] != value and day not in represented:
                changes['items'].append(dict(source_id=SOURCE_ID, publisher=PUBLISHER,
                    metric_id=product, title=product.title() + ' stock history',
                    kind='Revised petroleum stock history', date=day, from_capture=old_stamp,
                    to_capture=stamp, url=url, unit='thousand barrels',
                    before=old_history[day], after=value))
    return changes


def validate_capture(bundle, root=ROOT):
    require(bundle.get('schema_version') in (1, 2) and bundle.get('source_id') == SOURCE_ID,
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
    modern = bundle['schema_version'] == 2
    if modern:
        require(all(name in bundle for name in ('history_urls', 'product_history',
            'history_receipts', 'history_errors')),
            'EIA product history coverage state missing')
        require(('release_schedule' in bundle and 'schedule_receipt' in bundle)
                != ('schedule_error' in bundle),
                'EIA release schedule success-or-error state missing')
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
            if not modern and key in ('schema_version', 'history_urls'):
                continue  # v1.17 capture before product histories were introduced.
            require(bundle.get(key) == value, 'EIA derived value differs from raw: ' + key)
        histories = bundle.get('product_history', {})
        receipts = bundle.get('history_receipts', {})
        errors = bundle.get('history_errors', {})
        if modern or any(name in bundle for name in ('product_history', 'history_receipts', 'history_errors')):
            require(set(histories) == set(receipts)
                    and set(histories).isdisjoint(errors)
                    and set(histories) | set(errors) == set(HISTORY_URLS),
                    'EIA product history coverage state invalid')
            for product, observations in histories.items():
                receipt = receipts[product]
                body = (root / receipt['raw_path']).read_bytes()
                require(hashlib.sha256(body).hexdigest() == receipt['sha256'],
                        'EIA product history raw hash mismatch')
                require(observations == parse_product_history(body, product, bundle),
                        'EIA product history differs from raw: ' + product)
        if 'release_schedule' in bundle:
            receipt = bundle['schedule_receipt']
            body = (root / receipt['raw_path']).read_bytes()
            require(hashlib.sha256(body).hexdigest() == receipt['sha256'],
                    'EIA schedule raw hash mismatch')
            require(bundle['release_schedule'] == parse_schedule(
                body, bundle['captured_at'], bundle['week_end']),
                'EIA release schedule differs from raw')
            require('schedule_error' not in bundle, 'EIA schedule state ambiguous')
        elif 'schedule_receipt' in bundle:
            raise EnergyError('EIA schedule receipt has no parsed events')


def collect(previous, stamp, data_dir=DATA, fetch=_fetch):
    try:
        json_body = fetch(JSON_URL)
        csv_body = fetch(TABLE_URL)
        bundle = parse_sources(json_body, csv_body, stamp)
        bundle['receipts'] = dict(json=_raw(data_dir, json_body, 'json'),
                                  table=_raw(data_dir, csv_body, 'csv'))
        bundle['product_history'] = {}
        bundle['history_receipts'] = {}
        bundle['history_errors'] = {}
        for product, url in HISTORY_URLS.items():
            try:
                body = fetch(url)
                observations = parse_product_history(body, product, bundle)
                bundle['product_history'][product] = observations
                bundle['history_receipts'][product] = _raw(data_dir, body, 'html')
            except Exception as error:
                bundle['history_errors'][product] = (str(error) if isinstance(error, EnergyError)
                    else 'EIA product history request or normalization failed')
        try:
            body = fetch(SCHEDULE_URL)
            bundle['release_schedule'] = parse_schedule(body, stamp, bundle['week_end'])
            bundle['schedule_receipt'] = _raw(data_dir, body, 'html')
        except Exception as error:
            bundle['schedule_error'] = (str(error) if isinstance(error, EnergyError)
                else 'EIA release schedule request or normalization failed')
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
    for product, error in bundle.get('history_errors', {}).items():
        print(product + ' history unavailable: ' + error)
    if bundle.get('schedule_error'):
        print('release schedule unavailable: ' + bundle['schedule_error'])


if __name__ == '__main__':
    main()
