import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {earningsDossier,dossierTeaser,dossierFor} from '../site/earnings-dossier.mjs';
import {companyPage,buildSearchIndex} from '../site/publication.mjs';
import {detailTarget} from '../site/metric-links.mjs';
import {changeEdition} from '../site/changes.mjs';

const cik='0000320193';
const read=path=>JSON.parse(readFileSync(new URL(path,import.meta.url)));
const d={...read('../data/current.json'),corporate:read('../data/corporate/current.json'),business_briefs:read('../data/business_briefs/current.json'),financials:read('../data/financials/current.json')};
const apple=d.corporate.companies.find(c=>c.cik===cik);
const accession='0000320193-26-000018';
const filing=apple.filings.find(f=>f.id===accession);
const brief=d.business_briefs.briefs.find(b=>b.cik===cik&&b.accession===accession);
const financial=d.financials.companies.find(f=>f.cik===cik);
const section=financial.sections.find(s=>s.id==='operating'&&s.period_type==='quarter');
const figures=section.rows.filter(r=>['revenue','net_income'].includes(r.id)).map(r=>({id:r.id,label:r.label,current:r.current,prior:r.prior}));
const event={accession,filed:filing.filed,url:filing.url,headline:brief.headline,excerpt:brief.excerpt,exhibit_url:brief.source.url,captured_at:brief.captured_at};
d.earnings_dossiers={dossiers:[
  {cik,status:'matched',event,period_end:section.end,period_basis:'Issuer exhibit explicitly names the quarter end. Prior-year comparisons are presented in this 10-Q.',financial:{anchor:financial.anchor,figures,captured_at:financial.captured_at,boundary:financial.boundary,profile_type:financial.profile_type}},
  {cik:'0000789019',status:'quarter_facts_unavailable',reason:'A matching quarterly fact set from a controlling periodic filing is unavailable.',event:{accession:'microsoft-fixture',filed:'2026-07-29',url:'https://www.sec.gov/Archives/microsoft.htm',headline:'Microsoft reports fourth quarter results',excerpt:'Revenue increased.',exhibit_url:'https://www.sec.gov/Archives/microsoft-exhibit.htm',captured_at:'2026-09-29T20:00:00Z'}},
  {cik:'0001318605',status:'metadata_only',reason:'Exact issuer exhibit text was not verified.',event:{accession:'tesla-fixture',filed:'2026-07-01',url:'https://www.sec.gov/Archives/tesla.htm'}}
]};

test('source-matched Apple read exposes issuer and quarterly filing separately',()=>{
  const item=dossierFor(d,cik);
  assert.equal(item.status,'matched');
  const html=earningsDossier(d,cik);
  assert.match(html,/109\.42 USD bn versus 94\.04 USD bn/);
  assert.match(html,/Original exhibit/);
  assert.match(html,/Controlling 10-Q/);
  assert.match(html,/Issuer exhibit explicitly names the quarter end/);
  assert.match(html,/8-K filed 2026-07-30/);
  assert.match(html,/Facts captured/);
  assert.match(companyPage(d,cik),/id="company-earnings-dossier"/);
  assert.equal(detailTarget('company',new URLSearchParams('cik='+cik+'&dossier=earnings')),'company-earnings-dossier');
});

test('fallback read omits numerical join and explains absence',()=>{
  const msft=dossierFor(d,'0000789019');
  assert.equal(msft.status,'quarter_facts_unavailable');
  const html=earningsDossier(d,msft.cik);
  assert.match(html,/Figures are omitted/);
  assert.doesNotMatch(html,/earnings-table/);
  assert.match(html,/Original exhibit/);
});

test('Business and global search expose the same bounded dossier',()=>{
  const event=dossierFor(d,cik).event;
  assert.match(dossierTeaser(d,cik,event.accession),/Read earnings with filed figures/);
  assert.equal(dossierTeaser(d,cik,'unrelated-event'),'');
  assert.ok(buildSearchIndex(d).some(x=>x.url==='#company?cik='+cik+'&dossier=earnings'));
});

test('a Changes entry for the exact issuer event drills into the dossier',()=>{
  const accession=dossierFor(d,cik).event.accession;
  const row={id:'earnings-change-fixture',domain:'Companies',kind:'Newly captured document',title:'Apple result',source_id:'sec',cik,accession,date:'2026-07-30',url:'https://www.sec.gov/Archives/edgar/data/320193/example.htm',detail_url:'#company?cik='+cik+'&filing='+accession,to_capture:'2026-09-29T20:00:00Z'};
  const page=changeEdition({...d,changes:{items:[row],channels:[]}});
  assert.equal((page.match(/Filed quarterly result →/g)||[]).length,2);
  assert.match(page,/#company\?cik=0000320193&amp;dossier=earnings/);
});

test('untrusted issuer and source strings are escaped',()=>{
  const copy=structuredClone(d),item=dossierFor(copy,cik);
  item.event.headline='<script>bad()</script>';
  item.financial.figures[0].label='<img src=x onerror=bad()>';
  item.event.exhibit_url='javascript:bad()';
  const html=earningsDossier(copy,cik);
  assert.doesNotMatch(html,/<script>|<img|href="javascript:/);
  assert.match(html,/&lt;script&gt;/);
});

test('source-bound issuer read precedes tables and keeps issuer claims separate',()=>{
  const copy=structuredClone(d),item=dossierFor(copy,cik);
  item.issuer_read={status:'ok',exhibit_accession:accession,source_url:brief.source.url,
    claims:[{kind:'driver',text:'Volume drove the issuer result.',source_cue:'volume increased'},
      {kind:'outlook',text:'Issuer guidance, not realized revenue.',source_cue:'revenue guidance'}],
    question:'Will volume endure?'};
  const html=earningsDossier(copy,cik);
  assert.match(dossierTeaser(copy,cik,accession),/Read result context/);
  assert.match(html,/What matters in the issuer exhibit/);
  assert.match(html,/Operating read/);
  assert.match(html,/Issuer outlook/);
  assert.match(html,/Open question/);
  assert.match(html,/Exact EX-99\.1/);
  assert.match(html,/Source cue: “volume increased”/);
  assert.ok(html.indexOf('Volume drove')<html.indexOf('earnings-table'));
  assert.doesNotMatch(html,/Issuer highlight/);
  item.issuer_read.claims[0].text='<img src=x onerror=bad()>';
  item.issuer_read.claims[0].source_cue='<script>bad()</script>';
  assert.match(earningsDossier(copy,cik),/&lt;img/);
  assert.doesNotMatch(earningsDossier(copy,cik),/<script>/);
});

test('unreviewed and successor results disclose the editorial boundary',()=>{
  const copy=structuredClone(d),item=dossierFor(copy,cik);
  item.issuer_read_state='not_reviewed';
  assert.match(earningsDossier(copy,cik),/No reviewed operating read for this result/);
  item.issuer_read_state='successor_needs_review';
  assert.match(earningsDossier(copy,cik),/prior reviewed read is not carried forward/);
  item.issuer_read={status:'ok',exhibit_accession:accession,source_url:brief.source.url,
    claims:[{kind:'credit',text:'Credit costs were measured.',source_cue:'Credit costs'}],question:'What changes next?'};
  const html=earningsDossier(copy,cik);
  assert.match(html,/Credit watch/);
  assert.doesNotMatch(html,/prior reviewed read is not carried forward/);
});
