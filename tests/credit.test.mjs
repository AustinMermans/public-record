import test from 'node:test';
import assert from 'node:assert/strict';
import {creditRead} from '../site/credit.mjs';

const now=Date.parse('2026-09-29T20:00:00Z');
const clock='2026-09-29T19:12:38Z';
const series=(id,observations,url='https://example.gov/'+id)=>({id,source_id:id.startsWith('OFR-')?'ofr-fsi':id.toLowerCase(),unit:id.startsWith('OFR-')?'Index points':'Percent',frequency:'Daily · not seasonally adjusted',observations,url,captured_at:clock});
const metric=(id,current,prior,annualized=false)=>({id,unit:'Percent',frequency:'Quarterly',annualized,current:{date:'2026-06-30',value:current,url:'https://fdic.gov/qbp.xlsx'},prior:{date:'2026-03-31',value:prior,url:'https://fdic.gov/qbp.xlsx'}});
function fixture(){
  const rateIds=['nyfed-sofr','nyfed-effr','ofr-fsi','fdic-qbp'];
  return {series:[
    series('NYFED-SOFR',[['2026-09-25',3.89],['2026-09-28',3.90]]),
    series('NYFED-EFFR',[['2026-09-25',3.88],['2026-09-28',3.88]]),
    series('OFR-FSI',[['2026-09-24',-2.398],['2026-09-25',-2.63]]),
    series('OFR-CREDIT',[['2026-09-24',-1.126],['2026-09-25',-1.1]])],
    sources:rateIds.map(id=>({id,status:'ok',last_success:clock})),
    banking:{status:'ok',validation:{status:'reconciled'},quarter_end:'2026-06-30',last_success:clock,metrics:[metric('noncurrent','0.93','0.98'),metric('nco','0.57','0.59',true)]}};
}
test('dated evidence table keeps separate clocks, units, exact sources and counter-direction',()=>{
  const html=creditRead(fixture(),{now});
  assert.match(html,/2\.00 bp/);assert.match(html,/\+1\.00 bp/);
  assert.match(html,/-2\.630 points/);assert.match(html,/-0\.232 points/);
  assert.match(html,/-1\.100 points/);assert.match(html,/\+0\.026 points/);
  assert.match(html,/0\.93%/);assert.match(html,/-0\.05 pp/);
  assert.match(html,/0\.57%/);assert.match(html,/-0\.02 pp/);
  assert.match(html,/Effective 2026-09-28/);assert.match(html,/Observed 2026-09-25/);assert.match(html,/Quarter ended 2026-06-30/);
  for(const source of ['NYFED-SOFR','NYFED-EFFR','OFR-FSI','OFR-CREDIT'])assert.match(html,new RegExp('https://example.gov/'+source));
  assert.match(html,/https:\/\/fdic.gov\/qbp.xlsx/);
  for(const detail of ['#funding?view=spread','#economy?series=OFR-FSI','#economy?series=OFR-CREDIT','#funding?view=banking&amp;metric=noncurrent','#funding?view=banking&amp;metric=nco'])assert.ok(html.includes(detail));
  assert.match(html,/global stress fell.*credit contribution rose.*noncurrent loans fell.*charge-off rate fell/);
  assert.match(html,/separate clocks and populations/);assert.match(html,/not a credit spread/);assert.match(html,/not reconstructed original-release vintages/);
});
test('an absent common SOFR and EFFR effective date cannot become a spread or combined read',()=>{
  const d=fixture();d.series[1].observations=[['2026-09-26',3.88],['2026-09-27',3.88]];
  const html=creditRead(d,{now});assert.match(html,/No common effective date/);assert.match(html,/A combined read is withheld/);assert.doesNotMatch(html,/2\.00 bp/);
});
test('stale retrievals suppress synthesis rather than relabel quarterly data as current-week evidence',()=>{
  const d=fixture();d.sources.find(x=>x.id==='fdic-qbp').last_success='2026-09-20T00:00:00Z';
  const html=creditRead(d,{now});assert.match(html,/retrieval older than 36 hours/);assert.match(html,/A combined read is withheld/);assert.match(html,/Quarter ended 2026-06-30/);
});
test('a fresh poll of old daily observations does not produce a latest cross-source read',()=>{
  const d=fixture();for(const s of d.series)s.observations=s.observations.map(([date,v])=>[date.replace('2026','2020'),v]);
  const html=creditRead(d,{now});assert.match(html,/daily observation older than 7 days/);assert.match(html,/A combined read is withheld/);
});
test('series source, unit and daily frequency identities are required before arithmetic',()=>{
  for(const mutate of [
    d=>{d.series[0].unit='Basis points';},
    d=>{d.series[1].source_id='fred-effr';},
    d=>{d.series[2].frequency='Monthly';},
    d=>{d.series[3].unit='Percent';}]){
    const d=fixture();mutate(d);const html=creditRead(d,{now});assert.match(html,/A combined read is withheld/);
  }
});
test('wrong FDIC period, unit, annualization or validation cannot enter the read',()=>{
  for(const mutate of [
    d=>{d.banking.metrics[0].prior.date='2026-06-30';},
    d=>{d.banking.metrics[0].unit='Count';},
    d=>{d.banking.metrics[0].annualized=true;},
    d=>{d.banking.metrics[1].annualized=false;},
    d=>{d.banking.validation.status='failed';}]){
    const d=fixture();mutate(d);const html=creditRead(d,{now});assert.match(html,/A combined read is withheld/);assert.match(html,/Quarterly comparison unavailable/);
  }
});
test('a credit component on a different date is not aligned with total OFR stress',()=>{
  const d=fixture();d.series[3].observations[1][0]='2026-09-26';
  const html=creditRead(d,{now});assert.match(html,/Aligned component unavailable/);assert.match(html,/A combined read is withheld/);
});
test('missing or malicious source URLs never create unsafe links or fabricated numbers',()=>{
  const d=fixture();d.series[0].url='javascript:alert(1)';d.banking.metrics[0].current.url='javascript:bad()';d.series[2].observations.at(-1)[1]=NaN;
  const html=creditRead(d,{now});assert.doesNotMatch(html,/href="javascript:/);assert.match(html,/Unavailable/);assert.match(html,/A combined read is withheld/);
});
