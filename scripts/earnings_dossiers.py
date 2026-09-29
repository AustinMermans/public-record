"""Join SEC issuer-result exhibits to filing-anchored quarterly facts, or fail closed.

This is a build-time interpretation of already validated captures, not a new
collector. The exhibit supplies the period identity; the periodic filing
supplies the numerical facts. Neither a shared company name nor nearby dates
alone establish that both documents cover the same result.
"""
from __future__ import annotations

import re
import math
from datetime import date, datetime
from pathlib import Path

from business_briefs import _checked_source, visible_lines

ORDINAL = {'first': 'Q1', 'second': 'Q2', 'third': 'Q3', 'fourth': 'Q4'}
DATE = r'([A-Z][a-z]+ \d{1,2}, 20\d{2})'
EXPLICIT_END = (
    re.compile(r'\b(?:financial )?results for (?:its |the )?(?:fiscal )?(?:20\d{2} )?(?:first|second|third|fourth) quarter ended '+DATE, re.I),
    re.compile(r'\b(?:following )?results for (?:the )?quarter ended '+DATE, re.I),
    re.compile(r'\brevenue for (?:the )?(?:fiscal )?(?:first|second|third|fourth) quarter ended '+DATE, re.I),
    re.compile(r'\bOperating Review\s*[–—-]\s*Three Months Ended '+DATE, re.I),
)


def quarter_identity(headline):
    """Only an issuer result headline with an explicit fiscal quarter and year."""
    if not isinstance(headline, str) or not re.search(r'\b(results|earnings|financial)\b', headline, re.I):
        return None
    text=re.sub(r'[-–—]', ' ', headline).lower()
    patterns=(r'\b(first|second|third|fourth)\s+quarter\s+(?:fiscal\s+)?(20\d{2})\b',
              r'\bq([1-4])\s+(20\d{2})\b',
              r'\bfiscal\s+(20\d{2})\s+(first|second|third|fourth)\s+quarter\b',
              r'\b(20\d{2})\s+(first|second|third|fourth)\s+quarter\b')
    for index,pattern in enumerate(patterns):
        match=re.search(pattern,text)
        if not match:continue
        if index==1:return int(match[2]),'Q'+match[1]
        if index>=2:return int(match[1]),ORDINAL[match[2]]
        return int(match[2]),ORDINAL[match[1]]
    return None


def exhibit_period(brief, root):
    if brief.get('status') not in ('ok','stale') or not brief.get('source'):
        return None,None,False
    raw=_checked_source(brief['source'],Path(root),{'.html','.txt'})
    lines=visible_lines(raw,brief['source']['url'])
    # Lead statements precede long financial tables. The special Operating
    # Review heading is a publisher-labelled period, not a sales-volume period.
    ends=set()
    for line in lines[:45]:
        for pattern in EXPLICIT_END:
            match=pattern.search(line)
            if match:
                ends.add(datetime.strptime(match[1],'%B %d, %Y').date().isoformat())
    return (next(iter(ends)) if len(ends)==1 else None),quarter_identity(brief.get('headline')),len(ends)>1


def _date_gap(later, earlier):
    return (date.fromisoformat(later)-date.fromisoformat(earlier)).days


def _fact(point, anchor, start, end):
    return (isinstance(point,dict) and point.get('evidence_label')=='fact_source_reported'
            and isinstance(point.get('value'),(int,float)) and not isinstance(point.get('value'),bool)
            and math.isfinite(point['value'])
            and point.get('accession')==anchor['accession'] and point.get('url')==anchor['url']
            and point.get('unit')=='USD' and point.get('start')==start and point.get('end')==end)


def _figures(financial, anchor, section):
    result=[]
    for row in section.get('rows',[]):
        if row.get('id') not in ('revenue','net_income'):continue
        current=row.get('current')
        if not _fact(current,anchor,section.get('start'),section['end']):continue
        prior=row.get('prior')
        comparable=(row.get('comparison_status')=='comparable' and isinstance(prior,dict)
                    and _fact(prior,anchor,prior.get('start'),prior.get('end'))
                    and prior.get('concept')==current.get('concept')
                    and prior.get('start') and prior.get('end')
                    and 330<=_date_gap(section['end'],prior['end'])<=400
                    and 75<=_date_gap(prior['end'],prior['start'])<=105)
        result.append(dict(id=row['id'],label=row['label'],concept=current['concept'],unit='USD',
                           current={key:current[key] for key in ('value','start','end','accession','url')},
                           prior={key:prior[key] for key in ('value','start','end','accession','url')} if comparable else None))
    return result


def assemble_dossiers(corporate, briefs, financials, root):
    by_brief={(b['cik'],b['accession']):b for b in briefs.get('briefs',[])}
    by_financial={f['cik']:f for f in financials.get('companies',[])}
    result=[]
    for company in corporate.get('companies',[]):
        cik=company['cik']
        events=[f for f in company.get('filings',[]) if f.get('form')=='8-K' and not f.get('amendment') and '2.02' in f.get('items',[])]
        events.sort(key=lambda f:(f.get('accepted_at') or f['filed'],f['id']),reverse=True)
        entry=dict(cik=cik,company=company['name'],ticker=(company.get('tickers') or [None])[0],
                   status='no_selected_event',event=None,period_end=None,period_basis=None,
                   financial=None,reason='No Item 2.02 earnings event in the bounded selected filings.')
        if not events:
            result.append(entry);continue
        event=events[0]
        brief=by_brief.get((cik,event['id']))
        entry['event']=dict(accession=event['id'],filed=event['filed'],report_date=event.get('report_period'),
                            accepted_at=event.get('accepted_at'),url=event['url'],
                            headline=brief.get('headline') if brief else None,
                            excerpt=brief.get('excerpt') if brief else None,
                            exhibit_url=brief.get('source',{}).get('url') if brief and brief.get('source') else None,
                            brief_status=brief.get('status') if brief else 'unavailable',
                            captured_at=brief.get('captured_at') if brief else None)
        if not brief or brief.get('status') not in ('ok','stale'):
            entry.update(status='metadata_only',reason='Exact issuer exhibit text was not verified for this selected event.')
            result.append(entry);continue
        explicit_end,identity,ambiguous_end=exhibit_period(brief,root)
        if ambiguous_end:
            entry.update(status='period_unverified',reason='The issuer exhibit presents conflicting quarter-end dates in its lead statements.')
            result.append(entry);continue
        financial=by_financial.get(cik)
        anchor=financial.get('anchor') if financial else None
        section=next((s for s in financial.get('sections',[]) if s.get('id')=='operating' and s.get('period_type')=='quarter'),None) if financial else None
        if not anchor or not section or financial.get('status') not in ('ok','stale'):
            entry.update(status='quarter_facts_unavailable',reason='A matching quarterly fact set from a controlling periodic filing is unavailable.')
            result.append(entry);continue
        anchor_filing=next((f for f in company['filings'] if f['id']==anchor['accession'] and f['url']==anchor['url'] and f['form']=='10-Q' and not f.get('amendment')),None)
        source_base=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/'
        if not anchor_filing or not anchor['url'].startswith(source_base) or anchor['report_period']!=section.get('end') or anchor_filing.get('report_period')!=section['end']:
            entry.update(status='period_unverified',reason='The periodic filing identity or quarterly period could not be verified for this CIK.')
            result.append(entry);continue
        if not (0<=_date_gap(event['filed'],section['end'])<=80 and -7<=_date_gap(anchor['filed'],event['filed'])<=45):
            entry.update(status='period_unverified',reason='The issuer event and periodic filing are not in a defensible reporting sequence.')
            result.append(entry);continue
        period_basis=None
        labels={(p.get('fy'),p.get('fp')) for row in section.get('rows',[]) for p in (row.get('current'),) if isinstance(p,dict) and _fact(p,anchor,section.get('start'),section['end'])}
        if identity and labels and labels!={identity}:
            entry.update(status='period_mismatch',reason='Issuer fiscal-quarter label does not match the periodic filing facts.')
            result.append(entry);continue
        if explicit_end:
            if explicit_end!=section['end']:
                entry.update(status='period_mismatch',period_end=explicit_end,
                             reason='The issuer exhibit names a different quarter end from the periodic filing.')
                result.append(entry);continue
            period_basis='Issuer exhibit explicitly names the quarter end.'
        elif identity:
            if not labels:
                entry.update(status='quarter_facts_unavailable',reason='No source-reported quarterly fact carries a fiscal-quarter label for this match.')
                result.append(entry);continue
            period_basis='Issuer exhibit headline and SEC fact fiscal year/quarter match.'
        else:
            entry.update(status='period_unverified',reason='The issuer exhibit does not establish a compatible quarter identity.')
            result.append(entry);continue
        figures=_figures(financial,anchor,section)
        if not figures:
            entry.update(status='quarter_facts_unavailable',period_end=section['end'],period_basis=period_basis,
                         reason='The quarter is identified, but source-reported comparable financial measures are unavailable.')
            result.append(entry);continue
        entry.update(status='matched' if all(x=='ok' for x in (company.get('status'),brief['status'],financial['status'])) else 'stale_matched',
                     reason='Quarter identity verified against the issuer exhibit and controlling periodic filing.',
                     period_end=section['end'],period_basis=period_basis+' Prior-year comparisons are presented in this 10-Q, not reconstructed from the original prior-year filing.',
                     financial=dict(anchor=anchor,start=section.get('start'),end=section['end'],figures=figures,
                                    captured_at=financial.get('last_success') or financial.get('captured_at'),
                                    status=financial['status'],profile_type=financial.get('profile_type'),
                                    boundary=financial.get('boundary')))
        result.append(entry)
    return dict(coverage=len(result),matched=sum(x['status']=='matched' for x in result),
                stale_matched=sum(x['status']=='stale_matched' for x in result),dossiers=result)
