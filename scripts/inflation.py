"""Source-bound Cleveland Fed inflation nowcasts.

The public table is a model forecast, not a CPI/PCE release or a survey
consensus. Retained captures form a collection-era history only; they do not
reconstruct the publisher's original daily editions before this project.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
import subprocess
from datetime import date, datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'inflation'
URL = 'https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting'
MONTH_URL = 'https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json?sc_lang=en'
EASTERN = ZoneInfo('America/New_York')
CAPTIONS = {
    'Inflation, month-over-month percent change': 'mom',
    'Inflation, year-over-year percent change': 'yoy',
    'Quarterly annualized percent change': 'quarterly_saar',
}
HEADER = ['Month', 'CPI', 'Core CPI', 'PCE', 'Core PCE', 'Updated']
MEASURES = ('cpi', 'core_cpi', 'pce', 'core_pce')
MONTH_SERIES = ('CPI Inflation', 'Core CPI Inflation', 'PCE Inflation', 'Core PCE Inflation',
                'Actual CPI Inflation', 'Actual Core CPI Inflation',
                'Actual PCE Inflation', 'Actual Core PCE Inflation')


class InflationError(ValueError):
    pass


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = None
        self.section = None
        self.row = None
        self.cell = None
        self.caption = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.table = {'caption': '', 'header': [], 'body': [], 'footnote': []}
            self.section = None
        elif self.table is not None and tag in ('thead', 'tbody', 'tfoot'):
            self.section = tag
        elif self.table is not None and tag == 'caption':
            self.caption = []
        elif self.table is not None and self.section in ('thead', 'tbody') and tag == 'tr':
            self.row = []
        elif self.row is not None and tag in ('th', 'td'):
            self.cell = []

    def handle_data(self, value):
        if self.cell is not None:
            self.cell.append(value)
        elif self.caption is not None:
            self.caption.append(value)
        elif self.table is not None and self.section == 'tfoot':
            self.table['footnote'].append(value)

    def handle_endtag(self, tag):
        if tag == 'caption' and self.caption is not None:
            self.table['caption'] = ' '.join(''.join(self.caption).split())
            self.caption = None
        elif tag in ('th', 'td') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table['header' if self.section == 'thead' else 'body'].append(self.row)
            self.row = None
        elif tag in ('thead', 'tbody', 'tfoot'):
            self.section = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def _updated(label, captured_day):
    match = re.fullmatch(r'(\d{2})/(\d{2})', label)
    if not match:
        raise InflationError('Unrecognized Cleveland Fed update date')
    for year in (captured_day.year, captured_day.year - 1):
        try:
            candidate = date(year, int(match[1]), int(match[2]))
        except ValueError:
            continue
        if candidate <= captured_day and (captured_day - candidate).days <= 31:
            return candidate.isoformat()
    raise InflationError('Cleveland Fed update date is future or ambiguous')


def _target(label, basis):
    if basis == 'quarterly_saar':
        match = re.fullmatch(r'(20\d{2}):Q([1-4])', label)
        if not match:
            raise InflationError('Unrecognized quarterly inflation target')
        return f'{match[1]}Q{match[2]}'
    try:
        month = datetime.strptime(label, '%B %Y').date()
    except ValueError as exc:
        raise InflationError('Unrecognized monthly inflation target') from exc
    return month.strftime('%Y-%m')


def parse_page(raw, captured_at):
    captured = datetime.fromisoformat(captured_at)
    if captured.tzinfo is None:
        raise InflationError('Capture time needs a timezone')
    parser = _Tables()
    parser.feed(raw.decode('utf-8-sig'))
    found = [table for table in parser.tables if table['caption'] in CAPTIONS]
    if len(found) != 3 or {table['caption'] for table in found} != set(CAPTIONS):
        raise InflationError('Expected three distinct Cleveland Fed nowcast tables')
    captured_day = captured.astimezone(EASTERN).date()
    rows = []
    for table in found:
        basis = CAPTIONS[table['caption']]
        expected = HEADER if basis != 'quarterly_saar' else ['Quarter', *HEADER[1:]]
        if table['header'] != [expected] or not 1 <= len(table['body']) <= 6:
            raise InflationError('Nowcast table layout changed')
        period = 'quarter' if basis == 'quarterly_saar' else 'month'
        footnote = ' '.join(''.join(table['footnote']).split())
        expected_note = ('Note: If the cell is blank, it implies that the actual data corresponding '
                         f'to the {period} for that inflation measure have already been released.')
        if footnote != expected_note:
            raise InflationError('Publisher blank-cell explanation changed')
        for source_row in table['body']:
            if len(source_row) != 6:
                raise InflationError('Nowcast row width changed')
            values = {}
            for measure, value in zip(MEASURES, source_row[1:5]):
                if value and not re.fullmatch(r'-?\d{1,3}\.\d{2}', value):
                    raise InflationError('Nowcast cell is not a two-decimal percent')
                if value and not -100 <= Decimal(value) <= 100:
                    raise InflationError('Nowcast cell outside plausible percent bounds')
                values[measure] = value or None
            rows.append(dict(basis=basis, target=_target(source_row[0], basis),
                             updated_on=_updated(source_row[5], captured_day), values=values))
        if not any(any(row['values'].values()) for row in rows if row['basis'] == basis):
            raise InflationError('Nowcast table has no forecast values')
    if len({(row['basis'], row['target']) for row in rows}) != len(rows):
        raise InflationError('Duplicate inflation nowcast target')
    return rows


def extract_tables(response):
    """Retain only the three exact public table fragments, not the whole page."""
    fragments = []
    for table in re.findall(rb'<table\b[^>]*>.*?</table>', response, flags=re.I | re.S):
        caption = re.search(rb'<caption>\s*([^<]+?)\s*</caption>', table, flags=re.I | re.S)
        if caption and caption[1].decode('utf-8') in CAPTIONS:
            fragments.append(table)
    if len(fragments) != 3:
        raise InflationError('Expected three source nowcast table fragments')
    return b'\n'.join(fragments)


def _receipt(raw, captured_at):
    excerpt = extract_tables(raw)
    digest = hashlib.sha256(excerpt).hexdigest()
    relative = f'data/inflation/raw/{digest}.tables.html.gz'
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(gzip.compress(excerpt, mtime=0))
    return dict(captured_at=captured_at, sha256=digest,
                response_sha256=hashlib.sha256(raw).hexdigest(), raw_path=relative,
                rows=parse_page(excerpt, captured_at))


def parse_month_history(raw, targets, rows, captured_at):
    """Normalize only active table targets from the publisher's current JSON edition."""
    try:
        objects = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InflationError('Monthly history JSON invalid') from exc
    if not isinstance(objects, list):
        raise InflationError('Monthly history must be a list')
    wanted = set(targets)
    selected = {}
    for obj in objects:
        chart = obj.get('chart', {}) if isinstance(obj, dict) else {}
        match = re.fullmatch(r'(20\d{2})-(\d{1,2})', chart.get('subcaption', ''))
        if not match:
            continue
        target = f'{match[1]}-{int(match[2]):02d}'
        if target in wanted:
            if target in selected:
                raise InflationError('Duplicate monthly history target')
            selected[target] = obj
    if set(selected) != wanted:
        raise InflationError('Monthly history target missing')
    excerpt = json.dumps([selected[target] for target in sorted(wanted)],
                         ensure_ascii=False, separators=(',', ':')).encode()
    normalized = normalize_month_excerpt(excerpt, rows, captured_at)
    return excerpt, normalized


def normalize_month_excerpt(excerpt, rows, captured_at):
    try:
        objects = json.loads(excerpt)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InflationError('Monthly target excerpt invalid') from exc
    captured_day = datetime.fromisoformat(captured_at).astimezone(EASTERN).date()
    targets = {row['target'] for row in rows if row['basis'] == 'mom'}
    if not isinstance(objects, list) or len(objects) != len(targets):
        raise InflationError('Monthly target excerpt incomplete')
    result = []
    for obj in objects:
        if not isinstance(obj, dict) or set(obj) != {'chart', 'categories', 'dataset'}:
            raise InflationError('Monthly target object structure changed')
        chart = obj['chart']
        match = re.fullmatch(r'(20\d{2})-(\d{1,2})', chart.get('subcaption', ''))
        if not match:
            raise InflationError('Monthly chart target invalid')
        target = f'{match[1]}-{int(match[2]):02d}'
        if target not in targets or any(item['target'] == target for item in result):
            raise InflationError('Monthly chart target not in verified table')
        if chart.get('yaxisname') != 'Month-over-month percent change':
            raise InflationError('Monthly chart rate definition changed')
        edition = chart.get('_comment', '')
        if not re.fullmatch(r'20\d{2}-\d{2}-\d{2} 00:00', edition):
            raise InflationError('Monthly chart edition date invalid')
        edition_day = date.fromisoformat(edition[:10])
        if edition_day > captured_day or (captured_day - edition_day).days > 31:
            raise InflationError('Monthly chart edition date future or stale')
        categories = obj['categories']
        if not isinstance(categories, list) or len(categories) != 1 or not isinstance(categories[0].get('category'), list):
            raise InflationError('Monthly chart categories changed')
        dates = []
        year = int(match[1])
        last = None
        for item in categories[0]['category']:
            label = item.get('label', '')
            if item.get('vline') == 'true':
                if re.fullmatch(r'\d{2}/\d{2}', label):
                    raise InflationError('Dated category unexpectedly marked as a release line')
                continue
            day_match = re.fullmatch(r'(\d{2})/(\d{2})', label)
            if not day_match:
                raise InflationError('Monthly chart date label changed')
            month, day = map(int, day_match.groups())
            candidate = date(year, month, day)
            if last and candidate <= last:
                if last.month == 12 and month == 1:
                    year += 1
                    candidate = date(year, month, day)
                else:
                    raise InflationError('Monthly chart dates are nonmonotone')
            if candidate > captured_day or (candidate - date(int(match[1]), int(match[2]), 1)).days > 120:
                raise InflationError('Monthly chart date outside target window')
            dates.append(candidate.isoformat())
            last = candidate
        if not dates or len(dates) > 90:
            raise InflationError('Monthly chart date coverage invalid')
        datasets = obj['dataset']
        if not isinstance(datasets, list) or [item.get('seriesname') for item in datasets] != list(MONTH_SERIES):
            raise InflationError('Monthly chart series identities changed')
        series = {}
        for metric, dataset in zip(MEASURES, datasets[:4]):
            cells = dataset.get('data')
            if not isinstance(cells, list) or len(cells) != len(dates):
                raise InflationError('Monthly chart series length changed')
            points = []
            for day, cell in zip(dates, cells):
                value = cell.get('value', '')
                if value == '':
                    continue
                if not isinstance(value, str) or not re.fullmatch(r'-?\d{1,3}\.\d{1,17}', value):
                    raise InflationError('Monthly chart estimate invalid')
                number = Decimal(value)
                if not -100 <= number <= 100:
                    raise InflationError('Monthly chart estimate outside percent bounds')
                points.append([day, value])
            current = next(row['values'][metric] for row in rows if row['basis']=='mom' and row['target']==target)
            final = cells[-1].get('value', '')
            rounded = str(Decimal(final).quantize(Decimal('0.01'))) if final else None
            if rounded != current:
                raise InflationError('Monthly chart latest estimate disagrees with public table')
            series[metric] = points
        result.append(dict(target=target, edition_date=edition_day.isoformat(), series=series))
    if {item['target'] for item in result} != targets:
        raise InflationError('Monthly chart excerpt lacks table targets')
    return sorted(result, key=lambda item: item['target'])


def _history_receipt(raw, rows, captured_at):
    targets = [row['target'] for row in rows if row['basis']=='mom']
    excerpt, paths = parse_month_history(raw, targets, rows, captured_at)
    digest = hashlib.sha256(excerpt).hexdigest()
    relative = f'data/inflation/raw/{digest}.month-targets.json.gz'
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(gzip.compress(excerpt, mtime=0))
    return dict(url=MONTH_URL, sha256=digest, response_sha256=hashlib.sha256(raw).hexdigest(),
                raw_path=relative, paths=paths)


def _raw(snapshot, root):
    digest = snapshot.get('sha256', '')
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise InflationError('Invalid inflation source digest')
    expected = f'data/inflation/raw/{digest}.tables.html.gz'
    if snapshot.get('raw_path') != expected:
        raise InflationError('Invalid inflation raw path')
    body = gzip.decompress((Path(root) / expected).read_bytes())
    if hashlib.sha256(body).hexdigest() != digest:
        raise InflationError('Inflation source digest mismatch')
    return body


def validate_capture(bundle, root=ROOT):
    if bundle.get('url') != URL or bundle.get('schema_version') != 1:
        raise InflationError('Unexpected inflation source or schema')
    attempted = datetime.fromisoformat(bundle['attempted_at'])
    if attempted.tzinfo is None:
        raise InflationError('Inflation attempt clock lacks timezone')
    status = bundle.get('status')
    if status == 'unavailable':
        if bundle.get('rows') or bundle.get('history') or bundle.get('sha256') or bundle.get('publisher_history'):
            raise InflationError('Unavailable inflation capture has unverified values')
        if bundle.get('changes') != compare(None, bundle):
            raise InflationError('Unavailable inflation change channel invalid')
        return
    if status not in ('ok', 'stale'):
        raise InflationError('Invalid inflation capture status')
    captured = datetime.fromisoformat(bundle['captured_at'])
    if captured.tzinfo is None or captured > attempted:
        raise InflationError('Inflation capture clock is invalid')
    snapshots = bundle.get('history')
    if not isinstance(snapshots, list) or not snapshots:
        raise InflationError('Inflation capture history missing')
    if [s['captured_at'] for s in snapshots] != sorted({s['captured_at'] for s in snapshots}):
        raise InflationError('Inflation capture history is unordered or duplicated')
    for snapshot in snapshots:
        if not re.fullmatch(r'[0-9a-f]{64}', snapshot.get('response_sha256', '')):
            raise InflationError('Invalid full-response digest receipt')
        if parse_page(_raw(snapshot, root), snapshot['captured_at']) != snapshot.get('rows'):
            raise InflationError('Inflation rows differ from retained publisher page')
    latest = snapshots[-1]
    if any(bundle.get(key) != latest[key] for key in ('captured_at', 'sha256', 'response_sha256', 'raw_path', 'rows')):
        raise InflationError('Inflation current values differ from last verified snapshot')
    published = bundle.get('publisher_history')
    if published:
        digest = published.get('sha256', '')
        if published.get('url') != MONTH_URL or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise InflationError('Inflation publisher history receipt invalid')
        if not re.fullmatch(r'[0-9a-f]{64}', published.get('response_sha256', '')):
            raise InflationError('Inflation history full-response digest invalid')
        relative = f'data/inflation/raw/{digest}.month-targets.json.gz'
        if published.get('raw_path') != relative:
            raise InflationError('Inflation history excerpt path invalid')
        raw = gzip.decompress((Path(root) / relative).read_bytes())
        if hashlib.sha256(raw).hexdigest() != digest:
            raise InflationError('Inflation history excerpt digest mismatch')
        if normalize_month_excerpt(raw, bundle['rows'], bundle['captured_at']) != published.get('paths'):
            raise InflationError('Inflation history differs from source excerpt')
    elif not bundle.get('history_error'):
        raise InflationError('Inflation publisher history needs a receipt or explicit gap')
    previous = (dict(status='ok', captured_at=snapshots[-2]['captured_at'], rows=snapshots[-2]['rows'])
                if status == 'ok' and len(snapshots) > 1 else
                dict(status='ok', captured_at=latest['captured_at'], rows=latest['rows'])
                if status == 'stale' else None)
    if bundle.get('changes') != compare(previous, bundle):
        raise InflationError('Inflation change events differ from verified snapshots')


def compare(previous, current):
    old = previous if previous and previous.get('status') in ('ok', 'stale') else None
    channel = dict(id='cleveland-inflation-nowcast', label='Cleveland Fed inflation nowcast',
                   from_capture=(old or {}).get('captured_at'),
                   to_capture=current.get('captured_at'))
    result = dict(items=[], channels=[channel], baselines=[], skipped=[])
    if current['status'] != 'ok':
        channel.update(status='unavailable', error=current.get('error'))
        result['skipped'].append(channel['id'])
        return result
    if not old:
        channel['status'] = 'baseline'
        result['baselines'].append(channel['id'])
        return result
    channel['status'] = 'compared'
    earlier = {(r['basis'], r['target']): r for r in old['rows']}
    for row in current['rows']:
        prior = earlier.get((row['basis'], row['target']))
        if not prior:
            continue
        for metric in MEASURES:
            before, after = prior['values'][metric], row['values'][metric]
            if before == after:
                continue
            unit = ('percent, monthly nonannualized' if row['basis'] == 'mom' else
                    'percent, year over year' if row['basis'] == 'yoy' else
                    'percent, quarterly annualized')
            result['items'].append(dict(source_id=channel['id'], publisher='Federal Reserve Bank of Cleveland',
                title=f'{metric.upper().replace("_", " ")} inflation nowcast · {row["target"]}',
                kind='Inflation nowcast value changed' if before and after else
                     'Inflation nowcast now unavailable' if before else 'Newly available inflation nowcast',
                date=row['updated_on'], url=URL, metric_id=metric,
                basis=row['basis'], target=row['target'], unit=unit, before=before, after=after,
                from_capture=old['captured_at'], to_capture=current['captured_at'],
                summary='Same measure and target; a model estimate, not consensus or an official release.'))
    return result


def collect(fetch=None, fetch_month=None):
    attempted = datetime.now(timezone.utc).isoformat(timespec='seconds')
    old_path = DATA / 'current.json'
    old = json.loads(old_path.read_text()) if old_path.exists() else None
    if fetch is None:
        def fetch():
            process = subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                                      '--max-time', '45', URL], capture_output=True, timeout=55)
            if process.returncode:
                raise InflationError(process.stderr.decode(errors='replace')[:180])
            return process.stdout
    if fetch_month is None:
        def fetch_month():
            process = subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                                      '--max-time', '55', MONTH_URL], capture_output=True, timeout=65)
            if process.returncode:
                raise InflationError(process.stderr.decode(errors='replace')[:180])
            return process.stdout
    try:
        raw = fetch()
        snapshot = _receipt(raw, attempted)
        history = copy.deepcopy((old or {}).get('history', []))
        history.append(snapshot)
        bundle = dict(schema_version=1, status='ok', url=URL, attempted_at=attempted,
                      history=history, **snapshot)
        try:
            bundle['publisher_history'] = _history_receipt(fetch_month(), snapshot['rows'], attempted)
        except Exception as exc:
            bundle['history_error'] = str(exc)
    except Exception as exc:
        retained = old if old and old.get('status') in ('ok', 'stale') else None
        bundle = dict(copy.deepcopy(retained) if retained else {}, schema_version=1,
                      status='stale' if retained else 'unavailable', url=URL,
                      attempted_at=attempted, error=str(exc))
    bundle['changes'] = compare(old, bundle)
    validate_capture(bundle)
    DATA.mkdir(parents=True, exist_ok=True)
    old_path.write_text(json.dumps(bundle, separators=(',', ':')))
    (DATA / ('capture-' + attempted[:19].replace(':', '') + '.json')).write_text(
        json.dumps(dict(schema_version=1, status=bundle['status'], attempted_at=attempted,
                        snapshot=snapshot if bundle['status']=='ok' else None,
                        error=bundle.get('error')), separators=(',', ':')))
    return bundle


if __name__ == '__main__':
    result = collect()
    print('Cleveland inflation nowcast:', result['status'], len(result.get('rows', [])),
          'table rows', result.get('error', ''))
