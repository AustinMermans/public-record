import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import banking as b

STAMP='2002-04-15T12:00:00+00:00'
EDITION=dict(year=2002,quarter=1,quarter_end='2002-03-31',edition='2002 Q1',
    edition_url='https://www.fdic.gov/quarterly-banking-profile/quarterly-banking-profile-q1-2002',
    notes_url='https://www.fdic.gov/quarterly-banking-profile/qbp-notes-users-first-quarter-2002.pdf')
URL='https://www.fdic.gov/quarterly-banking-profile/qbp-time-series-spreadsheets-first-quarter-2002.xlsx'


def fixture_book():
    book={b.RATIO_SHEET:{},'Balance Sheet':{},'Quarterly Income':{}}
    def put(sheet,address,value,ratio=False):
        book[sheet][address]=dict(value=str(value),type='s' if isinstance(value,str) else 'n',formula=None,
                                  number_format='0.00' if ratio else 'General')
    def periods(sheet,row):
        for index in range(9):
            put(sheet,chr(67+index)+str(row),str(2000+index//4)+'Q'+str(index%4+1))
    ratio_values={'noncurrent':1,'nco':.5,'coverage':200,'roa':1.2,'equity_assets':10,'institutions':100}
    ratio_specs=[s for s in b.SPECS if s['sheet']==b.RATIO_SHEET]+[dict(id='institutions',row_label='Number of Institutions Reporting')]
    for index,spec in enumerate(ratio_specs):
        row=2+index*10
        put(b.RATIO_SHEET,'B'+str(row),spec['row_label'])
        put(b.RATIO_SHEET,'B'+str(row+2),'Asset Size Group');periods(b.RATIO_SHEET,row+2)
        put(b.RATIO_SHEET,'B'+str(row+3),'Assets < $100 Million')
        put(b.RATIO_SHEET,'B'+str(row+4),b.POPULATION)
        for column in 'CDEFGHIJK':put(b.RATIO_SHEET,column+str(row+4),ratio_values[spec['id']],spec['id']!='institutions')
    inputs={'deposits':7000,'institutions':100,'assets':10000,'net_income':30,
        'loans':5000,'allowance':100,'past_due90':10,'nonaccrual':40,'bank_equity':1000,
        'inclusive_equity':1010,'liabilities':8990,'income_nci':1,'income_inclusive':31,'income_reporters':100}
    for sheet,title in [('Balance Sheet',b.BS_TITLE),('Quarterly Income',b.INCOME_TITLE)]:
        put(sheet,'B2',title);put(sheet,'B4','(Amounts in $ Millions)');periods(sheet,5)
        specs=[s for s in b.SPECS if s['sheet']==sheet]
        specs += [dict(id=mid,row_label=label) for mid,(source,label) in b.SUPPORT.items() if source==sheet]
        for index,spec in enumerate(specs):
            row=8+index;put(sheet,'B'+str(row),spec['row_label'])
            for column in 'CDEFGHIJK':put(sheet,column+str(row),inputs[spec['id']])
    return book


def workbook_bytes(book):
    """Tiny OOXML source fixtures, not authored user-facing spreadsheets."""
    ns=b.NS['s'];rel=b.REL
    workbook=ET.Element('workbook',xmlns=ns);sheets=ET.SubElement(workbook,'sheets')
    relationships=ET.Element('Relationships',xmlns='http://schemas.openxmlformats.org/package/2006/relationships')
    content={}
    for index,(name,cells) in enumerate(book.items(),1):
        ET.SubElement(sheets,'sheet',name=name,sheetId=str(index),attrib={'{'+rel+'}id':'rId'+str(index)})
        ET.SubElement(relationships,'Relationship',Id='rId'+str(index),Target='worksheets/sheet'+str(index)+'.xml')
        sheet=ET.Element('worksheet',xmlns=ns);data=ET.SubElement(sheet,'sheetData');rows={}
        for address,cell in cells.items():
            _,row=b._address(address)
            if row not in rows:rows[row]=ET.SubElement(data,'row',r=str(row))
            kind='inlineStr' if cell['type']=='s' else cell['type']
            node=ET.SubElement(rows[row],'c',r=address,t=kind,s='1' if cell.get('number_format')=='0.00' else '0')
            if cell.get('formula'):ET.SubElement(node,'f').text=cell['formula']
            if cell['value'] is not None:
                if kind=='inlineStr':ET.SubElement(ET.SubElement(node,'is'),'t').text=cell['value']
                else:ET.SubElement(node,'v').text=cell['value']
        content['xl/worksheets/sheet'+str(index)+'.xml']=ET.tostring(sheet)
    content['xl/workbook.xml']=ET.tostring(workbook)
    content['xl/_rels/workbook.xml.rels']=ET.tostring(relationships)
    content['xl/styles.xml']=('<styleSheet xmlns="'+ns+'"><cellXfs><xf numFmtId="0"/><xf numFmtId="2"/></cellXfs></styleSheet>').encode()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for path,body in content.items():archive.writestr(path,body)
    return buffer.getvalue()


def receipt(body,url=URL,extension='xlsx',stamp=STAMP):
    sha=hashlib.sha256(body).hexdigest()
    return dict(url=url,sha256=sha,raw_path='data/banking/raw/'+sha+'.'+extension,captured_at=stamp)


def normalize(book=None):
    body=workbook_bytes(book or fixture_book())
    return b.normalize_banking(body,receipt(body),EDITION,STAMP)


def address(book,mid,last=True):
    spec=next(s for s in b.SPECS if s['id']==mid)
    row,_,columns=b._coordinates(book[spec['sheet']],spec['sheet'],spec['row_label'],EDITION)
    return spec['sheet'],('K' if last else 'C')+str(row)


class BankingParserTests(unittest.TestCase):
    def test_semantic_workbook_mapping_units_and_quarterly_income(self):
        data=normalize();metrics={m['id']:m for m in data['metrics']+data['context']}
        self.assertEqual(metrics['noncurrent']['current']['value'],'1.00')
        self.assertEqual(metrics['deposits']['current']['value'],'7000')
        self.assertEqual(metrics['net_income']['current']['value'],'30')
        self.assertEqual(metrics['nco']['unit'],'Percent');self.assertTrue(metrics['nco']['annualized'])
        self.assertEqual(metrics['net_income']['stock_flow'],'Quarter flow')
        self.assertEqual(metrics['roa']['prior']['date'],'2001-12-31')
        self.assertEqual(metrics['roa']['year_ago']['date'],'2001-03-31')
        self.assertEqual(data['coverage']['quarters'],9)
        self.assertEqual(data['quality_notes'],[])

    def test_source_binary_serialization_is_rounded_to_published_precision(self):
        book=fixture_book();sheet,cell=address(book,'nco');book[sheet][cell]['value']='0.56999999999999995'
        data=normalize(book);point=next(m for m in data['metrics'] if m['id']=='nco')['current']
        self.assertEqual(point['value'],'0.57');self.assertEqual(point['source_value'],'0.56999999999999995')

    def test_missing_or_renamed_population_header_never_uses_next_metric(self):
        for mid in ['roa','nco']:
            book=fixture_book();spec=next(s for s in b.SPECS if s['id']==mid)
            row=b._unique_row(book[b.RATIO_SHEET],spec['row_label'])
            book[b.RATIO_SHEET]['B'+str(row+2)]['value']='Unexpected header'
            with self.subTest(metric=mid):
                with self.assertRaisesRegex(b.BankingError,'header'):
                    b._coordinates(book[b.RATIO_SHEET],b.RATIO_SHEET,spec['row_label'],EDITION)
                with self.assertRaises(b.BankingError):normalize(book)

    def test_duplicate_or_missing_population_fails(self):
        for mode in ['duplicate','missing']:
            book=fixture_book();cells=book[b.RATIO_SHEET]
            if mode=='duplicate':cells['B7']=dict(cells['B6'])
            else:cells['B6']['value']='Commercial banks only'
            with self.subTest(mode=mode),self.assertRaises(b.BankingError):normalize(book)

    def test_missing_duplicate_or_future_quarter_header_fails(self):
        for mode in ['missing','duplicate','future']:
            book=fixture_book();cells=book['Balance Sheet']
            if mode=='missing':del cells['G5']
            elif mode=='duplicate':cells['L5']=dict(cells['K5'])
            else:cells['K5']['value']='2002Q2'
            with self.subTest(mode=mode),self.assertRaises(b.BankingError):normalize(book)

    def test_annual_income_wrong_unit_or_formula_and_error_rejected(self):
        for mode in ['annual','unit','formula','error','nan']:
            book=fixture_book();sheet,cell=address(book,'roa')
            if mode=='annual':book['Quarterly Income']['B2']['value']=b.INCOME_TITLE.replace('Quarterly','Annual')
            elif mode=='unit':book['Quarterly Income']['B4']['value']='(Amounts in $ Thousands)'
            elif mode=='formula':book[sheet][cell]['formula']='1+1'
            elif mode=='error':book[sheet][cell].update(type='e',value='#VALUE!')
            else:book[sheet][cell]['value']='NaN'
            with self.subTest(mode=mode),self.assertRaises(b.BankingError):normalize(book)

    def test_percentage_fraction_format_rejected(self):
        book=fixture_book();sheet,cell=address(book,'roa');book[sheet][cell]['number_format']='0.00%'
        with patch('banking.read_xlsx',return_value=book),self.assertRaises(b.BankingError):normalize()

    def test_historical_missingness_is_not_zero_but_headline_missing_rejected(self):
        book=fixture_book();sheet,cell=address(book,'nco',last=False);book[sheet][cell].update(value='N/A',type='s')
        metric=next(m for m in normalize(book)['metrics'] if m['id']=='nco')
        self.assertIsNone(metric['observations'][0]['value']);self.assertTrue(metric['observations'][0]['missing_reason'])
        sheet,cell=address(book,'nco');book[sheet][cell].update(value='N/A',type='s')
        with self.assertRaises(b.BankingError):normalize(book)

    def test_historical_ratio_exception_preserved_recent_exception_rejected(self):
        book=fixture_book();sheet,cell=address(book,'noncurrent',last=False);book[sheet][cell]['value']='2'
        data=normalize(book);self.assertEqual(data['quality_notes'][0]['date'],'2000-03-31')
        self.assertEqual(data['metrics'][0]['observations'][0]['value'],'2.00')
        sheet,cell=address(book,'noncurrent');book[sheet][cell]['value']='2'
        with self.assertRaisesRegex(b.BankingError,'Recent'):normalize(book)

    def test_negative_equity_rounding_interval_is_sign_safe(self):
        book=fixture_book();cells=book['Balance Sheet']
        for label,value in [('Total bank equity capital','-1000'),('Total equity capital','-990'),('Total liabilities','10990')]:
            row=b._unique_row(cells,label)
            for column in 'CDEFGHIJK':cells[column+str(row)]['value']=value
        sheet,cell=address(book,'equity_assets');row=b._address(cell)[1]
        for column in 'CDEFGHIJK':book[sheet][column+str(row)]['value']='-10'
        self.assertEqual(normalize(book)['quality_notes'],[])

    def test_zero_denominator_and_population_mismatch_fail(self):
        for label,value in [('Total loans and leases','0'),('Number of institutions reporting','99')]:
            book=fixture_book();row=b._unique_row(book['Balance Sheet'],label);book['Balance Sheet']['K'+str(row)]['value']=value
            with self.subTest(label=label),self.assertRaises(b.BankingError):normalize(book)

    def test_missing_recent_reconciliation_components_never_skip_gate(self):
        for mid in ['liabilities','inclusive_equity','income_nci','income_inclusive']:
            book=fixture_book();sheet,label=b.SUPPORT[mid];row=b._unique_row(book[sheet],label)
            book[sheet]['K'+str(row)].update(value='N/A',type='s')
            with self.subTest(metric=mid),self.assertRaisesRegex(b.BankingError,'Recent'):normalize(book)
        book=fixture_book();sheet,label=b.SUPPORT['income_nci'];row=b._unique_row(book[sheet],label)
        book[sheet]['C'+str(row)].update(value='N/A',type='s')
        data=normalize(book)
        check=next(c for c in data['validation']['checks'] if c['date']=='2000-03-31' and c['metric_id']=='income_bridge')
        self.assertEqual(check['status'],'unavailable')


class BankingCollectionTests(unittest.TestCase):
    def fixture_capture(self,directory=None):
        body=workbook_bytes(fixture_book())
        landing=('<a href="'+EDITION['edition_url']+'">QBP</a>').encode()
        page=('<a href="'+URL+'">Workbook</a><a href="'+EDITION['notes_url']+'">Notes</a>').encode()
        replies={b.LANDING:(landing,'html'),EDITION['edition_url']:(page,'html'),URL:(body,'xlsx')}
        calls=[]
        def fake(url,data_dir,stamp,extension):
            calls.append(url);content,ext=replies[url];self.assertEqual(extension,ext)
            r=receipt(content,url,ext,stamp)
            if directory:
                path=Path(directory)/r['raw_path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            return content,r
        bundle,_=b.collect_banking(None,STAMP,fetcher=fake)
        self.assertEqual(bundle['status'],'ok',bundle.get('error'))
        self.assertEqual(calls,[b.LANDING,EDITION['edition_url'],URL])
        return bundle

    def test_discovery_handles_quarter_name_variants_and_future_links(self):
        html=('<a href="'+EDITION['edition_url']+'">one</a><a href="/quarterly-banking-profile/quarterly-banking-profile-2q-2002">future</a>').encode()
        self.assertEqual(b.discover_edition(html,STAMP)['quarter'],1)
        with self.assertRaises(b.BankingError):b.discover_workbook(b'<a href="https://evil.test/file.xlsx">workbook</a>',EDITION)

    def test_raw_validation_binds_discovery_workbook_cells_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            data=self.fixture_capture(directory);b.validate_banking(data,raw_root=directory)
            for mode in ['no_discovery','wrong_cell','changed_income','hash','path']:
                changed=copy.deepcopy(data)
                if mode=='no_discovery':del changed['discovery_receipts']
                elif mode=='wrong_cell':changed['metrics'][0]['observations'][0]['cell']='ZZ1'
                elif mode=='changed_income':
                    for point in changed['context'][-1]['observations']:point['value']='30.1'
                    changed['context'][-1]['current']=changed['context'][-1]['observations'][-1]
                    changed['context'][-1]['prior']=changed['context'][-1]['observations'][-2]
                    changed['context'][-1]['year_ago']=changed['context'][-1]['observations'][-5]
                elif mode=='hash':(Path(directory)/changed['receipt']['raw_path']).write_bytes(b'bad')
                else:changed['receipt']['raw_path']='../bad.xlsx'
                with self.subTest(mode=mode),self.assertRaises(b.BankingError):b.validate_banking(changed,raw_root=directory)

    def test_stale_failure_retains_capture_and_raw_validates(self):
        with tempfile.TemporaryDirectory() as directory:
            original=self.fixture_capture(directory)
            def failure(*args):raise RuntimeError('secret sentinel')
            stale,attempt=b.collect_banking(original,'2002-04-16T12:00:00+00:00',fetcher=failure)
            self.assertEqual(stale['status'],'stale');self.assertEqual(stale['captured_at'],STAMP)
            self.assertEqual(stale['metrics'],original['metrics']);self.assertEqual(stale['changes']['skipped'],['fdic-qbp'])
            self.assertNotIn('sentinel',json.dumps(attempt));b.validate_banking(stale,raw_root=directory)
            unavailable,_=b.collect_banking(None,STAMP,fetcher=failure);b.validate_banking(unavailable)

    def test_comparison_baseline_revisions_new_quarter_and_definition(self):
        original=normalize()
        self.assertEqual(b.compare_banking(None,original)['baselines'],['fdic-qbp'])
        self.assertEqual(b.compare_banking(original,copy.deepcopy(original))['items'],[])
        current=copy.deepcopy(original);current['metrics'][1]['observations'][0]['value']='0.60'
        item=b.compare_banking(original,current)['items'][0]
        self.assertEqual(item['kind'],'Revised banking value');self.assertEqual(item['series_id'],'fdic-qbp-nco')
        current=copy.deepcopy(original);current['metrics'][1]['annualized']=False
        self.assertTrue(b.compare_banking(original,current)['items'][0]['comparison_boundary'])
        current=copy.deepcopy(original);m=current['metrics'][1]
        m['observations'].append(dict(m['observations'][-1],date='2002-06-30'))
        self.assertEqual(b.compare_banking(original,current)['items'][0]['kind'],'New banking reporting quarter')


if __name__=='__main__':unittest.main()
