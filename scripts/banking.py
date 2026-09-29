"""FDIC QBP published institution aggregates, read from retained XLSX evidence."""
import calendar
import copy
import hashlib
import io
import json
import posixpath
import re
import subprocess
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/banking'
LANDING = 'https://www.fdic.gov/quarterly-banking-profile'
SOURCE_ID = 'fdic-qbp'
PUBLISHER = 'FDIC · Quarterly Banking Profile'
POPULATION = 'All Insured Institutions'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


class BankingError(ValueError):
    """Controlled public-safe source or validation error."""


def require(condition, message):
    if not condition:
        raise BankingError(message)


def quarter_end(year, quarter):
    month = quarter * 3
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.links = []; self.feed(text)

    def handle_starttag(self, tag, attributes):
        if tag == 'a':
            href = dict(attributes).get('href')
            if href:
                self.links.append(href)


def discover_edition(body, captured_at):
    candidates = {}
    for href in Links(body.decode('utf-8')).links:
        url = urljoin(LANDING, href).split('#')[0]
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'www.fdic.gov':
            continue
        match = re.fullmatch(r'/quarterly-banking-profile/quarterly-banking-profile-(?:([1-4])q|q([1-4]))-(20\d{2})', parsed.path)
        if match:
            year, quarter = int(match[3]), int(match[1] or match[2])
            end = quarter_end(year, quarter)
            if end <= captured_at[:10]:
                candidates[end] = dict(year=year, quarter=quarter, quarter_end=end,
                    edition=f'{year} Q{quarter}', edition_url=url)
    require(candidates, 'No recognized current FDIC QBP edition link')
    return candidates[max(candidates)]


def discover_workbook(body, edition):
    matches = set()
    words = ['first', 'second', 'third', 'fourth']
    expected = '/quarterly-banking-profile/qbp-time-series-spreadsheets-'+words[edition['quarter']-1]+'-quarter-'+str(edition['year'])+'.xlsx'
    for href in Links(body.decode('utf-8')).links:
        url = urljoin(edition['edition_url'], href)
        p = urlparse(url)
        if p.scheme == 'https' and p.netloc == 'www.fdic.gov' and p.path == expected and not p.query:
            matches.add(url.split('#')[0])
    require(len(matches) == 1, 'Missing or ambiguous FDIC edition time-series workbook')
    return matches.pop()


def discover_notes(body,edition):
    word=['first','second','third','fourth'][edition['quarter']-1]
    expected=f'/quarterly-banking-profile/qbp-notes-users-{word}-quarter-{edition["year"]}.pdf'
    matches={urljoin(edition['edition_url'],href).split('#')[0] for href in Links(body.decode('utf-8')).links
             if urlparse(urljoin(edition['edition_url'],href)).path==expected}
    require(len(matches)==1 and next(iter(matches)).startswith('https://www.fdic.gov/'), 'Missing or ambiguous edition-specific FDIC notes')
    return matches.pop()


def fetch(url, data_dir, stamp, extension):
    p = subprocess.run(['curl','--http1.1','--fail','--silent','--show-error','--location','--max-time','40',
        '--user-agent','PublicRecord/1.7 github.com/AustinMermans/public-record',url],capture_output=True,timeout=50)
    require(p.returncode == 0, 'FDIC request failed (HTTP or network error)')
    require(len(p.stdout) <= 20_000_000, 'FDIC response exceeds bounded source size')
    digest = hashlib.sha256(p.stdout).hexdigest()
    path = data_dir/'raw'/(digest+'.'+extension); path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists(): path.write_bytes(p.stdout)
    try: relative = str(path.relative_to(ROOT))
    except ValueError: relative = str(path)
    return p.stdout, dict(url=url,sha256=digest,raw_path=relative,captured_at=stamp)


def read_xlsx(body, selected=None):
    """Read only stored cell values; never evaluate formulas or follow links."""
    require(body.startswith(b'PK'), 'FDIC response is not an XLSX workbook')
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        require(len(archive.infolist()) <= 200 and sum(i.file_size for i in archive.infolist()) < 100_000_000,
                'Workbook exceeds bounded ZIP structure')
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            strings = [''.join(node.itertext()) if not node.findall('.//s:t', NS)
                       else ''.join(t.text or '' for t in node.findall('.//s:t', NS))
                       for node in root.findall('s:si', NS)]
        relations = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        targets = {}
        for relation in relations:
            require(relation.get('TargetMode') != 'External', 'External workbook relationship unsupported')
            target = relation.get('Target', '')
            targets[relation.get('Id')] = posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/'+target)
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        styles = ET.fromstring(archive.read('xl/styles.xml'))
        formats = {'0':'General','1':'0','2':'0.00','3':'#,##0','4':'#,##0.00',
                   '9':'0%','10':'0.00%','37':'#,##0 ;(#,##0)'}
        formats.update({x.get('numFmtId'):x.get('formatCode') for x in styles.findall('s:numFmts/s:numFmt', NS)})
        cell_formats = [formats.get(x.get('numFmtId'), 'unsupported') for x in styles.findall('s:cellXfs/s:xf', NS)]
        selected = selected or {'Ratios by Asset Size Groups', 'Balance Sheet', 'Quarterly Income'}
        result = {}
        for sheet in workbook.findall('s:sheets/s:sheet', NS):
            name = sheet.get('name'); target = targets[sheet.get('{'+REL+'}id')]
            if name not in selected:
                continue
            require(name not in result and target.startswith('xl/'), 'Duplicate or unsafe workbook sheet')
            root = ET.fromstring(archive.read(target)); cells = {}
            for cell in root.findall('.//s:sheetData/s:row/s:c', NS):
                address = cell.get('r')
                require(address not in cells and re.fullmatch(r'[A-Z]+[1-9]\d*', address or ''), 'Duplicate or missing spreadsheet cell address')
                kind = cell.get('t', 'n'); value = cell.findtext('s:v', default=None, namespaces=NS)
                if kind == 's':
                    value = strings[int(value)]
                elif kind == 'inlineStr':
                    value = ''.join(t.text or '' for t in cell.findall('.//s:t', NS))
                formula = cell.findtext('s:f',default=None,namespaces=NS)
                if value is not None or formula is not None:
                    cells[address] = dict(value=value, type=kind, formula=formula,
                        number_format=cell_formats[int(cell.get('s','0'))])
            result[name] = cells
        require(set(result) == set(selected), 'Required FDIC semantic sheets missing')
        return result


RATIO_SHEET = 'Ratios by Asset Size Groups'
BS_TITLE = 'Assets and Liabilities of FDIC-Insured Commercial Banks and Savings Institutions'
INCOME_TITLE = 'Quarterly Income and Expense of FDIC-Insured Commercial Banks and Savings Institutions'
SPECS = [
    dict(id='noncurrent',label='Noncurrent loans / loans',sheet=RATIO_SHEET,
         row_label='Percent of Loans and Leases Noncurrent',unit='Percent',annualized=False,
         stock_flow='Quarter-end stock ratio',definition='Loans and leases 90 days or more past due plus nonaccrual, as a percentage of loans and leases.'),
    dict(id='nco',label='Net charge-off rate',sheet=RATIO_SHEET,
         row_label='Quarterly Net Charge-Offs to Loans and Leases',unit='Percent',annualized=True,
         stock_flow='Annualized quarterly performance ratio',definition='Published annualized quarterly net charge-offs divided by average loans and leases; not a ratio of quarter-end balances.'),
    dict(id='coverage',label='Allowance / noncurrent loans',sheet=RATIO_SHEET,
         row_label='Loss Allowance to Noncurrent Loans and Leases (Coverage Ratio)',unit='Percent',annualized=False,
         stock_flow='Quarter-end stock ratio',definition='Allowance for losses as a percentage of noncurrent loans and leases.'),
    dict(id='roa',label='Return on assets',sheet=RATIO_SHEET,
         row_label='Quarterly Return on Assets',unit='Percent',annualized=True,
         stock_flow='Annualized quarterly performance ratio',definition='Published annualized quarterly return on average assets; not net income divided by quarter-end assets.'),
    dict(id='equity_assets',label='Bank equity / assets',sheet=RATIO_SHEET,
         row_label='Equity Capital to Assets',unit='Percent',annualized=False,
         stock_flow='Quarter-end stock ratio',definition='Bank equity capital excluding noncontrolling interests as a percentage of assets; not a regulatory capital ratio.'),
    dict(id='deposits',label='Deposits',sheet='Balance Sheet',row_label='Deposits',unit='USD millions',annualized=False,
         stock_flow='Quarter-end stock',definition='FDIC-reported aggregate domestic and foreign-office deposits.'),
    dict(id='institutions',label='Reporting institutions',sheet='Balance Sheet',row_label='Number of institutions reporting',unit='Count',annualized=False,
         stock_flow='Quarter-end count',definition='Number of FDIC-insured commercial banks and savings institutions reporting.'),
    dict(id='assets',label='Assets',sheet='Balance Sheet',row_label='Total Assets',unit='USD millions',annualized=False,
         stock_flow='Quarter-end stock',definition='FDIC-reported aggregate assets, not bank holding-company assets.'),
    dict(id='net_income',label='Quarterly net income attributable to banks',sheet='Quarterly Income',row_label='Net income (loss) attributable to bank',unit='USD millions',annualized=False,
         stock_flow='Quarter flow',definition='Quarterly net income attributable to banks, excluding noncontrolling interests; not annual or year-to-date income.')]
SUPPORT = {
    'loans': ('Balance Sheet','Total loans and leases'),
    'allowance': ('Balance Sheet','Less: Reserve for losses'),
    'past_due90': ('Balance Sheet','Loans and leases 90 days or more past due'),
    'nonaccrual': ('Balance Sheet','Loans and leases in nonaccrual status'),
    'bank_equity': ('Balance Sheet','Total bank equity capital'),
    'inclusive_equity': ('Balance Sheet','Total equity capital'),
    'liabilities': ('Balance Sheet','Total liabilities'),
    'income_nci': ('Quarterly Income','Net income (loss) attributable to noncontrolling interests'),
    'income_inclusive': ('Quarterly Income','Net income (loss) attributable to bank and noncontrolling interests'),
    'income_reporters': ('Quarterly Income','Number of institutions reporting')}


def _address(address):
    match = re.fullmatch(r'([A-Z]+)(\d+)', address)
    return match[1], int(match[2])


def _label(value):
    return re.sub(r'\s+', ' ', value or '').strip()


def _label_rows(cells, text):
    return sorted({_address(address)[1] for address, cell in cells.items() if _label(cell['value']) == text})


def _unique_row(cells, text):
    matches = _label_rows(cells, text)
    require(len(matches) == 1, 'Missing or ambiguous FDIC heading: '+text)
    return matches[0]


def quarter_index(day):
    d = date.fromisoformat(day)
    require(d.month in (3,6,9,12) and day == quarter_end(d.year,d.month//3), 'Invalid bank reporting quarter')
    return d.year*4+d.month//3-1


def index_date(index):
    year, q = divmod(index,4)
    return quarter_end(year,q+1)


def _periods(cells, row, edition):
    periods = {}
    for address, cell in cells.items():
        column, line = _address(address)
        if line != row:
            continue
        match = re.fullmatch(r'((?:19|20)\d{2})Q([1-4])', cell['value'] or '')
        if match:
            end = quarter_end(int(match[1]),int(match[2]))
            require(end not in periods, 'Duplicate FDIC quarter heading')
            require(not cell.get('formula'), 'Formula-based quarter header unsupported')
            periods[end] = column
    require(periods and max(periods) == edition['quarter_end'], 'Workbook latest quarter differs from edition')
    indices = sorted(quarter_index(d) for d in periods)
    require(indices == list(range(indices[0],indices[-1]+1)), 'Missing FDIC quarter heading')
    return dict(sorted(periods.items()))


def _coordinates(cells, sheet, label, edition):
    if sheet == RATIO_SHEET:
        heading = _unique_row(cells,label)
        columns=[_address(a)[0] for a,c in cells.items() if _address(a)[1]==heading and _label(c['value'])==label]
        label_column=min(columns,key=lambda c:(len(c),c))
        following_labels=sorted((_address(a)[1],_label(c['value'])) for a,c in cells.items()
            if _address(a)[0]==label_column and _address(a)[1]>heading and _label(c['value']))
        require(following_labels and following_labels[0][1]=='Asset Size Group', 'Target ratio block population header is missing or moved')
        headers = _label_rows(cells,'Asset Size Group')
        following = [r for r in headers if r > heading]
        require(following, 'Missing FDIC ratio population/period header')
        header = min(following)
        # Each published block has one population/period header. Stop at the
        # next header rather than accidentally using a later metric's total.
        limit = min([r for r in headers if r>header], default=max(_address(a)[1] for a in cells)+1)
        candidates = [r for r in _label_rows(cells,POPULATION) if header < r < limit]
        require(len(candidates) == 1, 'Missing or duplicate all-insured population')
        row = candidates[0]
    else:
        _unique_row(cells, BS_TITLE if sheet=='Balance Sheet' else INCOME_TITLE)
        unit_row = _unique_row(cells, '(Amounts in $ Millions)')
        quarter_rows = {_address(a)[1] for a,c in cells.items() if re.fullmatch(r'(?:19|20)\d{2}Q[1-4]', c['value'] or '')}
        require(len(quarter_rows) == 1, 'Ambiguous quarterly table header')
        header = quarter_rows.pop()
        row = _unique_row(cells,label)
        require(unit_row < header < row, 'FDIC label lies outside expected table hierarchy')
    return row, header, _periods(cells,header,edition)


def _decimal(value):
    require(isinstance(value,str) and re.fullmatch(r'-?\d{1,20}(?:\.\d{1,20})?',value), 'Invalid or nonfinite banking value')
    return Decimal(value)


def _value(cell, unit):
    require(cell.get('type') != 'e' and not cell.get('formula'), 'Formula/error in selected FDIC source cell')
    value = cell.get('value')
    if value is None or value in ('','N/A','NA','n.a.'):
        return None
    require(cell.get('type') == 'n', 'Selected FDIC amount is not a numeric source cell')
    number = _decimal(value)
    require('%' not in cell.get('number_format',''), 'Unexpected percentage-fraction format in selected FDIC sheet')
    if unit == 'Percent':
        require(cell.get('number_format') == '0.00', 'Published ratio precision or units changed')
        return format(number.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')
    require(number == number.to_integral_value(), 'Expected whole source millions or reporting count')
    return format(number,'.0f')


def _series(book, spec, edition, url):
    cells = book[spec['sheet']]
    row, header, periods = _coordinates(cells,spec['sheet'],spec['row_label'],edition)
    observations = []
    for day, column in periods.items():
        address = column+str(row)
        cell = cells.get(address,dict(value=None,type='n'))
        value = _value(cell,spec['unit'])
        point = dict(date=day,value=value,source_value=cell.get('value'),cell=address,url=url)
        if value is None:
            point['missing_reason'] = 'Not supplied in the published source cell'
        observations.append(point)
    lookup = {p['date']:p for p in observations}; q = quarter_index(edition['quarter_end'])
    return dict(spec,frequency='Quarterly',population=POPULATION,header_row=header,source_row=row,
        current=lookup[edition['quarter_end']],prior=lookup.get(index_date(q-1)),year_ago=lookup.get(index_date(q-4)),
        observations=observations)


def _reconciliation(metrics, support):
    """Use rounding intervals for million-rounded components and 0.01% ratios."""
    values = {m['id']:{p['date']:p for p in m['observations']} for m in [*metrics,*support]}
    notes, checks = [], []
    def val(mid, day):
        value = values[mid][day]['value']
        return _decimal(value) if value is not None else None
    days = list(values['assets'])
    with localcontext() as ctx:
        ctx.prec = 40
        for day in days:
            assets, loans, allowance, pd90, nonaccrual, equity = [val(k,day) for k in ['assets','loans','allowance','past_due90','nonaccrual','bank_equity']]
            cases = [('noncurrent',None if pd90 is None or nonaccrual is None else pd90+nonaccrual,loans,Decimal(1),Decimal('.5')),
                     ('coverage',allowance,None if pd90 is None or nonaccrual is None else pd90+nonaccrual,Decimal('.5'),Decimal(1)),
                     ('equity_assets',equity,assets,Decimal('.5'),Decimal('.5'))]
            for mid,num,den,num_error,den_error in cases:
                published = val(mid,day)
                if any(v is None for v in (num,den,published)):
                    checks.append(dict(date=day,metric_id=mid,status='unavailable'))
                    continue
                require(den > den_error, 'Zero or invalid banking reconciliation denominator')
                calculated = num/den*100
                endpoints=[n/d*100 for n in (num-num_error,num+num_error) for d in (den-den_error,den+den_error)]
                low = min(endpoints)-Decimal('.005')
                high = max(endpoints)+Decimal('.005')
                match = low <= published <= high
                checks.append(dict(date=day,metric_id=mid,status='reconciled' if match else 'published_component_mismatch'))
                if not match:
                    notes.append(dict(date=day,metric_id=mid,published=str(published),calculated=format(calculated,'.6f'),
                        residual=format(published-calculated,'.6f'),
                        note='Published ratio cannot be reconstructed from these displayed components. Retained as published; not component-reconciled.'))
            # These whole-million financial statements are individually rounded.
            bank, nci, inclusive = [val(k,day) for k in ['net_income','income_nci','income_inclusive']]
            if all(v is not None for v in (bank,nci,inclusive)):
                residual=bank+nci-inclusive
                checks.append(dict(date=day,metric_id='income_bridge',status='reconciled' if abs(residual)<=1 else 'published_component_mismatch'))
                if abs(residual)>1:
                    notes.append(dict(date=day,metric_id='income_bridge',published=str(inclusive),calculated=str(bank+nci),residual=str(-residual),unit='USD millions',
                        note='Published inclusive income differs from bank income plus noncontrolling interests beyond rounding. Source values retained without repair.'))
            else:
                checks.append(dict(date=day,metric_id='income_bridge',status='unavailable'))
            liability, inclusive_equity = [val(k,day) for k in ['liabilities','inclusive_equity']]
            if all(v is not None for v in (assets,liability,inclusive_equity)):
                residual=assets-liability-inclusive_equity
                checks.append(dict(date=day,metric_id='balance_sheet',status='reconciled' if abs(residual)<=1 else 'published_component_mismatch'))
                if abs(residual)>1:
                    notes.append(dict(date=day,metric_id='balance_sheet',published=str(assets),calculated=str(liability+inclusive_equity),residual=str(residual),unit='USD millions',
                        note='Published assets differ from liabilities plus inclusive equity beyond rounding. Source values retained without repair.'))
            else:
                checks.append(dict(date=day,metric_id='balance_sheet',status='unavailable'))
            reporter_values = [val(k,day) for k in ['institutions','income_reporters','ratio_reporters']]
            require(len(set(reporter_values)) == 1, 'Reporting populations differ between selected FDIC tables')
    return checks,notes


def _recent_checks(checks,recent):
    expected={'noncurrent','coverage','equity_assets','income_bridge','balance_sheet'}
    for day in recent:
        rows=[c for c in checks if c['date']==day]
        require(len(rows)==len(expected) and {c['metric_id'] for c in rows}==expected
                and all(c['status']=='reconciled' for c in rows), 'Recent banking checks are missing or not reconciled')


def normalize_banking(body, receipt, edition, captured_at):
    book = read_xlsx(body)
    require(hashlib.sha256(body).hexdigest()==receipt['sha256'], 'Banking workbook hash mismatch')
    require(receipt['captured_at']==captured_at, 'Banking receipt capture mismatch')
    expected = discover_workbook(('<a href="'+receipt['url']+'">workbook</a>').encode(),edition)
    require(expected == receipt['url'], 'Banking workbook URL does not match edition')
    all_metrics = [_series(book,spec,edition,receipt['url']) for spec in SPECS]
    support = [_series(book,dict(id=mid,label=label,sheet=sheet,row_label=label,unit='Count' if mid=='income_reporters' else 'USD millions'),edition,receipt['url']) for mid,(sheet,label) in SUPPORT.items()]
    support.append(_series(book,dict(id='ratio_reporters',label='Number of Institutions Reporting',sheet=RATIO_SHEET,
        row_label='Number of Institutions Reporting',unit='Count'),edition,receipt['url']))
    dates = [p['date'] for p in all_metrics[0]['observations']]
    require(all([p['date'] for p in m['observations']]==dates for m in [*all_metrics,*support]), 'FDIC sheet quarterly periods do not align')
    recent = {edition['quarter_end'],index_date(quarter_index(edition['quarter_end'])-1),index_date(quarter_index(edition['quarter_end'])-4)}
    for metric in all_metrics:
        for point in metric['observations']:
            if point['date'] in recent:
                require(point['value'] is not None, 'Required current/prior/year-ago banking value missing')
            if point['value'] is not None and metric['id'] in ('assets','deposits','institutions','noncurrent','coverage'):
                require(_decimal(point['value'])>=0, 'Negative banking stock/count or credit ratio')
    checks, notes = _reconciliation(all_metrics,support)
    _recent_checks(checks,recent)
    result = dict(schema_version=1,source_id=SOURCE_ID,publisher=PUBLISHER,status='ok',captured_at=captured_at,
        last_success=captured_at,attempted_at=captured_at,**edition,publication_date=None,url=receipt['url'],receipt=copy.deepcopy(receipt),
        population=POPULATION,population_note='FDIC-reported aggregates of insured commercial banks and savings institutions, not bank holding companies. Parent and subsidiary institution reports can both be included without a double-counting adjustment.',
        metrics=all_metrics[:6],context=all_metrics[6:],support=support,quality_notes=notes,
        coverage=dict(start=dates[0],end=dates[-1],quarters=len(dates),
            note='Published history from this workbook edition, not original-release vintages. Historical component mismatches are retained explicitly; no ratios are reconstructed or repaired.'),
        validation=dict(status='reconciled',scope='Current, prior-quarter and year-ago source-component ratios; full history checked with exceptions retained.',checks=checks),
        attribution='Source: FDIC Quarterly Banking Profile.',
        terms_url='https://www.fdic.gov/data.json',
        method_note='Published aggregate ratios, not unweighted institution averages. Quarterly ROA and charge-off ratios are already annualized using average-period denominators. Percent values are percentage points; monetary values are USD millions. No regulatory capital ratios or composite health score.')
    validate_banking(result)
    return result


def validate_banking(bundle, raw_root=None):
    require(bundle.get('schema_version')==1 and bundle.get('source_id')==SOURCE_ID, 'Invalid banking bundle identity')
    require(bundle.get('status') in ('ok','stale','unavailable'), 'Invalid banking source status')
    if bundle['status']=='unavailable':
        require(not bundle.get('metrics') and not bundle.get('context'), 'Unavailable banking bundle contains unverified values')
        return
    captured = datetime.fromisoformat(bundle['captured_at']); attempted = datetime.fromisoformat(bundle['attempted_at'])
    require(captured.tzinfo and attempted.tzinfo and captured<=attempted and bundle.get('last_success')==bundle['captured_at'], 'Invalid banking success/attempt clocks')
    require(bundle.get('quarter_end')==quarter_end(bundle['year'],bundle['quarter']) and bundle['quarter_end']<=bundle['captured_at'][:10]
            and bundle.get('edition')==f"{bundle['year']} Q{bundle['quarter']}", 'Banking edition period mismatch')
    require(bundle.get('population')==POPULATION, 'Wrong banking population')
    receipt = bundle.get('receipt',{})
    require(receipt.get('url')==bundle.get('url') and receipt.get('captured_at')==bundle['captured_at']
            and re.fullmatch('[a-f0-9]{64}',receipt.get('sha256','')) and receipt.get('raw_path'), 'Banking source receipt invalid')
    discover_workbook(('<a href="'+bundle['url']+'">source</a>').encode(),bundle)
    metrics = bundle.get('metrics',[])+bundle.get('context',[])
    require(len(bundle.get('metrics',[]))==6 and len(bundle.get('context',[]))==3
            and [m['id'] for m in metrics]==[s['id'] for s in SPECS], 'Missing, duplicate or reordered banking metric identity')
    dates = None
    for metric,spec in zip(metrics,SPECS):
        require(all(metric.get(k)==v for k,v in spec.items()) and metric.get('population')==POPULATION
                and metric.get('frequency')=='Quarterly', 'Banking metric definition or quarterly population mismatch')
        observations = metric.get('observations',[])
        local_dates = [p['date'] for p in observations]
        require(local_dates and local_dates==sorted(set(local_dates)) and local_dates[-1]==bundle['quarter_end'], 'Banking observation quarter mismatch')
        require([quarter_index(d) for d in local_dates]==list(range(quarter_index(local_dates[0]),quarter_index(local_dates[-1])+1)), 'Missing banking history quarter')
        if dates is None: dates=local_dates
        require(local_dates==dates, 'Banking metric histories not aligned')
        lookup={p['date']:p for p in observations}; q=quarter_index(bundle['quarter_end'])
        for key,index in [('current',q),('prior',q-1),('year_ago',q-4)]:
            require(metric.get(key)==lookup.get(index_date(index)) and metric.get(key)
                    and metric[key]['value'] is not None, 'Banking headline period/missingness mismatch')
        for point in observations:
            require(point.get('url')==bundle['url'] and re.fullmatch('[A-Z]+[1-9]\d*',point.get('cell','')), 'Banking source cell provenance missing')
            if point['value'] is not None:
                _decimal(point['value'])
                require(point.get('source_value') is not None, 'Banking original cell value missing')
            else:
                require(point.get('missing_reason'), 'Banking missing value not explained')
    coverage=bundle.get('coverage',{})
    require(coverage.get('start')==dates[0] and coverage.get('end')==dates[-1] and coverage.get('quarters')==len(dates), 'Banking coverage metadata mismatch')
    support=bundle.get('support',[])
    require(len(support)==len(SUPPORT)+1 and {s['id'] for s in support}==set(SUPPORT)|{'ratio_reporters'}, 'Banking reconciliation inputs missing')
    require(all([p['date'] for p in s['observations']]==dates for s in support), 'Banking supporting periods mismatch')
    checks,notes=_reconciliation(metrics,support)
    require(bundle.get('quality_notes')==notes and bundle.get('validation',{}).get('checks')==checks
            and bundle['validation'].get('status')=='reconciled', 'Banking diagnostics differ from input evidence')
    recent={bundle['quarter_end'],index_date(quarter_index(bundle['quarter_end'])-1),index_date(quarter_index(bundle['quarter_end'])-4)}
    _recent_checks(checks,recent)
    if raw_root is not None:
        root=Path(raw_root).resolve()
        def retained(receipt,extension):
            relative=Path('data/banking/raw')/(receipt['sha256']+'.'+extension)
            require(receipt['raw_path']==relative.as_posix(), 'Banking evidence path outside content-addressed directory')
            path=root/relative
            require(not path.is_symlink() and path.resolve().is_relative_to((root/'data/banking/raw').resolve()), 'Unsafe banking evidence path')
            body=path.read_bytes()
            require(hashlib.sha256(body).hexdigest()==receipt['sha256'], 'Banking retained source hash mismatch')
            return body
        body=retained(receipt,'xlsx')
        discovery=bundle.get('discovery_receipts')
        require(isinstance(discovery,list) and len(discovery)==2 and discovery[0]['url']==LANDING, 'Banking discovery receipts missing')
        require(all(r.get('captured_at')==bundle['captured_at'] for r in discovery), 'Banking discovery clocks mismatch')
        discovered=discover_edition(retained(discovery[0],'html'),bundle['captured_at'])
        require(discovery[1]['url']==discovered['edition_url'], 'Banking discovery edition URL mismatch')
        page=retained(discovery[1],'html')
        require(discover_workbook(page,discovered)==bundle['url'], 'Banking discovery workbook URL mismatch')
        require(bundle.get('notes_url')==discover_notes(page,discovered), 'Banking definitions link differs from edition source')
        require(all(bundle.get(k)==v for k,v in discovered.items()), 'Banking latest edition differs from discovery')
        edition={k:bundle[k] for k in ('year','quarter','quarter_end','edition','edition_url','notes_url')}
        rebuilt=normalize_banking(body,receipt,edition,bundle['captured_at'])
        for key in rebuilt:
            if key not in ('status','attempted_at'):
                require(bundle.get(key)==rebuilt[key], 'Banking normalized value differs from raw source: '+key)


def compare_banking(previous,current):
    old_capture=(previous or {}).get('captured_at');stamp=current.get('captured_at')
    state='unavailable' if current.get('status')!='ok' else 'baseline' if not old_capture or not (previous or {}).get('metrics') else 'compared'
    result=dict(from_capture=old_capture,to_capture=stamp,items=[],
        baselines=[SOURCE_ID] if state=='baseline' else [],skipped=[SOURCE_ID] if state=='unavailable' else [],
        channels=[dict(id=SOURCE_ID,label=PUBLISHER,status=state,from_capture=old_capture,to_capture=stamp,
                       attempted_at=current.get('attempted_at'),error=current.get('error') if state=='unavailable' else None)])
    if state!='compared':return result
    old={m['id']:m for m in previous.get('metrics',[])+previous.get('context',[])}
    fields=('unit','frequency','annualized','stock_flow','definition','population')
    for metric in current.get('metrics',[])+current.get('context',[]):
        before=old.get(metric['id'])
        if not before:continue
        context=dict(source_id=SOURCE_ID,publisher=PUBLISHER,title=metric['label'],metric_id=metric['id'],series_id=SOURCE_ID+'-'+metric['id'],
            from_capture=old_capture,to_capture=stamp,url=current['url'],previous_url=previous['url'],
            edition=current['edition'],previous_edition=previous['edition'],unit=metric['unit'])
        if previous.get('population')!=current.get('population') or any(before.get(k)!=metric.get(k) for k in fields):
            result['items'].append(dict(context,kind='Banking definition changed',comparison_boundary=True,
                before=json.dumps({k:before.get(k) for k in fields},sort_keys=True),
                after=json.dumps({k:metric.get(k) for k in fields},sort_keys=True)))
            continue
        prior={p['date']:p for p in before['observations']}
        for point in metric['observations']:
            p=prior.get(point['date']);kind=None
            if p is None:kind='New banking reporting quarter' if point['date']>max(prior) else 'Newly available banking quarter'
            elif p['value'] is None and point['value'] is not None:kind='Banking value became available'
            elif p['value'] is not None and point['value'] is None:kind='Banking value unavailable'
            elif p['value'] is not None and _decimal(p['value'])!=_decimal(point['value']):kind='Revised banking value'
            if kind:
                result['items'].append(dict(context,kind=kind,date=point['date'],before=p['value'] if p else None,
                    after=point['value'],comparison_boundary=p is None,cell=point['cell']))
    return result


def collect_banking(previous,stamp,data_dir=DATA,fetcher=fetch):
    receipts=[]
    try:
        landing,receipt=fetcher(LANDING,data_dir,stamp,'html');receipts.append(receipt)
        edition=discover_edition(landing,stamp)
        page,receipt=fetcher(edition['edition_url'],data_dir,stamp,'html');receipts.append(receipt)
        edition['notes_url']=discover_notes(page,edition)
        url=discover_workbook(page,edition)
        body,receipt=fetcher(url,data_dir,stamp,'xlsx');receipts.append(receipt)
        bundle=normalize_banking(body,receipt,edition,stamp)
        bundle['discovery_receipts']=receipts[:2]
    except Exception as error:
        message=str(error) if isinstance(error,BankingError) else 'FDIC collection or normalization failed'
        bundle=copy.deepcopy(previous) if previous and previous.get('metrics') else dict(schema_version=1,
            source_id=SOURCE_ID,publisher=PUBLISHER,url=LANDING,metrics=[],context=[],captured_at=None)
        bundle.update(status='stale' if bundle.get('metrics') else 'unavailable',attempted_at=stamp,error=message)
    bundle['changes']=compare_banking(previous,bundle)
    return bundle,dict(attempted_at=stamp,status=bundle['status'],receipts=receipts,error=bundle.get('error'))


def main():
    DATA.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
    current=DATA/'current.json'
    previous=json.loads(current.read_text()) if current.exists() else None
    (DATA/'comparison-baseline.json').write_text(json.dumps(previous,separators=(',',':')))
    bundle,attempt=collect_banking(previous,stamp)
    validate_banking(bundle,raw_root=ROOT)
    text=json.dumps(bundle,allow_nan=False,separators=(',',':'))
    current.write_text(text)
    suffix=stamp[:19].replace(':','')
    (DATA/('capture-'+suffix+'.json')).write_text(text)
    (DATA/('attempt-'+suffix+'.json')).write_text(json.dumps(attempt,allow_nan=False,separators=(',',':')))
    print('FDIC QBP',bundle['status'],bundle.get('edition'),bundle.get('coverage',{}).get('quarters'),'quarters')
    if bundle.get('error'):print(bundle['error'])


if __name__=='__main__':main()
