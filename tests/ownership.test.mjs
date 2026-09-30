import test from 'node:test';
import assert from 'node:assert/strict';
import {ownershipRows,ownershipSelection,ownershipPage,ownershipOverview,ownershipCard,companyOwnership,filingOwnership} from '../site/ownership.mjs';

const cik='0000102109', accession='0001214659-26-010625';
const row=(ordinal,code,direction,table='non_derivative')=>({
  id:`${cik}:${accession}:${table}:${ordinal}`,table,ordinal,transaction_date:'2026-08-17',
  security:'Common Stock',code,direction,shares:'1200',price_per_share:'4.1208',owned_after:'21200',
  ownership:'I',ownership_nature:'By fund',footnotes:[{id:'F1',text:'Weighted average price.'}],
});
const form={cik,company:'Example Energy',tickers:['EXE'],accession,form:'4',filed:'2026-08-18',
  accepted_at:'2026-08-18T13:00:00Z',status:'ok',cached:false,
  xml_url:'https://www.sec.gov/Archives/edgar/data/102109/000121465926010625/marketforms.xml',
  filing_url:'https://www.sec.gov/Archives/edgar/data/102109/000121465926010625/xslF345X06/marketforms.xml',
  document:{owners:[{name:'Ada Buyer'},{name:'Second Owner'}],filing_plan_indicated:true,
    rows:[row(1,'P','A'),row(2,'F','D'),row(3,'S','D'),row(4,'P','A','derivative')]}};
const data={corporate:{companies:[{cik,name:'Example Energy'}]},ownership:{forms:[form]}};

test('purchase filter includes derivative and non-derivative P/A and retains filing-level owners',()=>{
  assert.equal(ownershipRows(data).length,4);
  assert.equal(ownershipSelection(data,{kind:'purchase'}).rows.length,2);
  assert.equal(ownershipSelection(data,{kind:'sale'}).rows.length,1);
  assert.equal(ownershipSelection(data,{kind:'compensation'}).rows.length,1);
  assert.equal(ownershipSelection(data,{kind:'other'}).rows.length,0);
  assert.equal(ownershipSelection(data,{cik:'other'}).rows.length,4);
  const html=ownershipCard(ownershipRows(data)[0]);
  assert.match(html,/Ada Buyer · Second Owner/);
  assert.match(html,/1,200/);
  assert.match(html,/Weighted average price/);
  assert.match(html,/Filing-level Rule 10b5-1 indicator/);
  assert.doesNotMatch(html,/open-market insider buy|\$4,944|bullish/i);
  assert.match(ownershipPage(data,{kind:'purchase'}),/Derivative table/);
});

test('reader and company views expose exact sources and explicit coverage',()=>{
  const page=ownershipPage(data,{cik,kind:'purchase'});
  assert.match(page,/2 matching rows/);
  assert.match(page,/Purchase-coded acquisitions/);
  assert.match(page,/purchase filter includes derivative and non-derivative P\/A rows/);
  assert.match(page,/private purchases/);
  assert.match(page,/not deduplicated or summed/);
  assert.match(page,/marketforms\.xml/);
  assert.match(companyOwnership(data,cik),/All selected rows/);
  assert.match(filingOwnership(data,cik,accession),/4 transaction rows/);
  const combined=filingOwnership(data,cik,accession)+companyOwnership(data,cik);
  assert.equal((combined.match(/id="ownership-/g)||[]).length,4);
  const missing={...data,ownership:{forms:[{...form,status:'metadata_only',document:null}]}};
  assert.match(filingOwnership(missing,cik,accession),/XML is unavailable/);
  assert.doesNotMatch(ownershipPage(missing),/Ada Buyer/);
  const external={...data,ownership:{forms:[{...form,status:'other_issuer',document:null,reported_issuer_cik:'0000920760'}]}};
  assert.match(ownershipPage(external),/other-issuer filings excluded/);
  assert.doesNotMatch(ownershipPage(external),/Ada Buyer/);
});

test('default reader promotes distinct issuers ahead of the row ledger',()=>{
  const older={...form,accession:'0001214659-26-010624',accepted_at:'2026-08-17T13:00:00Z'};
  const second={...form,cik:'0000000002',company:'Second Issuer',accession:'0001214659-26-010626',accepted_at:'2026-08-16T13:00:00Z'};
  const sample={...data,ownership:{forms:[older,second,form]}};
  const overview=ownershipOverview(sample);
  assert.equal((overview.match(/class="ownership-overview-item"/g)||[]).length,2);
  assert.match(overview,/Example Energy/);
  assert.match(overview,/Second Issuer/);
  assert.doesNotMatch(overview,/0001214659-26-010624/);
  const page=ownershipPage(sample);
  assert.ok(page.indexOf('Latest across issuers')<page.indexOf('Transaction rows'));
  assert.doesNotMatch(ownershipPage(sample,{kind:'purchase'}),/Latest across issuers/);
});
