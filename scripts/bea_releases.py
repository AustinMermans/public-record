"""Keyless, source-bound BEA real-GDP release history.

The BEA full schedule supplies discovery, not actuals. A GDP estimate enters the
history only after the schedule links to a news release and the linked page's
own title, embargo time, target quarter, estimate stage, and current-stage real
GDP growth sentence all reconcile. Historical FRED observations are not used.
"""
import copy
import hashlib
import json
import math
import re
import subprocess
import tempfile
from datetime import date, datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bea_changes import compare_bea_releases

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'bea_releases'
SCHEDULE_URL = 'https://www.bea.gov/news/schedule/full'
SOURCE = 'U.S. Bureau of Economic Analysis'
BASIS = 'quarterly seasonally adjusted annual rate'
STAGES = {'advance': 0, 'second': 1, 'third': 2}
VOID_TAGS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
             'link', 'meta', 'param', 'source', 'track', 'wbr'}
MONTHS = {name: number for number, name in enumerate(
    ('', 'January', 'February', 'March', 'April', 'May', 'June',
     'July', 'August', 'September', 'October', 'November', 'December')) if number}


class BEAError(ValueError):
    """A BEA page or publication boundary cannot be verified."""


def require(condition, message):
    if not condition:
        raise BEAError(message)


def _clean(value):
    return re.sub(r'\s+', ' ', value).strip()


def _quarter_stage(title):
    match = re.search(r'^GDP \((Advance|Second|Third) Estimate\).*?\b([1-4])(?:st|nd|rd|th) Quarter(?: and Year)? (20\d{2})\b',
                      title, re.I)
    require(match is not None, 'Not an identified quarterly GDP estimate title')
    stage = match.group(1).lower()
    return f'{match.group(3)}Q{match.group(2)}', stage


def _official_url(path):
    url = urljoin('https://www.bea.gov', path)
    parts = urlparse(url)
    require(parts.scheme == 'https' and parts.netloc == 'www.bea.gov'
            and re.fullmatch(r'/news/20\d{2}/[a-z0-9-]+', parts.path)
            and not parts.query and not parts.fragment,
            'GDP release link is not a canonical BEA news page')
    return url


class _ScheduleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.cell_depth = 0

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        classes = props.get('class', '').split()
        if tag == 'tr' and 'scheduled-releases-type-press' in classes:
            require(self.row is None, 'Nested BEA schedule row')
            self.row = {}
        elif self.row is not None:
            if tag == 'td' and self.cell is None:
                self.cell = {'class': classes, 'text': '', 'hrefs': []}
                self.cell_depth = 1
            elif self.cell is not None and tag not in VOID_TAGS:
                self.cell_depth += 1
                if tag == 'a' and props.get('href'):
                    self.cell['hrefs'].append(props['href'])

    def handle_data(self, data):
        if self.cell is not None:
            self.cell['text'] += data + ' '

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if self.cell is not None:
            self.cell_depth -= 1
            if tag == 'td' and self.cell_depth == 0:
                classes = self.cell['class']
                key = ('date' if 'scheduled-date' in classes else
                       'title' if 'release-title' in classes else
                       'url' if 'views-field-field-scheduled-release-url' in classes else None)
                if key:
                    require(key not in self.row, 'Duplicate BEA schedule cell')
                    self.row[key] = self.cell
                self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def _scheduled_date(label, quarter):
    match = re.fullmatch(r'([A-Z][a-z]+) (\d{1,2}) (?:\d{1,2}:\d{2} [AP]M)?', _clean(label))
    require(match is not None and match.group(1) in MONTHS, 'Invalid BEA schedule date')
    month = MONTHS[match.group(1)]
    target_year, target_quarter = int(quarter[:4]), int(quarter[-1])
    # Estimates of Q4 are released in the following year; all other quarters
    # normally release in the target year. Delayed Q4 releases still fit.
    year = target_year + (target_quarter == 4)
    return date(year, month, int(match.group(2))).isoformat()


def parse_schedule(body):
    require(isinstance(body, bytes) and 100 < len(body) <= 3_000_000,
            'Missing or oversized BEA schedule HTML')
    try:
        html = body.decode('utf-8-sig')
    except UnicodeError as exc:
        raise BEAError('BEA schedule is not UTF-8') from exc
    require('Release Schedule' in html and 'scheduled-releases-type-press' in html,
            'BEA full schedule structure missing')
    parser = _ScheduleHTML()
    parser.feed(html)
    require(parser.rows and parser.row is None and parser.cell is None,
            'Incomplete BEA schedule table')
    output = []
    for row in parser.rows:
        title = _clean(row.get('title', {}).get('text', ''))
        if not title.startswith('GDP ('):
            continue
        quarter, stage = _quarter_stage(title)
        if quarter < '2025Q4':
            continue
        require({'date', 'title', 'url'} <= row.keys(), 'Incomplete BEA GDP schedule row')
        stamp = _scheduled_date(row['date']['text'], quarter)
        hrefs = row['url']['hrefs']
        require(len(hrefs) <= 1, 'Ambiguous BEA GDP release link')
        url = _official_url(hrefs[0]) if hrefs else None
        output.append(dict(quarter=quarter, stage=stage, date=stamp, title=title, url=url))
    require(output, 'No recent quarterly GDP rows in BEA full schedule')
    keys = [(row['quarter'], row['stage']) for row in output]
    require(len(keys) == len(set(keys)), 'Duplicate BEA GDP schedule stage')
    return sorted(output, key=lambda row: (row['quarter'], STAGES[row['stage']]))


class _ReleaseHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.description = None
        self.canonical = None
        self.title = None
        self.embargo = None
        self.paragraphs = []
        self._h1 = None
        self._embargo = None
        self._body_depth = 0
        self._p = None
        self._p_depth = 0

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        classes = props.get('class', '').split()
        if tag == 'meta' and props.get('name') == 'description':
            self.description = props.get('content')
        if tag == 'link' and props.get('rel') == 'canonical':
            self.canonical = props.get('href')
        if tag == 'h1' and self._h1 is None:
            self._h1 = ''
        if 'field--name-field-release-date' in classes:
            self._embargo = ''
        if 'release-body' in classes and self._body_depth == 0:
            self._body_depth = 1
        elif self._body_depth and tag not in VOID_TAGS:
            self._body_depth += 1
            if tag == 'p' and self._p is None:
                self._p = ''
                self._p_depth = self._body_depth

    def handle_data(self, data):
        if self._h1 is not None:
            self._h1 += data + ' '
        if self._embargo is not None:
            self._embargo += data + ' '
        if self._p is not None:
            self._p += data + ' '

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if tag == 'h1' and self._h1 is not None:
            if self.title is None and self._h1.strip().startswith('GDP ('):
                self.title = _clean(self._h1)
            self._h1 = None
        if tag == 'div' and self._embargo is not None:
            self.embargo = _clean(self._embargo)
            self._embargo = None
        if self._body_depth:
            if tag == 'p' and self._p is not None and self._p_depth == self._body_depth:
                self.paragraphs.append(_clean(self._p))
                self._p = None
            self._body_depth -= 1


class _TableHTML(HTMLParser):
    """Only cell text and row boundaries; never consult live interactive tables."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            require(self.row is None, 'Nested BEA GDP table row')
            self.row = []
        elif tag in ('th', 'td') and self.row is not None:
            require(self.cell is None, 'Nested BEA GDP table cell')
            self.cell = [tag, '']

    def handle_data(self, data):
        if self.cell is not None:
            self.cell[1] += data + ' '

    def handle_endtag(self, tag):
        if tag in ('th', 'td') and self.cell is not None:
            self.row.append((self.cell[0], _clean(self.cell[1])))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def _table_current_stage(html, quarter, stage):
    matching = []
    for match in re.finditer(r'<table\b[^>]*>.*?</table>', html, re.I | re.S):
        table = _TableHTML()
        table.feed(match.group())
        if not table.rows or 'Real GDP and Related Measures' not in ' '.join(
                value for _, value in table.rows[0]):
            continue
        matching.append(table.rows)
    if not matching:
        return None
    require(len(matching) == 1, 'Ambiguous BEA real-GDP summary table')
    rows = matching[0]
    require(len(rows) >= 3, 'Truncated BEA real-GDP summary table')
    heading = ' '.join(value for row in rows[:3] for _, value in row)
    require(re.search(r'Percent [Cc]hange \(SAAR\)', heading),
            'BEA GDP table does not establish SAAR basis')
    span = re.search(r'from\s+(20\d{2})\s*:?\s*Q([1-4])\s+to\s+'
                     r'(?:(20\d{2})\s*:?\s*)?Q([1-4])', heading, re.I)
    require(span is not None, 'BEA GDP table target quarter missing')
    target = f'{span.group(3) or span.group(1)}Q{span.group(4)}'
    require(target == quarter, 'BEA GDP table targets a different quarter')
    stage_rows = [index for index, row in enumerate(rows[:4])
                  if any(re.fullmatch(r'(?:Advance|Second|Third) Estimate', value, re.I)
                         for _, value in row)]
    require(len(stage_rows) == 1, 'BEA GDP table stage header missing or ambiguous')
    stage_row = stage_rows[0]
    stage_columns = [_clean(value).lower() for _, value in rows[stage_row][1:]]
    stage_columns = [re.sub(r'\s+estimate$', '', value) for value in stage_columns]
    require(stage in stage_columns and len(stage_columns) == len(set(stage_columns)),
            'BEA GDP table current-stage column missing or ambiguous')
    current_index = stage_columns.index(stage) + 1
    gdp_rows = [row for row in rows[stage_row + 1:] if row and row[0][1] == 'Real GDP']
    require(len(gdp_rows) == 1 and len(gdp_rows[0]) > current_index,
            'BEA GDP table real-GDP row missing or incomplete')
    displayed = gdp_rows[0][current_index][1]
    require(re.fullmatch(r'-?\d{1,2}(?:\.\d+)?', displayed),
            'BEA GDP table current-stage cell is not numeric')
    return displayed


def _embargo_time(text):
    match = re.search(r'EMBARGOED UNTIL RELEASE AT (\d{1,2}):(\d{2}) a\.m\. (EDT|EST), '
                      r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), '
                      r'([A-Z][a-z]+) (\d{1,2}), (20\d{2})', text)
    require(match is not None and match.group(4) in MONTHS,
            'BEA release has no verifiable embargo timestamp')
    offset = -4 if match.group(3) == 'EDT' else -5
    try:
        local = datetime(int(match.group(6)), MONTHS[match.group(4)], int(match.group(5)),
                         int(match.group(1)), int(match.group(2)), tzinfo=timezone(timedelta(hours=offset)))
    except ValueError as exc:
        raise BEAError('Invalid BEA embargo date') from exc
    return local.astimezone(timezone.utc)


_GDP_PATTERN = re.compile(
    r'\bReal gross domestic product\s*\(GDP\)\s+(increased|decreased)\s+'
    r'at an annual rate of\s+(\d{1,2}(?:\.\d+)?)\s+percent\s+'
    r'in the\s+(first|second|third|fourth)\s+quarter of\s+(20\d{2})\b', re.I)


def _growth(sentence, quarter):
    match = _GDP_PATTERN.search(sentence)
    require(match is not None, 'Missing current-stage real GDP annual-rate sentence')
    number = match.group(2)
    target = f"{match.group(4)}Q{('first', 'second', 'third', 'fourth').index(match.group(3).lower()) + 1}"
    require(target == quarter, 'GDP growth sentence targets a different quarter')
    value = float(number) * (1 if match.group(1).lower() == 'increased' else -1)
    require(math.isfinite(value) and abs(value) < 100, 'Invalid BEA real GDP growth rate')
    return value, ('-' if value < 0 else '') + number


def _gdi(paragraphs, quarter):
    pattern = re.compile(r'\bReal gross domestic income\s*\(GDI\)\s+(increased|decreased)\s+'
                         r'(\d{1,2}(?:\.\d+)?)\s+percent\s+in the\s+'
                         r'(first|second|third|fourth)\s+quarter\b', re.I)
    for paragraph in paragraphs[:12]:
        match = pattern.search(paragraph)
        if match and int(quarter[-1]) == ('first', 'second', 'third', 'fourth').index(match.group(3).lower()) + 1:
            return float(match.group(2)) * (1 if match.group(1).lower() == 'increased' else -1)
    return None


def _revision_note(paragraphs):
    for paragraph in paragraphs:
        # A paragraph may discuss several measures. Bind the qualified revision
        # to a single sentence about Real GDP, not to a PCE or GDI revision.
        for sentence in re.split(r'(?<!\d)\.(?!\d)\s+', paragraph):
            match = re.search(r'\b(?:an? )?(upward|downward) revision of less than 0\.1 percentage point\b', sentence, re.I)
            if (match and re.search(r'\bReal GDP\b', sentence, re.I)
                    and not re.search(r'\b(?:PCE|GDI|final sales|gross domestic purchases|current-dollar GDP)\b', sentence, re.I)):
                article = 'an' if match.group(1).lower() == 'upward' else 'a'
                return f'BEA reports {article} {match.group(1).lower()} revision of less than 0.1 percentage point.'
    for paragraph in paragraphs[:12]:
        match = re.search(r'\bReal GDP was revised (up|down) (\d+(?:\.\d+)?) percentage point'
                          r' from the (advance|second) estimate\b', paragraph, re.I)
        if match:
            return f'Real GDP was revised {match.group(1).lower()} {match.group(2)} percentage point from the {match.group(3).lower()} estimate.'
        if re.search(r'\bReal GDP increased at the same rate as in the advance estimate\b', paragraph, re.I):
            return 'BEA reports the same displayed rate as in the advance estimate.'
    return None


def parse_release(body, scheduled, captured_at):
    require(isinstance(body, bytes) and 100 < len(body) <= 5_000_000,
            'Missing or oversized BEA release HTML')
    try:
        html = body.decode('utf-8-sig')
    except UnicodeError as exc:
        raise BEAError('BEA release is not UTF-8') from exc
    parser = _ReleaseHTML()
    parser.feed(html)
    require(parser.title and parser.embargo and parser.paragraphs,
            'BEA GDP release structure missing')
    require(parser.canonical == scheduled['url'],
            'BEA page canonical URL differs from linked schedule row')
    quarter, stage = _quarter_stage(parser.title)
    require((quarter, stage) == (scheduled['quarter'], scheduled['stage']),
            'BEA page title differs from linked schedule row')
    require(parser.title == scheduled['title'], 'BEA page title differs from schedule title')
    embargo = _embargo_time(parser.embargo)
    now = datetime.fromisoformat(captured_at.replace('Z', '+00:00'))
    require(now.tzinfo is not None and embargo <= now, 'BEA embargo has not elapsed')
    require(embargo.date().isoformat() == scheduled['date'],
            'BEA page publication date differs from schedule')
    value, display = _growth(parser.paragraphs[0], quarter)
    if parser.description:
        require(_growth(parser.description, quarter) == (value, display),
                'BEA description and release-body growth rates disagree')
    table_value = _table_current_stage(html, quarter, stage)
    if table_value is not None:
        require(table_value == display, 'BEA lead rate and current-stage SAAR table disagree')
    release = dict(quarter=quarter, stage=stage, published_at=embargo.date().isoformat(),
                   embargo_at=embargo.isoformat(timespec='minutes'),
                   value=value, display_value=display, unit='percent', basis=BASIS,
                   url=scheduled['url'], title=parser.title, source_locator='First paragraph of News Release',
                   captured_at=captured_at)
    if table_value is not None:
        release['table_source_locator'] = 'Real GDP and Related Measures · current-stage Real GDP cell'
    gdi = _gdi(parser.paragraphs, quarter)
    if gdi is not None:
        release['gdi_value'] = gdi
        release['gdi_source_locator'] = 'News Release body · Real gross domestic income paragraph'
    note = _revision_note(parser.paragraphs)
    if note:
        release['revision_note'] = note
        release['revision_note_locator'] = 'News Release body / Technical Notes'
    return release


def _fetch(url):
    version = (ROOT / 'VERSION').read_text().strip()
    run = subprocess.run(['curl', '--http1.1', '--fail', '--location', '--silent', '--show-error',
                          '--max-time', '40', '--user-agent',
                          f'PublicRecord/{version} (+https://github.com/AustinMermans/public-record)', url],
                         capture_output=True, timeout=50)
    require(run.returncode == 0 and run.stdout, 'BEA request failed')
    return run.stdout


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
        temporary = Path(handle.name)
    temporary.replace(path)


def _store_raw(data_dir, body, suffix):
    digest = hashlib.sha256(body).hexdigest()
    path = data_dir / 'raw' / f'{digest}.{suffix}'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(body)
    # In the repository, evidence paths are repository-relative like other
    # collectors. Disposable test captures keep paths relative to their root.
    root = data_dir.parent.parent if data_dir.parent.name == 'data' else data_dir.parent
    return digest, str(path.relative_to(root))


def validate_capture(bundle, root=ROOT):
    require(bundle.get('schema_version') == 1 and bundle.get('source_id') == 'bea-gdp-releases',
            'Invalid BEA capture identity')
    require(bundle.get('status') in ('ok', 'stale', 'unavailable'), 'Invalid BEA status')
    if bundle['status'] == 'unavailable':
        require(not bundle.get('releases'), 'Unavailable BEA capture has release values')
        return
    captured = datetime.fromisoformat(bundle['captured_at'].replace('Z', '+00:00'))
    attempted = datetime.fromisoformat(bundle['attempted_at'].replace('Z', '+00:00'))
    require(captured.tzinfo is not None and attempted.tzinfo is not None and captured <= attempted,
            'Invalid BEA capture/attempt clocks')
    schedule = bundle['schedule']
    require(schedule['url'] == SCHEDULE_URL and schedule['captured_at'] == bundle['captured_at'],
            'Invalid BEA schedule receipt')
    if root is not None:
        schedule_bytes = (root / schedule['raw_path']).read_bytes()
        require(hashlib.sha256(schedule_bytes).hexdigest() == schedule['sha256'],
                'BEA schedule raw hash mismatch')
    keys = set()
    for row in bundle['releases']:
        key = (row['quarter'], row['stage'])
        require(key not in keys and row['quarter'] >= '2025Q4' and row['stage'] in STAGES,
                'Duplicate or invalid BEA release stage')
        keys.add(key)
        require(row['unit'] == 'percent' and row['basis'] == BASIS
                and isinstance(row['value'], (int, float)) and math.isfinite(row['value'])
                and isinstance(row['display_value'], str)
                and re.fullmatch(r'-?\d{1,2}(?:\.\d+)?', row['display_value'])
                and float(row['display_value']) == row['value'],
                'Invalid BEA release value/basis')
        require(row['published_at'] <= bundle['captured_at'][:10]
                and row['captured_at'] <= bundle['captured_at'], 'Future BEA release')
        _official_url(row['url'])
        if root is not None:
            body = (root / row['raw_path']).read_bytes()
            require(hashlib.sha256(body).hexdigest() == row['sha256'],
                    'BEA release raw hash mismatch')
            evidence = parse_release(body, dict(quarter=row['quarter'], stage=row['stage'],
                                                date=row['published_at'], title=row['title'], url=row['url']),
                                     row['captured_at'])
            require(all(row.get(field) == evidence.get(field) for field in
                        ('value', 'display_value', 'published_at', 'source_locator', 'table_source_locator',
                         'gdi_value', 'revision_note')),
                    'BEA release differs from retained source bytes')
    for row in bundle['scheduled']:
        require((row['quarter'], row['stage']) not in keys and row['stage'] in STAGES,
                'Scheduled BEA row duplicates a published release')


def collect(data_dir=DATA, fetch=_fetch, captured_at=None):
    """Refresh linked BEA releases; retain the last good capture on any failure."""
    stamp = captured_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
    now = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    require(now.tzinfo is not None, 'BEA capture requires timezone-aware clock')
    current = data_dir / 'current.json'
    previous = json.loads(current.read_text()) if current.exists() else None
    try:
        schedule_bytes = fetch(SCHEDULE_URL)
        schedule_rows = parse_schedule(schedule_bytes)
        schedule_sha, schedule_path = _store_raw(data_dir, schedule_bytes, 'html')
        retained = {(r['quarter'], r['stage']): r for r in previous.get('releases', [])} if previous and previous.get('status') != 'unavailable' else {}
        scheduled = []
        for row in schedule_rows:
            key = (row['quarter'], row['stage'])
            if key in retained:
                require(not row['url'] or row['url'] == retained[key]['url'],
                        'BEA schedule link changed for retained release')
                continue
            if not row['url'] or row['date'] > now.date().isoformat():
                scheduled.append({key: row[key] for key in ('quarter', 'stage', 'date', 'title')})
                continue
            body = fetch(row['url'])
            release = parse_release(body, row, stamp)
            digest, path = _store_raw(data_dir, body, 'html')
            release.update(sha256=digest, raw_path=path)
            retained[key] = release
        require(retained, 'No verified BEA GDP news releases yet')
        bundle = dict(schema_version=1, source_id='bea-gdp-releases', publisher=SOURCE,
                      status='ok', captured_at=stamp, last_success=stamp, attempted_at=stamp,
                      error=None, schedule=dict(url=SCHEDULE_URL, sha256=schedule_sha,
                                                raw_path=schedule_path, captured_at=stamp),
                      releases=sorted(retained.values(), key=lambda r: (r['quarter'], STAGES[r['stage']])),
                      scheduled=scheduled,
                      scope='Published BEA real GDP stage estimates from 2025Q4 forward; not a complete historical vintage archive.')
        bundle['changes'] = compare_bea_releases(previous, bundle)
        evidence_root = data_dir.parent.parent if data_dir.parent.name == 'data' else data_dir.parent
        validate_capture(bundle, evidence_root)
        _write_json(current, bundle)
        return bundle
    except (BEAError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        error = _clean(str(exc))[:240] or type(exc).__name__
        if previous and previous.get('status') != 'unavailable':
            bundle = copy.deepcopy(previous)
            bundle.update(status='stale', attempted_at=stamp, error=error)
        else:
            bundle = dict(schema_version=1, source_id='bea-gdp-releases', publisher=SOURCE,
                          status='unavailable', captured_at=None, last_success=None,
                          attempted_at=stamp, error=error, schedule=None, releases=[], scheduled=[])
        bundle['changes'] = compare_bea_releases(previous, bundle)
        _write_json(current, bundle)
        return bundle


if __name__ == '__main__':
    print(json.dumps(collect(), indent=2, sort_keys=True))
