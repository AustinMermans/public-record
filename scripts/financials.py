"""Filing-anchored, screen-grade SEC companyfacts normalization.

Pure transformation: no network, persistence, estimates, currency conversion,
TTM reconstruction or implicit substitution of old concepts into current rows.
"""
from __future__ import annotations

from datetime import date
import math


REVENUE = {
    # Explicit covered-issuer mappings. Candidates retain their distinct source
    # concept and definition; a prior value must use the selected current tag.
    cik: ('RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'SalesRevenueNet')
    for cik in ('0000320193', '0000789019', '0001018724', '0000104169', '0001045810',
                '0001652044', '0001326801', '0001318605', '0000059478', '0001403161',
                '0000200406', '0000021344', '0000018230', '0000080424', '0000040545',
                '0000354950', '0001707925', '0000753308', '0001045609')
}
REVENUE.update({cik: ('Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax',
                     'RevenueFromContractWithCustomerIncludingAssessedTax')
                for cik in ('0000034088', '0002115436', '0001067983', '0000731766')})
REVENUE['0000104169'] = ('Revenues',)  # Includes membership/other income, unlike merchandise contract revenue.
BANKS = {'0000019617', '0000070858'}
SPECIALISTS = {
    '0001067983': ('insurance_conglomerate', 'Insurance and investment conglomerate: generic tags do not establish underwriting results or comparable industrial margins.'),
    '0000731766': ('health_insurance_services', 'Health insurance and services: generic tags do not establish medical-care ratios or segment economics.'),
    '0001045609': ('reit', 'REIT: GAAP earnings and cash PPE payments are not FFO, AFFO or same-store NOI.'),
    '0000753308': ('utility', 'Utility: consolidated cash investment includes regulated and other operations; it is not a regulatory funding-gap estimate.'),
    '0000018230': ('industrial_finance', 'Consolidated industrial and financing activities: these figures do not establish industrial net debt or leverage.'),
    '0000040545': ('industrial_perimeter', 'Historical consolidation and disposal changes require filing review; same-tag comparisons are not an organic-growth bridge.'),
    '0000034088': ('predecessor_registrant', 'Prior Exxon Mobil registrant: its CIK history is not spliced into the successor holding company.'),
    '0002115436': ('successor_registrant', 'ExxonMobil holding-company registrant: predecessor CIK history remains separate.')}

COMMON_INCOME = [
    ('operating_income', 'Operating income', ('OperatingIncomeLoss',), 'USD'),
    ('net_income', 'Net income', ('NetIncomeLoss', 'ProfitLoss'), 'USD'),
    ('eps_diluted', 'Diluted earnings per share', ('EarningsPerShareDiluted',), 'USD/shares')]
BANK_INCOME = [
    ('revenue', 'Net revenue after interest expense', ('RevenuesNetOfInterestExpense',), 'USD'),
    ('net_interest_income', 'Net interest income', ('InterestIncomeExpenseNet',), 'USD'),
    ('noninterest_income', 'Noninterest income', ('NoninterestIncome',), 'USD'),
    ('credit_provision', 'Provision for credit losses', ('ProvisionForLoanLeaseAndOtherLosses', 'ProvisionForCreditLosses'), 'USD'),
    ('net_income', 'Net income', ('NetIncomeLoss',), 'USD'),
    ('eps_diluted', 'Diluted earnings per share', ('EarningsPerShareDiluted',), 'USD/shares')]
CASH_FLOW = [
    ('cfo', 'Operating cash flow', ('NetCashProvidedByUsedInOperatingActivities',), 'USD'),
    ('cash_ppe', 'Cash payments for property, plant and equipment', ('PaymentsToAcquirePropertyPlantAndEquipment',), 'USD')]
BALANCE = [
    ('cash', 'Cash and cash equivalents', ('CashAndCashEquivalentsAtCarryingValue',), 'USD'),
    ('assets', 'Total assets', ('Assets',), 'USD'),
    ('liabilities', 'Total liabilities (not debt)', ('Liabilities',), 'USD'),
    ('equity', 'Equity', ('StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest', 'StockholdersEquity'), 'USD')]
TEMPORARY_EQUITY = ('temporary_equity', 'Temporary equity (as tagged)',
                   ('TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests',
                    'RedeemableNoncontrollingInterestEquityCarryingAmount'), 'USD')


def _day(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError('Expected ISO date')
    return date.fromisoformat(value)


def _days(start, end):
    return (_day(end) - _day(start)).days + 1


class Normalizer:
    def __init__(self, payload, company, captured_at):
        self.company = company
        self.cik = str(company['cik']).zfill(10)
        if str(payload.get('cik', '')).zfill(10) != self.cik:
            raise ValueError('Companyfacts CIK does not match covered issuer')
        _day(captured_at[:10])
        self.captured_at = captured_at
        self.facts = payload.get('facts', {}).get('us-gaap', {})
        self.sources = {}
        self.flags = []
        self.checks = []
        self.bridges = []
        self.filings = [f for f in company.get('filings', [])
                        if f.get('form') in ('10-K', '10-Q', '10-K/A', '10-Q/A')
                        and f.get('report_period') and f.get('filed')
                        and f['filed'] <= captured_at[:10] and f['report_period'] <= f['filed']]
        for f in self.filings:
            _day(f['report_period']); _day(f['filed'])
        self.by_accession = {f['id']: f for f in self.filings}

    def flag(self, area, issue, period=None, source_id=None, severity='medium'):
        self.flags.append(dict(flag_id=f'QA-{len(self.flags)+1:03}', severity=severity,
                               entity=self.company['name'], period=period, area=area, issue=issue,
                               impact='Limits reported-financial comparison; not a complete model input.',
                               recommended_fix='Inspect the accession-linked financial statements and concept definition.',
                               source_id=source_id, status='open'))

    def check(self, area, period, test, expected, observed, result, source_id=None):
        self.checks.append(dict(check_id=f'CHECK-{len(self.checks)+1:03}', area=area, period=period,
                                test=test, expected_value=expected, observed_value=observed,
                                variance=observed-expected if isinstance(expected,(int,float)) and isinstance(observed,(int,float)) else None,
                                result=result, source_id=source_id))

    def raw(self, concept, unit):
        return self.facts.get(concept, {}).get('units', {}).get(unit, [])

    def eligible(self, fact, accession):
        try:
            if fact.get('accn') != accession or fact.get('form') not in ('10-K', '10-Q', '10-K/A', '10-Q/A'):
                return False
            filing=self.by_accession.get(accession)
            if filing and (fact['form']!=filing['form'] or fact.get('filed')!=filing['filed']):
                return False
            _day(fact['end']); _day(fact['filed'])
            if fact.get('start'):
                _day(fact['start'])
                if fact['start'] > fact['end']:
                    return False
            return (fact['end'] <= fact['filed'] <= self.captured_at[:10]
                    and not isinstance(fact['val'], bool) and isinstance(fact['val'], (int,float))
                    and math.isfinite(fact['val']))
        except (KeyError, ValueError, TypeError):
            return False

    def evidence(self, fact, concept, unit, label='fact_source_reported'):
        accession = fact['accn']; filing = self.by_accession.get(accession, {})
        url = filing.get('url') or f'https://www.sec.gov/Archives/edgar/data/{int(self.cik)}/{accession.replace("-", "")}/{accession}-index.html'
        sid = f'SEC-{self.cik}-{accession}'
        source = self.sources.setdefault(sid, dict(source_id=sid, source_name=f'{self.company["name"]} {fact["form"]} filed {fact["filed"]}',
            source_type='filing', owner_or_provider='SEC / issuer-reported XBRL', period_covered=[],
            as_of_date=fact['filed'], retrieved_at=self.captured_at, file_tab_page_url_or_location=url,
            source_rank=3, freshness_status='acceptable_for_period',
            notes='Companyfacts standardized taxonomy facts; accession-linked. Filing date is not an intraday availability timestamp.'))
        period = (fact.get('start')+' to ' if fact.get('start') else '')+fact['end']
        if period not in source['period_covered']:
            source['period_covered'].append(period)
        return dict(value=fact['val'], start=fact.get('start'), end=fact['end'], accession=accession,
                    filed=fact['filed'], form=fact['form'], url=url, source_id=sid,
                    evidence_label=label, namespace='us-gaap', concept=concept, unit=unit,
                    fy=fact.get('fy'), fp=fact.get('fp'), frame=fact.get('frame'),
                    source_label=self.facts.get(concept,{}).get('label',concept),
                    source_definition=self.facts.get(concept,{}).get('description',''),
                    confidence='high', normalization_method='as_reported', retrieved_at=self.captured_at)

    def pick(self, concept, unit, start, end, anchor):
        original = [f for f in self.raw(concept,unit) if self.eligible(f,anchor['id'])
                    and f.get('start') == start and f['end'] == end]
        if not original:
            return None, 'No fact for this concept, unit, exact period and anchor accession.', []
        # Amendments can disagree on one line without replacing unrelated rows.
        amendments = [f for a in self.filings if a['form'] == anchor['form']+'/A'
                      and a['report_period'] == anchor['report_period'] and a['filed'] >= anchor['filed']
                      for f in self.raw(concept,unit) if self.eligible(f,a['id'])
                      and f.get('start') == start and f['end'] == end]
        candidates = original + amendments
        if len({f['val'] for f in candidates}) != 1:
            return None, 'Conflicting facts for the same concept, unit and exact period; no working value selected.', [self.evidence(f,concept,unit,'contradicted_source') for f in candidates]
        fact = sorted(original,key=lambda f:(f['filed'],f.get('frame','')))[-1]
        self.check(concept,end,'Exact-period same-accession value is unique',1,1,'pass')
        return self.evidence(fact,concept,unit), None, []

    def period(self, specs, anchor, kind):
        end = anchor['report_period']; candidates = set()
        for _, _, concepts, unit in specs:
            for concept in concepts:
                for fact in self.raw(concept,unit):
                    if not self.eligible(fact,anchor['id']) or fact['end'] != end or not fact.get('start'):
                        continue
                    span = _days(fact['start'],end)
                    fp = fact.get('fp')
                    if kind == 'annual':
                        valid = anchor['form']=='10-K' and fp=='FY' and 350 <= span <= 380
                    elif kind == 'quarter':
                        valid = anchor['form']=='10-Q' and fp in ('Q1','Q2','Q3') and 75 <= span <= 105
                    else:
                        bounds={'Q1':(75,105),'Q2':(150,210),'Q3':(240,300)}
                        valid=fp in bounds and bounds[fp][0] <= span <= bounds[fp][1]
                    if valid:
                        candidates.add((fact['start'],end))
        if len(candidates) == 1:
            start,end = next(iter(candidates))
            self.check(kind,end,'Unique filing-anchored duration and fiscal label',1,1,'pass')
            return start,end
        self.flag(kind,'No unique full-period duration established; missing, conflicting or stub periods are not filled.',end)
        return None,end

    def prior_period(self, concept, unit, start, end, anchor):
        if start is None:
            annual_ends={f['report_period'] for f in self.filings if f['form']=='10-K' and f['report_period']<end}
            target=max(annual_ends) if annual_ends else None
            return (None,target) if target else None
        span=_days(start,end)
        candidates={(f['start'],f['end']) for f in self.raw(concept,unit)
                    if self.eligible(f,anchor['id']) and f.get('start') and f['end']<end
                    and 350 <= (_day(end)-_day(f['end'])).days <= 380
                    and abs(_days(f['start'],f['end'])-span)<=7}
        return next(iter(candidates)) if len(candidates)==1 else None

    def row(self, spec, period, anchor, section):
        rid,label,concepts,unit = spec; start,end = period
        row=dict(id=rid,label=label,concept=None,unit=unit,current=None,prior=None,
                 comparison_status='missing_required_source',evidence_label='missing_required_source')
        if section!='balance_sheet' and start is None:
            row['issue']='A defensible duration is unavailable.'
            return row
        # Choose a mapped concept only if this exact current filing/period has it.
        concept=next((c for c in concepts if any(self.eligible(f,anchor['id']) and f.get('start')==start and f['end']==end for f in self.raw(c,unit))),None)
        if not concept:
            row['issue']='No mapped current-period fact in the anchor filing and required unit; no old-tag or currency fallback.'
            self.flag(rid,row['issue'],end)
            return row
        row['concept']='us-gaap:'+concept
        if rid=='net_income':
            row['label']='Net income attributable to parent' if concept=='NetIncomeLoss' else 'Net income including noncontrolling interests'
        if rid=='equity':
            row['label']='Equity including noncontrolling interests' if concept=='StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest' else 'Parent stockholders’ equity'
        if rid=='temporary_equity':
            row['label']='Redeemable noncontrolling interests' if concept=='RedeemableNoncontrollingInterestEquityCarryingAmount' else 'Temporary equity including noncontrolling interests'
        current,issue,conflicts=self.pick(concept,unit,start,end,anchor)
        row['current']=current
        if issue:
            row.update(issue=issue,conflicts=conflicts)
            self.flag(rid,issue,end,severity='high' if conflicts else 'medium')
            return row
        row['evidence_label']='fact_source_reported'
        prior_period=self.prior_period(concept,unit,start,end,anchor)
        if prior_period:
            row['prior'],issue,conflicts=self.pick(concept,unit,*prior_period,anchor)
            if conflicts:row['conflicts']=conflicts
        else:
            issue='No uniquely matched comparative period in the current filing.'
        row['comparison_status']='comparable' if row['prior'] else 'missing_required_source'
        if issue:
            row['issue']=issue
            self.bridges.append(dict(area=section,metric_or_framework=rid,current_period=end,
                prior_period=prior_period[1] if prior_period else None,current_basis=row['concept'],
                prior_basis='Same concept, unit and comparable duration required',comparison_status='missing_required_source',
                current_value=current['value'],prior_value=None,model_treatment='Current reported value only; no growth estimate.',
                required_source='Comparative statement in the same filing',source_id=current['source_id']))
            if conflicts:self.flag(rid,issue,end,current['source_id'],'high')
        if rid=='cash_ppe':
            row['normalization_note']='Positive source payments are cash outflows; shown as a payment amount, not sign-flipped.'
        return row

    def derived(self, rid, label, left, right, divide=False):
        row=dict(id=rid,label=label,concept='Public Record calculation',unit='Percent' if divide else left['unit'],
                 current=None,prior=None,comparison_status='missing_required_source',evidence_label='derived_calculation',
                 formula='100 × operating income / revenue' if divide else 'Operating cash flow − cash PPE payments')
        for key in ('current','prior'):
            a,b=left.get(key),right.get(key)
            if not a or not b or a['unit']!=b['unit'] or (a['start'],a['end'],a['accession'])!=(b['start'],b['end'],b['accession']):
                continue
            if divide and b['value']<=0 or not divide and b['value']<0:
                continue
            row[key]=dict(a,value=100*a['value']/b['value'] if divide else a['value']-b['value'],
                          concept=rid,unit=row['unit'],evidence_label='derived_calculation',normalization_method='calculated',
                          formula=row['formula'],inputs=[dict(metric=left['id'],**a),dict(metric=right['id'],**b)])
        if row['current'] and row['prior']:row['comparison_status']='comparable'
        if not row['current']:row['issue']='Requires nonconflicting inputs with identical duration, currency and accession; margin denominator must be positive.'
        return row

    def section(self, specs, anchor, sid, title, kind):
        period=(None,anchor['report_period']) if kind=='instant' else self.period(specs,anchor,kind)
        rows=[self.row(spec,period,anchor,sid) for spec in specs]
        byid={r['id']:r for r in rows}
        if sid=='operating' and self.cik not in BANKS and self.cik!='0001067983':
            rows.insert(2,self.derived('operating_margin','Operating margin',byid['operating_income'],byid['revenue'],True))
        if sid=='cash_flow':
            rows.append(self.derived('cfo_less_cash_ppe','Operating cash flow less cash PPE payments',byid['cfo'],byid['cash_ppe']))
        if sid=='balance_sheet':
            vals=[byid[k]['current'] for k in ('assets','liabilities','equity')]
            if all(vals) and len({x['accession'] for x in vals})==1:
                assets,liabilities,equity=[x['value'] for x in vals]
                temporary=byid.get('temporary_equity',{}).get('current')
                rhs=liabilities+equity+(temporary['value'] if temporary else 0)
                tolerance=max(1,abs(assets)*1e-6);ok=abs(assets-rhs)<=tolerance
                self.check('balance_sheet',period[1],'Assets = liabilities + selected equity'+(' + temporary equity' if temporary else ''),assets,rhs,'pass' if ok else 'exception',vals[0]['source_id'])
                if not ok:self.flag('balance_sheet','Selected equity basis does not reconcile assets and liabilities; minority interests or presentation differences require filing review.',period[1],vals[0]['source_id'],'high')
        return dict(id=sid,title=title,period_type=kind,start=period[0],end=period[1],
                    period_label=f'{period[0]} to {period[1]}' if period[0] else 'As of '+period[1] if kind=='instant' else 'Duration unavailable; report ends '+period[1],rows=rows)

    def result(self):
        originals=[f for f in self.filings if f['form'] in ('10-K','10-Q')]
        profile,boundary=('bank','Bank-specific reported metrics: no industrial operating margin or cash-flow template; no inferred NIM, CET1 or loan-loss ratio.') if self.cik in BANKS else SPECIALISTS.get(self.cik,('operating_company','Consolidated reported metrics; no organic-growth, valuation, leverage or complete-model claim.'))
        out=dict(cik=self.cik,name=self.company['name'],profile_type=profile,boundary=boundary,anchor=None,sections=[],annual_history=[],
                 source_index=[],qa_flags=self.flags,validation_checks=self.checks,comparability_bridges=self.bridges,
                 readiness=dict(status='not_ready',readiness_effect='not_decision_ready',scope='Reported-financial screen only; not a complete valuation or credit model.'),
                 captured_at=self.captured_at,owning_workflow='dashboard-builder',artifact_role='embedded_support_artifact',
                 hidden_unless_requested=True,decision_impact='Source and comparison gaps limit financial trend interpretation.')
        if not originals:
            self.flag('anchor','No verified original periodic filing and report end are available.',severity='blocker')
            return out
        anchor=max(originals,key=lambda f:(f['report_period'],f['filed'],f['id']))
        out['anchor']={k:anchor.get(k) for k in ('form','filed','report_period','url')};out['anchor']['accession']=anchor['id']
        income=BANK_INCOME if self.cik in BANKS else [('revenue','Revenue',REVENUE.get(self.cik,()),'USD')]+COMMON_INCOME
        if self.cik=='0000070858':
            income=[('revenue','Net revenue after interest expense',('Revenues',),'USD')]+BANK_INCOME[1:]
        annual=anchor['form']=='10-K'
        out['sections'].append(self.section(income,anchor,'operating','Reported annual operations' if annual else 'Reported quarter operations','annual' if annual else 'quarter'))
        if self.cik not in BANKS:
            out['sections'].append(self.section(CASH_FLOW,anchor,'cash_flow','Reported annual cash generation' if annual else 'Reported year-to-date cash generation','annual' if annual else 'ytd'))
        bs=BALANCE+[('deposits','Deposits',('Deposits',),'USD')] if self.cik in BANKS else BALANCE
        if any(self.eligible(f,anchor['id']) and f['end']==anchor['report_period'] and not f.get('start')
               for tag in TEMPORARY_EQUITY[2] for f in self.raw(tag,'USD')):
            bs=bs+[TEMPORARY_EQUITY]
        out['sections'].append(self.section(bs,anchor,'balance_sheet','Reported balance sheet','instant'))
        annuals=sorted((f for f in originals if f['form']=='10-K'),key=lambda f:f['report_period'],reverse=True)
        seen=set()
        for filing in annuals:
            if filing['report_period'] in seen:continue
            seen.add(filing['report_period'])
            if len(seen)>5:break
            section=self.section(income,filing,'annual','Reported annual operations','annual')
            if section['start'] and any(r['current'] for r in section['rows']):
                section['anchor']={**{k:filing.get(k) for k in ('form','filed','report_period','url')},'accession':filing['id']}
                out['annual_history'].append(section)
        self.flag('coverage','Headline statements only; issuer-specific KPIs, guidance, segments, debt terms and complete cash-flow reconciliations are not normalized.',anchor['report_period'],'SEC-'+self.cik+'-'+anchor['id'],'low')
        self.check('identity',anchor['report_period'],'Payload CIK equals covered issuer CIK',self.cik,self.cik,'pass')
        out['source_index']=list(self.sources.values())
        count=sum(r['current'] is not None for sec in out['sections'] for r in sec['rows'])
        out['readiness'].update(status='partial' if count else 'not_ready',readiness_effect='screen_grade' if count else 'not_decision_ready',available_current_rows=count)
        return out


def normalize_company(payload, company, captured_at):
    """Normalize one companyfacts payload against verified submissions metadata."""
    return Normalizer(payload,company,captured_at).result()
