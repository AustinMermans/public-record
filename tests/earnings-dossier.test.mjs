import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {earningsDossier,dossierTeaser,dossierFor} from '../site/earnings-dossier.mjs';
import {companyPage,buildSearchIndex} from '../site/publication.mjs';
import {detailTarget} from '../site/metric-links.mjs';
import {changeEdition} from '../site/changes.mjs';

const d=JSON.parse(readFileSync(new URL('../dist/data.json',import.meta.url)));
const cik='0000320193';

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
