"""Keyless Philadelphia Fed SPF median forecasts with release-date provenance.

These are current historical workbook cells, not archived original workbook vintages.
Only surveys with a documented, elapsed news release date are published.
"""
import hashlib
import io
import json
import math
import re
import subprocess
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'spf'
BASE = ('https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/'
        'survey-of-professional-forecasters/')
URLS = {name: BASE + filename for name, filename in (
    ('medianGrowth', 'historical-data/medianGrowth.xlsx'),
    ('medianLevel', 'historical-data/medianLevel.xlsx'),
    ('release_dates', 'spf-release-dates.txt'),
)}
SHEET_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PACKAGE_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
N = {'s': SHEET_NS}
SERIES = {
    'RGDP': ('medianGrowth', 'drgdp', 'percent, quarter-over-quarter annualized growth'),
    'UNEMP': ('medianLevel', 'UNEMP', 'percent, quarterly average'),
    'CPI': ('medianLevel', 'CPI', 'percent, quarter-over-quarter annualized change'),
    'CORECPI': ('medianLevel', 'CORECPI', 'percent, quarter-over-quarter annualized change'),
    'PCE': ('medianLevel', 'PCE', 'percent, quarter-over-quarter annualized change'),
    'COREPCE': ('medianLevel', 'COREPCE', 'percent, quarter-over-quarter annualized change'),
}


class SPFError(ValueError):
    """Source structure or release safety cannot be established."""


def require(ok, message):
    if not ok:
        raise SPFError(message)


def _year_quarter(year, quarter):
    require(1900 <= year <= 2100 and 1 <= quarter <= 4, 'Invalid survey quarter')
    return f'{year}Q{quarter}'


def target_quarter(survey, suffix):
    """Suffix 2 is survey quarter; 3 is the next quarter, through 6 at +4."""
    require(re.fullmatch(r'\d{4}Q[1-4]', survey) and suffix in range(2, 7),
            'Invalid SPF target mapping')
    year, quarter = int(survey[:4]), int(survey[-1])
    index = year * 4 + quarter - 1 + suffix - 2
    return f'{index // 4}Q{index % 4 + 1}'


def parse_release_dates(body):
    require(isinstance(body, bytes) and len(body) < 1_000_000, 'Invalid release-date response')
    try:
        lines = body.decode('utf-8-sig').splitlines()
    except UnicodeError as exc:
        raise SPFError('Release dates are not UTF-8 text') from exc
    require(any('prior to 1990:Q2 are not known' in line for line in lines),
            'Release-date scope statement missing')
    dates, year = {}, None
    pattern = re.compile(r'^\s*(?:(\d{4})\s+)?Q([1-4])\s+(\d{1,2}/\d{1,2}/\d{2,4})\**\s+(\d{1,2}/\d{1,2}/\d{2,4})\**\s*$')
    for line in lines:
        match = pattern.match(line)
        if not match:
            continue
        if match[1]:
            year = int(match[1])
        require(year is not None, 'Quarter precedes release year')
        survey = _year_quarter(year, int(match[2]))
        if survey == '1990Q2':
            continue  # The source flags this release as not real time.
        require(survey not in dates, f'Duplicate SPF release date for {survey}')
        token = match[4]
        month, day, release_year = map(int, token.split('/'))
        if release_year < 100:
            release_year += 1900 if release_year >= 90 else 2000
        try:
            released = date(release_year, month, day)
        except ValueError as exc:
            raise SPFError('Invalid SPF release date') from exc
        require(release_year == year, 'Ambiguous SPF release date')
        dates[survey] = released.isoformat()
    require(dates and min(dates) == '1990Q3', 'No documented SPF release history')
    return dates


def _shared_strings(archive):
    if 'xl/sharedStrings.xml' not in archive.namelist():
        return []
    root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
    return [''.join(t.text or '' for t in si.findall('.//s:t', N))
            for si in root.findall('s:si', N)]


def _cell_value(cell, strings):
    kind = cell.get('t')
    if kind == 'inlineStr':
        return ''.join(t.text or '' for t in cell.findall('.//s:t', N))
    value = cell.findtext('s:v', namespaces=N)
    if kind == 's':
        require(value is not None and value.isdigit() and int(value) < len(strings),
                'Invalid shared-string index')
        return strings[int(value)]
    require(kind not in ('e', 'b'), 'Error or boolean in SPF workbook')
    return value


def _sheet_paths(archive):
    workbook = ET.fromstring(archive.read('xl/workbook.xml'))
    relations = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    targets = {}
    for relation in relations:
        if relation.get('Type', '').endswith('/worksheet'):
            target = relation.get('Target', '').lstrip('/')
            target = target if target.startswith('xl/') else 'xl/' + target
            require('..' not in Path(target).parts and target in archive.namelist(),
                    'Invalid worksheet target')
            targets[relation.get('Id')] = target
    paths = {}
    for sheet in workbook.findall('.//s:sheet', N):
        name, relationship = sheet.get('name'), sheet.get(f'{{{REL_NS}}}id')
        require(name not in paths and relationship in targets, 'Missing or duplicate worksheet')
        paths[name] = targets[relationship]
    return paths


def parse_workbook(body, wanted):
    """Return selected sheet rows as (survey, suffix -> (number, A1 cell))."""
    require(isinstance(body, bytes) and body.startswith(b'PK') and len(body) <= 20_000_000,
            'SPF response is not a bounded XLSX workbook')
    try:
        archive = zipfile.ZipFile(io.BytesIO(body))
        info = archive.infolist()
        require(len(info) <= 250 and sum(item.file_size for item in info) <= 100_000_000,
                'SPF workbook exceeds bounded ZIP structure')
        strings, paths = _shared_strings(archive), _sheet_paths(archive)
        result = {}
        for sheet, prefix in wanted.items():
            require(sheet in paths, f'Missing SPF sheet {sheet}')
            root = ET.fromstring(archive.read(paths[sheet]))
            rows = root.findall('.//s:sheetData/s:row', N)
            require(len(rows) >= 2, f'Empty SPF sheet {sheet}')
            def cells(row):
                return {cell.get('r'): _cell_value(cell, strings)
                        for cell in row.findall('s:c', N)}
            header = cells(rows[0])
            columns = {}
            for suffix in range(2, 7):
                name = f'{prefix}{suffix}'
                matches = [re.match(r'^[A-Z]+', ref).group() for ref, value in header.items()
                           if value == name and re.fullmatch(r'[A-Z]+1', ref)]
                require(len(matches) == 1, f'Missing or duplicate SPF column {name}')
                columns[suffix] = matches[0]
            require(header.get('A1') == 'YEAR' and header.get('B1') == 'QUARTER',
                    f'Invalid SPF row headers in {sheet}')
            selected = {}
            for row in rows[1:]:
                row_number = row.get('r')
                require(row_number and row_number.isdigit(), 'Invalid SPF row address')
                values = cells(row)
                if not values:
                    continue
                try:
                    year_float, quarter_float = float(values.get(f'A{row_number}')), float(values.get(f'B{row_number}'))
                except (TypeError, ValueError) as exc:
                    raise SPFError(f'Missing survey identity in {sheet}') from exc
                require(year_float.is_integer() and quarter_float.is_integer(), 'Fractional SPF survey identity')
                survey = _year_quarter(int(year_float), int(quarter_float))
                require(survey not in selected, f'Duplicate SPF survey {survey} in {sheet}')
                points = {}
                for suffix, column in columns.items():
                    ref = f'{column}{row_number}'
                    raw = values.get(ref)
                    if raw is None or raw in ('', '#N/A'):
                        continue
                    try:
                        number = float(raw)
                    except ValueError as exc:
                        raise SPFError(f'Non-numeric SPF forecast at {sheet}!{ref}') from exc
                    require(math.isfinite(number), f'Nonfinite SPF forecast at {sheet}!{ref}')
                    require(sheet != 'UNEMP' or 0 <= number <= 100,
                            f'Invalid unemployment forecast at {sheet}!{ref}')
                    points[suffix] = (number, f'{sheet}!{ref}')
                selected[survey] = points
            result[sheet] = selected
        return result
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise SPFError('Malformed SPF XLSX workbook') from exc


def build_snapshot(growth, level, release_text, captured_at, sources):
    """Build a complete validated snapshot from the three retained official bytes."""
    now = datetime.fromisoformat(captured_at.replace('Z', '+00:00'))
    require(now.tzinfo is not None, 'Capture timestamp requires a time zone')
    dates = parse_release_dates(release_text)
    books = {'medianGrowth': parse_workbook(growth, {'RGDP': 'drgdp'}),
             'medianLevel': parse_workbook(level, {key: key for key in SERIES if key != 'RGDP'})}
    latest_date_survey = max(dates)
    current_quarter = f'{now.year}Q{(now.month - 1) // 3 + 1}'
    series = {}
    for metric, (book, sheet, unit) in SERIES.items():
        rows, points = books[book][metric], []
        for survey in sorted(rows):
            if survey < '1990Q3':
                continue
            if survey not in dates:
                require(survey > latest_date_survey and survey > current_quarter,
                        f'Missing historical release date for {survey}')
                continue
            released = dates[survey]
            if released >= now.date().isoformat():
                continue  # Date-only source cannot prove release happened during its calendar day.
            for suffix in range(2, 7):
                if suffix in rows[survey]:
                    value, cell = rows[survey][suffix]
                    points.append(dict(survey=survey, released=released,
                                       target=target_quarter(survey, suffix), value=value, cell=cell))
        require(points, f'No released SPF forecasts for {metric}')
        series[metric] = {'unit': unit, 'workbook': book, 'points': points}
    return {'source': 'Federal Reserve Bank of Philadelphia · Survey of Professional Forecasters',
            'vintage': 'Current published median workbooks captured at the stated time; historical cells may have been revised',
            'status': 'ok', 'captured_at': captured_at, 'attempted_at': captured_at,
            'error': None, 'sources': sources, 'series': series}


def _fetch(url):
    run = subprocess.run(['curl', '--http1.1', '--fail', '--location', '--silent', '--show-error',
                          '--max-time', '40', '--user-agent',
                          'PublicRecord/1.7 github.com/AustinMermans/public-record', url],
                         capture_output=True, timeout=50)
    require(run.returncode == 0 and run.stdout, 'Philadelphia Fed request failed')
    return run.stdout


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
        temporary = Path(handle.name)
    temporary.replace(path)


def collect(data_dir=DATA, fetch=_fetch, captured_at=None):
    """Refresh one atomic capture; a failed refresh keeps the last good values."""
    stamp = captured_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
    current = data_dir / 'current.json'
    previous = json.loads(current.read_text()) if current.exists() else None
    try:
        bodies = {name: fetch(url) for name, url in URLS.items()}
        sources = {}
        for name, body in bodies.items():
            require(isinstance(body, bytes) and len(body) <= 20_000_000,
                    'Philadelphia Fed response exceeds bounded source size')
            digest = hashlib.sha256(body).hexdigest()
            ext = 'txt' if name == 'release_dates' else 'xlsx'
            relative = Path('data/spf/raw') / f'{digest}.{ext}'
            sources[name] = {'url': URLS[name], 'sha256': digest, 'raw_path': str(relative)}
        snapshot = build_snapshot(bodies['medianGrowth'], bodies['medianLevel'],
                                  bodies['release_dates'], stamp, sources)
        raw = data_dir / 'raw'
        raw.mkdir(parents=True, exist_ok=True)
        for name, body in bodies.items():
            path = data_dir / 'raw' / Path(sources[name]['raw_path']).name
            if not path.exists():
                path.write_bytes(body)
        if previous and previous.get('captured_at') and previous.get('series'):
            _write_json(data_dir / 'comparison-baseline.json', previous)
        _write_json(current, snapshot)
        return snapshot
    except (SPFError, OSError, subprocess.TimeoutExpired, ValueError) as exc:
        state = dict(previous) if previous and previous.get('status') in ('ok', 'stale') else {
            'source': 'Federal Reserve Bank of Philadelphia · Survey of Professional Forecasters',
            'series': {}, 'sources': {}, 'captured_at': None}
        state.update(status='stale' if state['captured_at'] else 'unavailable',
                     attempted_at=stamp, error=str(exc)[:250])
        _write_json(current, state)
        return state


def validate_capture(capture, root=ROOT):
    """Reconcile every published point to retained official source bytes."""
    require(capture.get('status') in ('ok', 'stale', 'unavailable'), 'Invalid SPF capture status')
    if capture['status'] == 'unavailable':
        require(not capture.get('captured_at') and not capture.get('series'),
                'Unavailable SPF capture has published forecasts')
        return
    require(capture.get('captured_at') and capture.get('sources') and capture.get('series'),
            'SPF successful capture lacks source evidence')
    raw = {}
    for name in URLS:
        item = capture['sources'].get(name)
        require(isinstance(item, dict) and item.get('url') == URLS[name], 'SPF source URL mismatch')
        path = (root / item.get('raw_path', '')).resolve()
        require(path.is_relative_to(root.resolve() / 'data' / 'spf' / 'raw') and path.is_file(),
                'SPF raw evidence path missing or outside approved directory')
        body = path.read_bytes()
        require(hashlib.sha256(body).hexdigest() == item.get('sha256'), 'SPF raw evidence hash mismatch')
        raw[name] = body
    reconstructed = build_snapshot(raw['medianGrowth'], raw['medianLevel'],
                                   raw['release_dates'], capture['captured_at'], capture['sources'])
    require(reconstructed['series'] == capture['series'], 'SPF published series differs from source cells')
    if capture['status'] == 'stale':
        require(capture.get('attempted_at') and capture['attempted_at'] >= capture['captured_at'],
                'Stale SPF capture lacks a later attempt')


if __name__ == '__main__':
    outcome = collect()
    print(json.dumps({'status': outcome['status'], 'captured_at': outcome['captured_at'],
                      'attempted_at': outcome['attempted_at'], 'error': outcome['error'],
                      'counts': {name: len(spec['points']) for name, spec in outcome['series'].items()}},
                     sort_keys=True))
    # A source outage is visible as stale/unavailable data, not a failure of
    # the other independent publication channels.
