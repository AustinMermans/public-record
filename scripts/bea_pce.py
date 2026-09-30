"""Source-bound BEA Personal Income and Outlays PCE price release collector.

The full release schedule is discovery only. A monthly observation requires its
dated View link, matching canonical news page, elapsed embargo, and four rates
in the release body's two PCE price-index paragraphs. Retained HTML is replayed
when validating a capture; interactive data tables are never substituted.
"""

import copy
import hashlib
import json
import math
import re
import subprocess
import tempfile
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'bea_pce'
SCHEDULE_URL = 'https://www.bea.gov/news/schedule/full'
SOURCE_ID = 'bea-pce-releases'
PUBLISHER = 'U.S. Bureau of Economic Analysis'
MONTHS = {name: number for number, name in enumerate(
    ('', 'January', 'February', 'March', 'April', 'May', 'June',
     'July', 'August', 'September', 'October', 'November', 'December')) if number}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'link', 'meta', 'param', 'source', 'track', 'wbr'}
FIELDS = ('headline_mom', 'core_mom', 'headline_yoy', 'core_yoy')


class BEAPCEError(ValueError):
    """A BEA source, publication boundary, or rate cannot be verified."""


def require(condition, message):
    if not condition:
        raise BEAPCEError(message)


def clean(text):
    return re.sub(r'\s+([.,;:])', r'\1', re.sub(r'\s+', ' ', text)).strip()


def _decode(body, kind):
    require(isinstance(body, bytes) and 100 < len(body) <= 5_000_000,
            f'Missing or oversized BEA {kind} HTML')
    try:
        return body.decode('utf-8-sig')
    except UnicodeError as exc:
        raise BEAPCEError(f'BEA {kind} is not UTF-8') from exc


def _target(title):
    match = re.fullmatch(r'Personal Income and Outlays, ([A-Z][a-z]+) (20\d{2})', title)
    require(match is not None and match.group(1) in MONTHS,
            'Not a single-month Personal Income and Outlays title')
    return f'{match.group(2)}-{MONTHS[match.group(1)]:02d}', match.group(1)


def _official_url(path):
    url = urljoin('https://www.bea.gov', path)
    parsed = urlparse(url)
    require(parsed.scheme == 'https' and parsed.netloc == 'www.bea.gov'
            and re.fullmatch(r'/news/20\d{2}/personal-income-and-outlays-[a-z]+-20\d{2}', parsed.path)
            and not parsed.query and not parsed.fragment,
            'PCE release link is not a canonical single-month BEA news URL')
    return url


class _ScheduleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        classes = props.get('class', '').split()
        if tag == 'tr' and 'scheduled-releases-type-press' in classes:
            require(self.row is None, 'Nested BEA schedule row')
            self.row = {}
        elif self.row is not None:
            if tag == 'td' and self.cell is None:
                self.cell = {'class': classes, 'text': '', 'hrefs': []}
                self.depth = 1
            elif self.cell is not None and tag not in VOID:
                self.depth += 1
                if tag == 'a' and props.get('href'):
                    self.cell['hrefs'].append(props['href'])

    def handle_data(self, data):
        if self.cell is not None:
            self.cell['text'] += data + ' '

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.cell is not None:
            self.depth -= 1
            if tag == 'td' and self.depth == 0:
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


def parse_schedule(body):
    html = _decode(body, 'schedule')
    require('Release Schedule' in html and 'scheduled-releases-type-press' in html,
            'BEA full schedule structure missing')
    parser = _ScheduleHTML()
    parser.feed(html)
    require(parser.rows and parser.row is None and parser.cell is None,
            'Incomplete BEA schedule table')
    output = []
    for row in parser.rows:
        title = clean(row.get('title', {}).get('text', ''))
        if not title.startswith('Personal Income and Outlays, '):
            continue
        # Combined and annual releases have no single target month. They are
        # deliberately excluded, including October and November 2025.
        if title == 'Personal Income and Outlays, October and November 2025':
            continue
        require(re.fullmatch(r'Personal Income and Outlays, [A-Z][a-z]+ 20\d{2}', title),
                'Changed or combined BEA PCE schedule title')
        target, _ = _target(title)
        if target < '2026-01':
            continue
        require({'date', 'title', 'url'} <= row.keys(), 'Incomplete BEA PCE schedule row')
        date_match = re.fullmatch(r'([A-Z][a-z]+) (\d{1,2}) (?:\d{1,2}:\d{2} [AP]M)?',
                                  clean(row['date']['text']))
        require(date_match is not None and date_match.group(1) in MONTHS,
                'Invalid BEA PCE schedule date')
        try:
            stamp = date(int(target[:4]), MONTHS[date_match.group(1)], int(date_match.group(2)))
            # A December observation normally publishes in the following year.
            if stamp.month < int(target[5:]):
                stamp = stamp.replace(year=stamp.year + 1)
        except ValueError as exc:
            raise BEAPCEError('Invalid BEA PCE schedule date') from exc
        hrefs = row['url']['hrefs']
        require(len(hrefs) <= 1, 'Ambiguous BEA PCE release link')
        url = _official_url(hrefs[0]) if hrefs else None
        if url:
            require(urlparse(url).path.split('/')[2] == str(stamp.year),
                    'BEA schedule link publication year differs from date')
            require(url.endswith(f'personal-income-and-outlays-{MONTH_NAMES[int(target[5:])]}-{target[:4]}'),
                    'BEA schedule link target differs from row title')
        output.append(dict(target=target, date=stamp.isoformat(), title=title, url=url))
    require(output, 'No 2026-or-later monthly PCE rows in BEA full schedule')
    targets = [row['target'] for row in output]
    require(len(targets) == len(set(targets)), 'Duplicate BEA PCE schedule month')
    return sorted(output, key=lambda row: row['target'])


MONTH_NAMES = {number: name.lower() for name, number in MONTHS.items()}


class _ReleaseHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
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
        if tag == 'link' and props.get('rel') == 'canonical':
            self.canonical = props.get('href')
        if tag == 'h1' and self._h1 is None:
            self._h1 = ''
        if 'field--name-field-release-date' in classes:
            self._embargo = ''
        if 'release-body' in classes and not self._body_depth:
            self._body_depth = 1
        elif self._body_depth and tag not in VOID:
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
        if tag in VOID:
            return
        if tag == 'h1' and self._h1 is not None:
            if self.title is None and self._h1.strip().startswith('Personal Income and Outlays, '):
                self.title = clean(self._h1)
            self._h1 = None
        if tag == 'div' and self._embargo is not None:
            self.embargo = clean(self._embargo)
            self._embargo = None
        if self._body_depth:
            if tag == 'p' and self._p is not None and self._p_depth == self._body_depth:
                self.paragraphs.append(clean(self._p))
                self._p = None
            self._body_depth -= 1


def _embargo_time(text):
    match = re.fullmatch(
        r'EMBARGOED UNTIL RELEASE AT (\d{1,2}):(\d{2}) a\.m\. (EDT|EST), '
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),? '
        r'([A-Z][a-z]+) (\d{1,2}), (20\d{2})', text, re.I)
    require(match is not None and match.group(5) in MONTHS,
            'BEA PCE release has no verifiable embargo timestamp')
    offset = -4 if match.group(3) == 'EDT' else -5
    try:
        local = datetime(int(match.group(7)), MONTHS[match.group(5)], int(match.group(6)),
                         int(match.group(1)), int(match.group(2)),
                         tzinfo=timezone(timedelta(hours=offset)))
    except ValueError as exc:
        raise BEAPCEError('Invalid BEA PCE embargo date') from exc
    require(local.strftime('%A').lower() == match.group(4).lower(),
            'BEA PCE embargo weekday mismatch')
    return local.astimezone(timezone.utc)


RATE = r'(\d{1,2}(?:\.\d+)?)'


def _rate(verb, number):
    value = float(number) * (-1 if verb == 'decreased' else 1)
    require(math.isfinite(value) and abs(value) < 100, 'Invalid BEA PCE price rate')
    return value, ('-' if value < 0 else '') + number


def _paragraph_values(paragraph, month, period):
    prefix = (r'From the preceding month, the PCE price index for ' if period == 'mom'
              else r'From the same month one year ago, the PCE price index for ')
    start = re.compile(r'^' + prefix + re.escape(month) + r' (increased|decreased) ' + RATE +
                       r' percent\. Excluding food and energy, the PCE price index '
                       r'(?:also )?(increased|decreased) ' + RATE +
                       (r' percent\.' if period == 'mom' else r' percent from one year ago\.'), re.I)
    match = start.fullmatch(paragraph)
    require(match is not None, f'Missing or changed BEA PCE {period} price paragraph')
    return _rate(match.group(1).lower(), match.group(2)), _rate(match.group(3).lower(), match.group(4))


def parse_release(body, scheduled, captured_at):
    html = _decode(body, 'release')
    parser = _ReleaseHTML()
    parser.feed(html)
    require(parser.title and parser.embargo and parser.paragraphs,
            'BEA PCE release structure missing')
    require(parser.canonical == scheduled['url'],
            'BEA PCE canonical URL differs from schedule View link')
    target, month = _target(parser.title)
    require(target == scheduled['target'] and parser.title == scheduled['title'],
            'BEA PCE release title differs from schedule')
    embargo = _embargo_time(parser.embargo)
    now = datetime.fromisoformat(captured_at.replace('Z', '+00:00'))
    require(now.tzinfo is not None and embargo <= now,
            'BEA PCE embargo has not elapsed')
    require(embargo.date().isoformat() == scheduled['date'],
            'BEA PCE publication date differs from schedule')
    found = {}
    locators = {}
    for index, paragraph in enumerate(parser.paragraphs, 1):
        for period, marker in (('mom', 'From the preceding month, the PCE price index'),
                               ('yoy', 'From the same month one year ago, the PCE price index')):
            if paragraph.startswith(marker):
                require(period not in found, f'Duplicate BEA PCE {period} price paragraph')
                found[period] = _paragraph_values(paragraph, month, period)
                locators[period] = f'News Release body, paragraph {index}'
    require(set(found) == {'mom', 'yoy'}, 'Missing BEA PCE monthly or annual price paragraph')
    display = {f'headline_{period}': found[period][0][1] for period in ('mom', 'yoy')}
    display.update({f'core_{period}': found[period][1][1] for period in ('mom', 'yoy')})
    values = {key: float(display[key]) for key in FIELDS}
    return dict(target=target, published_at=embargo.date().isoformat(),
                embargo_at=embargo.isoformat(timespec='minutes'), values=values,
                display_values=display, unit='percent', title=parser.title,
                source_locator=locators, url=scheduled['url'], captured_at=captured_at)


def _fetch(url):
    version = (ROOT / 'VERSION').read_text().strip()
    run = subprocess.run(['curl', '--http1.1', '--fail', '--location', '--silent',
                          '--show-error', '--max-time', '40', '--user-agent',
                          f'PublicRecord/{version} (+https://github.com/AustinMermans/public-record)', url],
                         capture_output=True, timeout=50)
    require(run.returncode == 0 and run.stdout, 'BEA PCE request failed')
    return run.stdout


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
        temporary = Path(handle.name)
    temporary.replace(path)


def _store_raw(data_dir, body):
    digest = hashlib.sha256(body).hexdigest()
    path = data_dir / 'raw' / f'{digest}.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(body)
    root = data_dir.parent.parent if data_dir.parent.name == 'data' else data_dir.parent
    return digest, str(path.relative_to(root))


def _raw(root, path, digest):
    require(re.fullmatch(r'data/bea_pce/raw/[0-9a-f]{64}\.html', path)
            or re.fullmatch(r'bea_pce/raw/[0-9a-f]{64}\.html', path),
            'Invalid BEA PCE raw evidence path')
    body = (root / path).read_bytes()
    require(hashlib.sha256(body).hexdigest() == digest and path.endswith(f'{digest}.html'),
            'BEA PCE raw evidence hash mismatch')
    return body


def validate_capture(bundle, root=ROOT):
    require(bundle.get('schema_version') == 1 and bundle.get('source_id') == SOURCE_ID,
            'Invalid BEA PCE capture identity')
    require(bundle.get('status') in ('ok', 'stale', 'unavailable'), 'Invalid BEA PCE status')
    attempted = datetime.fromisoformat(bundle['attempted_at'].replace('Z', '+00:00'))
    require(attempted.tzinfo is not None, 'Invalid BEA PCE attempt clock')
    if bundle['status'] == 'unavailable':
        require(bundle.get('captured_at') is None and not bundle.get('releases'),
                'Unavailable BEA PCE capture has actual values')
        if 'changes' in bundle:
            changes = bundle['changes']
            require(changes.get('items') == [] and changes.get('baselines') == []
                    and changes.get('skipped') == [SOURCE_ID]
                    and len(changes.get('channels', [])) == 1
                    and changes['channels'][0].get('id') == SOURCE_ID
                    and changes['channels'][0].get('status') == 'unavailable'
                    and changes['channels'][0].get('to_capture') is None,
                    'Unavailable BEA PCE capture claims a change')
        return
    captured = datetime.fromisoformat(bundle['captured_at'].replace('Z', '+00:00'))
    require(captured.tzinfo is not None and captured <= attempted,
            'Invalid BEA PCE capture/attempt clocks')
    schedule = bundle['schedule']
    require(schedule['url'] == SCHEDULE_URL and schedule['captured_at'] == bundle['captured_at'],
            'Invalid BEA PCE schedule receipt')
    rows = parse_schedule(_raw(root, schedule['raw_path'], schedule['sha256'])) if root else None
    indexed = {row['target']: row for row in rows} if rows else {}
    discoveries = bundle.get('discovery_schedules', [])
    require(isinstance(discoveries, list), 'Invalid BEA PCE discovery schedules')
    discovered = {}
    if root:
        for receipt in discoveries:
            require(receipt['url'] == SCHEDULE_URL
                    and receipt['sha256'] not in discovered
                    and receipt['captured_at'] <= bundle['captured_at'],
                    'Invalid or duplicate BEA PCE discovery schedule')
            discovered[receipt['sha256']] = {
                row['target']: row for row in parse_schedule(
                    _raw(root, receipt['raw_path'], receipt['sha256']))}
    targets = set()
    for release in bundle['releases']:
        target = release['target']
        require(target not in targets and target >= '2026-01', 'Duplicate or invalid BEA PCE target')
        targets.add(target)
        require(release['unit'] == 'percent' and set(release['values']) == set(FIELDS)
                and set(release['display_values']) == set(FIELDS), 'Invalid BEA PCE values')
        require(all(isinstance(release['values'][key], (int, float))
                    and math.isfinite(release['values'][key])
                    and release['values'][key] == float(release['display_values'][key])
                    for key in FIELDS), 'Invalid BEA PCE rate/display reconciliation')
        require(release['published_at'] <= bundle['captured_at'][:10]
                and release['captured_at'] <= bundle['captured_at'], 'Future BEA PCE release')
        require(_official_url(release['url']) == release['url'], 'Invalid BEA PCE URL')
        if root:
            discovery_sha = release['discovery_schedule_sha256']
            require(discovery_sha in discovered and target in discovered[discovery_sha],
                    'BEA PCE release missing original discovery schedule')
            discovery_row = discovered[discovery_sha][target]
            require(discovery_row['url'] == release['url'],
                    'BEA PCE release differs from discovery schedule View link')
            if target in indexed:
                require(indexed[target]['url'] == release['url'],
                        'BEA PCE live schedule link changed for retained release')
            body = _raw(root, release['raw_path'], release['sha256'])
            replay = parse_release(body, discovery_row, release['captured_at'])
            require(all(release.get(key) == replay.get(key) for key in replay),
                    'BEA PCE release differs from retained source bytes')
    for row in bundle['scheduled']:
        require(row['target'] not in targets, 'Scheduled BEA PCE month duplicates an actual')
        if root:
            require(row['target'] in indexed, 'Unknown scheduled BEA PCE month')
            require(row == {key: indexed[row['target']][key] for key in ('target', 'date', 'title')},
                    'Scheduled BEA PCE row differs from captured schedule')
            require(not indexed[row['target']]['url']
                    or indexed[row['target']]['date'] > captured.date().isoformat(),
                    'Linked published BEA PCE month left scheduled')
    if root:
        require((targets & set(indexed)) | {row['target'] for row in bundle['scheduled']} == set(indexed),
                'BEA PCE capture omits schedule month')
        require(set(discovered) == {row['discovery_schedule_sha256'] for row in bundle['releases']},
                'Unused or missing BEA PCE discovery schedule')
    if 'changes' in bundle:
        changes = bundle['changes']
        require(isinstance(changes, dict) and len(changes.get('channels', [])) == 1,
                'Invalid BEA PCE change receipt')
        channel = changes['channels'][0]
        require(channel.get('id') == SOURCE_ID
                and channel.get('label') == 'BEA · dated PCE price releases'
                and channel.get('to_capture') == bundle.get('captured_at'),
                'BEA PCE change channel differs from capture')
        status = channel.get('status')
        items = changes.get('items')
        require(isinstance(items, list), 'Invalid BEA PCE change items')
        if bundle['status'] != 'ok':
            require(status == 'unavailable' and not items
                    and changes.get('skipped') == [SOURCE_ID]
                    and changes.get('baselines') == [],
                    'Unavailable BEA PCE capture claims a change')
        elif status == 'baseline':
            require(not items and changes.get('baselines') == [SOURCE_ID]
                    and changes.get('skipped') == []
                    and channel.get('from_capture') is None,
                    'BEA PCE baseline claims a release change')
        else:
            require(status == 'compared' and changes.get('baselines') == []
                    and changes.get('skipped') == []
                    and isinstance(channel.get('from_capture'), str)
                    and channel['from_capture'] < bundle['captured_at'],
                    'Invalid BEA PCE compared channel')
            by_target = {row['target']: row for row in bundle['releases']}
            require(len(items) == len({item.get('target') for item in items}),
                    'Duplicate BEA PCE change target')
            for item in items:
                target = item.get('target')
                require(target in by_target
                        and by_target[target]['captured_at'] > channel['from_capture']
                        and item == _change_item(
                    by_target[target], channel['from_capture'], bundle['captured_at']),
                    'BEA PCE change item differs from verified release')


def _change_item(row, from_capture, to_capture):
    return dict(
        source_id=SOURCE_ID, publisher=PUBLISHER, kind='Newly captured PCE release',
        title=f"BEA PCE prices · {row['target']}", date=row['published_at'],
        published_at=row['published_at'], target=row['target'],
        unit='Percent · monthly and year over year', before=None,
        after=copy.deepcopy(row['values']), url=row['url'],
        source_locator=copy.deepcopy(row['source_locator']),
        summary='Dated official Personal Income and Outlays release; four published price-index rates for the target month, not revisions to an older release.',
        from_capture=from_capture, to_capture=to_capture)


def compare_bea_pce(previous, current):
    """Emit a change only when a target first becomes a verified actual."""
    old = previous if previous and previous.get('status') in ('ok', 'stale') else None
    channel = dict(id=SOURCE_ID, label='BEA · dated PCE price releases',
                   from_capture=(old or {}).get('captured_at'),
                   to_capture=current.get('captured_at'))
    result = dict(items=[], channels=[channel], baselines=[], skipped=[])
    if current.get('status') != 'ok' or not current.get('captured_at'):
        channel.update(status='unavailable',
                       error='BEA PCE release check failed; retained values are not a new comparison.')
        result['skipped'].append(SOURCE_ID)
        return result
    if not old or not old.get('releases'):
        channel['status'] = 'baseline'
        result['baselines'].append(SOURCE_ID)
        return result
    channel['status'] = 'compared'
    before = {row['target']: row for row in old['releases']}
    for row in current['releases']:
        if row['target'] in before:
            require(row == before[row['target']],
                    'Previously captured BEA PCE actual changed')
            continue
        result['items'].append(_change_item(row, old['captured_at'], current['captured_at']))
    return result


def collect(data_dir=DATA, fetch=_fetch, captured_at=None):
    """Refresh verified releases, retaining the last good capture on failure."""
    stamp = captured_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
    now = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    require(now.tzinfo is not None, 'BEA PCE capture requires timezone-aware clock')
    current = data_dir / 'current.json'
    previous = json.loads(current.read_text()) if current.exists() else None
    evidence_root = data_dir.parent.parent if data_dir.parent.name == 'data' else data_dir.parent
    try:
        if previous:
            validate_capture(previous, evidence_root)
        schedule_body = fetch(SCHEDULE_URL)
        rows = parse_schedule(schedule_body)
        schedule_sha, schedule_path = _store_raw(data_dir, schedule_body)
        schedule_receipt = dict(url=SCHEDULE_URL, sha256=schedule_sha,
                                raw_path=schedule_path, captured_at=stamp)
        retained = {r['target']: r for r in previous['releases']} if previous and previous['status'] != 'unavailable' else {}
        discoveries = copy.deepcopy(previous['discovery_schedules']) if retained else []
        scheduled = []
        for row in rows:
            target = row['target']
            if target in retained:
                require(row['url'] == retained[target]['url'],
                        'BEA PCE schedule link changed for retained release')
                continue
            if not row['url'] or row['date'] > now.date().isoformat():
                scheduled.append({key: row[key] for key in ('target', 'date', 'title')})
                continue
            body = fetch(row['url'])
            release = parse_release(body, row, stamp)
            digest, path = _store_raw(data_dir, body)
            release.update(sha256=digest, raw_path=path,
                           discovery_schedule_sha256=schedule_sha)
            retained[target] = release
            if schedule_sha not in {item['sha256'] for item in discoveries}:
                discoveries.append(schedule_receipt)
        require(retained, 'No verified BEA PCE news releases yet')
        bundle = dict(schema_version=1, source_id=SOURCE_ID, publisher=PUBLISHER,
                      status='ok', captured_at=stamp, attempted_at=stamp,
                      last_success=stamp, error=None,
                      schedule=schedule_receipt, discovery_schedules=discoveries,
                      releases=sorted(retained.values(), key=lambda r: r['target']),
                      scheduled=scheduled,
                      scope='Single-month published BEA PCE price release readings from January 2026 forward; not a complete historical vintage archive.')
        validate_capture(bundle, evidence_root)
        bundle['changes'] = compare_bea_pce(previous, bundle)
        _write_json(current, bundle)
        return bundle
    except (BEAPCEError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        error = clean(str(exc))[:240] or type(exc).__name__
        if previous and previous.get('status') != 'unavailable':
            bundle = copy.deepcopy(previous)
            bundle.update(status='stale', attempted_at=stamp, error=error)
        else:
            bundle = dict(schema_version=1, source_id=SOURCE_ID, publisher=PUBLISHER,
                          status='unavailable', captured_at=None, attempted_at=stamp,
                          last_success=None, error=error, schedule=None,
                          discovery_schedules=[], releases=[], scheduled=[])
        bundle['changes'] = compare_bea_pce(previous, bundle)
        _write_json(current, bundle)
        return bundle


if __name__ == '__main__':
    print(json.dumps(collect(), indent=2, sort_keys=True))
