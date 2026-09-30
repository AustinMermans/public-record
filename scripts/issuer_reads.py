"""Publish short editorial reads only when their exact issuer exhibit still matches.

The catalogue is deliberately reviewed, not generated from arbitrary filing
text. Every factual sentence points to a hashed visible line in the retained
EX-99.1. A separately matched 10-Q supplies only its own reported facts.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from business_briefs import _checked_source, visible_lines

KINDS = {'driver', 'exception', 'outlook'}
SHA = re.compile(r'^[0-9a-f]{64}$')


def attach_issuer_reads(dossier_bundle, brief_bundle, catalogue, root):
    if catalogue.get('schema_version') != 1:
        raise ValueError('Unsupported issuer-read catalogue')
    briefs = {(b['cik'], b['accession']): b for b in brief_bundle.get('briefs', [])}
    dossiers = {d['cik']: d for d in dossier_bundle.get('dossiers', [])}
    seen = set()
    attached = 0
    for item in catalogue.get('reads', []):
        cik = item['cik']
        if cik in seen:
            raise ValueError('Duplicate issuer read: ' + cik)
        seen.add(cik)
        dossier = dossiers.get(cik)
        # A new reporting event must remove the old read from the live page.
        if not dossier or dossier.get('status') not in ('matched', 'stale_matched') or dossier['event']['accession'] != item['event_accession']:
            continue
        if dossier['period_end'] != item['period_end']:
            raise ValueError('Issuer-read period mismatch: ' + cik)
        brief = briefs.get((cik, item['event_accession']))
        if not brief or brief.get('status') not in ('ok', 'stale') or not isinstance(item.get('source_sha256'), str) or not SHA.fullmatch(item['source_sha256']):
            raise ValueError('Issuer-read source mismatch: ' + cik)
        raw = _checked_source(brief['source'], Path(root), {'.html', '.txt'})
        lines = visible_lines(raw, brief['source']['url'])
        # The SEC may recapture the same visible exhibit with different HTML
        # bytes. Allow that only when the entire normalized visible document
        # still matches the reviewed raw receipt, not merely the cited lines.
        if brief['source']['sha256'] != item['source_sha256']:
            suffix = Path(brief['source']['raw_path']).suffix
            reviewed = {'sha256': item['source_sha256'],
                        'raw_path': 'data/business_briefs/raw/' + item['source_sha256'] + suffix}
            try:
                reviewed_raw = _checked_source(reviewed, Path(root), {'.html', '.txt'})
            except (OSError, ValueError) as exc:
                raise ValueError('Reviewed issuer-read source unavailable: ' + cik) from exc
            if visible_lines(reviewed_raw, brief['source']['url']) != lines:
                raise ValueError('Issuer-read visible exhibit changed: ' + cik)
        claims = item.get('claims', [])
        if not claims or len(claims) > 3 or len({c['kind'] for c in claims}) != len(claims):
            raise ValueError('Issuer read needs one to three distinct claims: ' + cik)
        quoted_words = 0
        for claim in claims:
            if claim['kind'] not in KINDS or not isinstance(claim.get('text'), str) or not claim['text'].strip():
                raise ValueError('Invalid issuer-read claim: ' + cik)
            spans = claim.get('evidence', [])
            if not spans or len(spans) > 4:
                raise ValueError('Issuer-read claim lacks bounded evidence: ' + cik)
            for span in spans:
                ordinal, digest = span['line'], span['sha256']
                if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0 or ordinal >= len(lines) or not isinstance(digest, str) or not SHA.fullmatch(digest):
                    raise ValueError('Invalid issuer-read evidence locator: ' + cik)
                if hashlib.sha256(lines[ordinal].encode('utf-8')).hexdigest() != digest:
                    raise ValueError('Issuer-read source line changed: ' + cik)
            cue = claim.get('source_cue')
            if not isinstance(cue, str) or not cue or len(cue.split()) > 10 or not any(cue in lines[span['line']] for span in spans):
                raise ValueError('Issuer-read source cue is unsupported: ' + cik)
            quoted_words += len(cue.split())
        if quoted_words > 25:
            raise ValueError('Issuer-read source cues exceed short-quote budget: ' + cik)
        question = item.get('question')
        if not isinstance(question, str) or not question.strip() or len(question) > 240:
            raise ValueError('Issuer read needs a concise open question: ' + cik)
        dossier['issuer_read'] = dict(claims=[dict(kind=c['kind'], text=c['text'], source_cue=c['source_cue'],
                                                   evidence=c['evidence']) for c in claims],
                                      question=question, source_url=brief['source']['url'],
                                      source_sha256=brief['source']['sha256'],
                                      exhibit_accession=item['event_accession'],
                                      status=brief['status'])
        attached += 1
    dossier_bundle['issuer_reads'] = attached
    return dossier_bundle
