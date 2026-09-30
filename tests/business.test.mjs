import test from 'node:test';
import assert from 'node:assert/strict';
import {businessSelection,businessPage,filingStory,financialBrief,filingDetail,bindBusiness,briefFor} from '../site/business.mjs';
import {companyPage,deskPage} from '../site/publication.mjs';
import {detailTarget} from '../site/metric-links.mjs';
const filing=(id,form='8-K',overrides={})=>({id,form,filed:'2026-09-28',accepted_at:'2026-09-28T14:00:00Z',report_period:'2026-09-27',items:['2.03','9.01'],url:'https://www.sec.gov/Archives/'+id+'.htm',...overrides});
const company=(cik,name,tickers,filings)=>({cik,name,tickers,filings,status:'ok',captured_at:'2026-09-28T16:00:00Z',industry:'Software'});
const a=company('0000000001','Alpha Technologies',['ALPH'],[filing('a'),filing('b','4'),filing('c','10-Q',{items:[],filed:'2026-08-01',accepted_at:'2026-08-01T14:00:00Z'})]);
const b=company('0000000002','Beta Holdings',['BETA'],[filing('d','8-K',{items:['5.02','2.02']})]);
const d={corporate:{companies:[a,b]},sources:[],records:[],events:[],series:[]};
const point=(value,overrides={})=>({value,unit:'USD',evidence_label:'fact_source_reported',concept:'Revenue',accession:'c',url:a.filings[2].url,start:'2026-04-01',end:'2026-06-30',...overrides});
const financial=(overrides={})=>({cik:a.cik,status:'ok',captured_at:'2026-09-28T16:00:00Z',anchor:{accession:'c',url:a.filings[2].url,filed:'2026-08-01'},sections:[{id:'operating',period_type:'quarter',start:'2026-04-01',end:'2026-06-30',rows:[{id:'revenue',label:'Revenue',unit:'USD',comparison_status:'comparable',current:point(200e6),prior:point(100e6,{start:'2025-04-01',end:'2025-06-30'})}]}],...overrides});
const withFinancial=f=>({...d,financials:{companies:[f]}});
test('business search finds company identity, partial names, tickers, CIK and filing topics',()=>{
  for(const q of ['ALPH','Alpha Tech','0000000001','1'])assert.ok(businessSelection(d,{q}).companies.some(c=>c.cik===a.cik));
  assert.equal(businessSelection(d,{q:'financial obligation'}).stories[0].f.id,'a');
  assert.equal(businessSelection(d,{q:'earnings',topic:'results'}).stories.length,2);
  assert.equal(businessSelection(d,{q:'unmatched'}).stories.length,0);
});
test('default headlines preserve all business reports and exclude ownership noise; topics include secondary items',()=>{
  const state=businessSelection(d);assert.equal(state.stories.length,3);assert.ok(state.stories.every(s=>s.f.id!=='b'));
  assert.equal(businessSelection(d,{topic:'all'}).stories.length,4);
  assert.equal(businessSelection(d,{topic:'ownership'}).stories[0].f.id,'b');
  assert.equal(businessSelection(d,{topic:'results'}).stories.length,2);
  assert.equal(businessSelection(d,{topic:'governance'}).stories[0].f.id,'d');
});
test('short ticker identities and structured item/form/accession queries never match unrelated substrings',()=>{
  const visa=company('0001403161','Visa Inc.',['V'],[filing('0001403161-26-000001','8-K',{items:['5.03','9.01']})]);
  const ge=company('0000040545','GE Aerospace',['GE'],[filing('0000040545-26-000001','4',{items:[]})]);
  const data={...d,corporate:{companies:[a,b,visa,ge]}};
  assert.deepEqual(businessSelection(data,{q:'V'}).companies,[visa]);
  assert.deepEqual(businessSelection(data,{q:'GE',topic:'all'}).stories.map(s=>s.c),[ge]);
  assert.deepEqual(businessSelection(data,{q:'5.03',topic:'all'}).stories.map(s=>s.c),[visa]);
  assert.equal(businessSelection(data,{q:'Item 5.03'}).stories.length,1);
  assert.equal(businessSelection(data,{q:'10-Q'}).stories.length,1);
  assert.equal(businessSelection(data,{q:'4',topic:'all'}).stories.length,2);
  assert.equal(businessSelection(data,{q:'CIK 1'}).companies[0].cik,a.cik);
  assert.equal(businessSelection(data,{q:'0001403161-26-000001'}).stories.length,1);
  assert.equal(businessSelection(data,{q:'9999999999'}).stories.length,0);
});
test('governance items remain substantive headlines and unknown reported codes stay explicit',()=>{
  for(const code of ['3.03','5.03','5.08']) {
    const s=filingStory(a,filing('x','8-K',{items:[code,'9.01']}));
    assert.ok(s.topics.includes('governance'));assert.match(s.summary,new RegExp(code.replace('.','\\.')));
    assert.doesNotMatch(s.title,/financial statements or exhibits/);
  }
  assert.match(filingStory(a,filing('x','8-K',{items:['5.08']})).summary,/does not establish/);
  const unknown=filingStory(a,filing('x','8-K',{items:['99.01']}));
  assert.match(unknown.summary,/Reported Item 99\.01/);assert.doesNotMatch(unknown.summary,/unavailable/);
});
test('pagination is complete, bounded, and deterministic for ties; query and topic survive links',()=>{
  const many={...d,corporate:{companies:[{...a,filings:Array.from({length:27},(_,i)=>filing(String(i).padStart(3,'0')))}]}};
  assert.equal(businessSelection(many,{page:999}).page,3);
  const pages=[1,2,3].flatMap(page=>businessSelection(many,{page}).stories.slice((page-1)*12,page*12).map(s=>s.f.id));
  assert.equal(new Set(pages).size,27);
  assert.equal(businessSelection(many,{page:0}).page,1);
  const html=businessPage(many,{q:'Alpha',topic:'events',page:2});
  assert.match(html,/q=Alpha&amp;topic=events&amp;page=3/);
});
test('a single company search leads with issuer identity and filing-bound financial context',()=>{
  const html=businessPage(withFinancial(financial()),{q:'ALPH'});
  assert.ok(html.indexOf('business-spotlight')<html.indexOf('business-layout'));
  assert.match(html,/Company match · ALPH/);
  assert.match(html,/200\.00 USD mn/);
  assert.match(html,/#company\?cik=0000000001/);
  assert.doesNotMatch(businessPage(d),/business-spotlight/);
  assert.doesNotMatch(businessPage(d,{q:'8-K'}),/business-spotlight/);
  assert.equal((html.match(/business-company/g)||[]).length,0);
});
test('a source-bound earnings exhibit supplies headline and excerpt without inventing other filing news',()=>{
  const id='0000000001-26-000001',base='https://www.sec.gov/Archives/edgar/data/1/000000000126000001/';
  const f=filing(id,'8-K',{items:['2.02','9.01'],url:base+'primary.htm'}),issuer={...a,filings:[f]};
  const brief={cik:issuer.cik,accession:id,filing_url:f.url,status:'ok',headline:'Alpha reports a record quarter',excerpt:'Alpha reported quarterly cloud revenue of $2 billion.',source:{url:base+'ex991.htm'},captured_at:'2026-09-29T17:00:00Z'};
  const data={...d,corporate:{companies:[issuer]},business_briefs:{briefs:[brief]}};
  assert.equal(briefFor(data,issuer,f),brief);
  assert.match(businessPage(data,{q:'cloud'}),/Alpha reports a record quarter/);
  assert.match(businessPage(data,{q:'cloud'}),/Issuer excerpt/);
  const front=businessPage(data);
  assert.ok(front.indexOf('business-issuer-lead')<front.indexOf('business-layout'));
  assert.match(front,/From issuer results/);
  assert.match(front,/Original exhibit/);
  const reviewed={...data,earnings_dossiers:{dossiers:[{cik:issuer.cik,status:'matched',event:{accession:id},issuer_read:{claims:[{kind:'driver',text:'Cloud volume lifted the result.'}]}}]}};
  assert.match(businessPage(reviewed),/href="#company\?cik=0000000001&amp;dossier=earnings">Alpha reports a record quarter<\/a>/);
  assert.match(businessPage(reviewed),/Cloud volume lifted the result/);
  assert.doesNotMatch(businessPage(data,{q:'ALPH'}),/business-issuer-lead/);
  assert.doesNotMatch(businessPage(data,{topic:'results'}),/business-issuer-lead/);
  assert.match(filingDetail(data,issuer,id),/Headline and excerpt reproduced from the linked issuer exhibit/);
  const wrong={...data,business_briefs:{briefs:[{...brief,source:{url:'https://example.com/other.htm'}}]}};
  assert.equal(briefFor(wrong,issuer,f),null);
  assert.doesNotMatch(businessPage(wrong,{q:'Alpha'}),/record quarter/);
});
test('headlines describe source items without inventing transaction direction, annual results, or amendment outcome',()=>{
  assert.match(filingStory(a,filing('x','4')).title,/transaction report/);
  assert.doesNotMatch(filingStory(a,filing('x','4')).title,/buys|sells/i);
  assert.deepEqual(filingStory(a,filing('x','144')).topics,['ownership']);
  assert.match(filingStory(a,filing('x','144')).summary,/does not establish/);
  assert.match(filingStory(a,filing('x','8-K/A',{amendment:true})).title,/amendment/);
  assert.match(filingStory(a,filing('x','8-K',{items:['8.01','9.01']})).summary,/specific announcement/);
  assert.match(filingStory(a,filing('x','10-K',{items:[]})).summary,/Annual report/);
  assert.doesNotMatch(businessPage(d,{q:'ALPH',topic:'results'}),/Primary 8-K.*10-Q/);
});
test('financial briefs require an exact source accession and source URL and never attach old figures to an unrelated event',()=>{
  const fd=withFinancial(financial());
  assert.match(financialBrief(fd,a,a.filings[2]),/200\.00 USD mn/);
  assert.match(financialBrief(fd,a,a.filings[2]),/\+100\.0%/);
  assert.equal(financialBrief(fd,a,a.filings[0]),'');
  for(const overrides of [{accession:'wrong'},{url:'https://www.sec.gov/Archives/wrong.htm'},{evidence_label:'derived_calculation'},{unit:'EUR'},{value:NaN}]) {
    const f=financial();f.sections[0].rows[0].current=point(200e6,overrides);assert.equal(financialBrief(withFinancial(f),a),'');
  }
});
test('zero values remain visible, nonpositive priors and incompatible concepts never produce percentage changes',()=>{
  for(const value of [0,-100]) {
    const f=financial();f.sections[0].rows[0].prior=point(value);assert.doesNotMatch(financialBrief(withFinancial(f),a),/% vs/);
  }
  const f=financial();f.sections[0].rows[0].current=point(0);assert.match(financialBrief(withFinancial(f),a),/0\.00 USD mn/);
  f.sections[0].rows[0].prior=point(100,{concept:'OtherRevenue'});assert.doesNotMatch(financialBrief(withFinancial(f),a),/% vs/);
  f.status='stale';assert.match(financialBrief(withFinancial(f),a),/Stale financial capture/);
});
test('specialist financial context and successor predecessor-identity link are visible beside headline numbers',()=>{
  const successor={...a,cik:'0002115436',name:'ExxonMobil Holdings Corp',tickers:['XOM']};
  const predecessor={...b,cik:'0000034088',name:'EXXON MOBIL CORP',tickers:[]};
  const f={...financial(),cik:successor.cik,profile_type:'successor_registrant',boundary:'ExxonMobil holding-company registrant: predecessor CIK history remains separate.'};
  const data={...d,corporate:{companies:[successor,predecessor]},financials:{companies:[f]}};
  const html=businessPage(data,{q:'XOM'});
  assert.match(html,/predecessor CIK history remains separate/);
  assert.match(html,/not a spliced CIK history/);
  assert.match(html,/#company\?cik=0000034088/);
  assert.match(html,/Prior Exxon registrant/);
});
test('filing detail and share URLs retain company identity and exact accession; missing accession is explicit',()=>{
  assert.match(filingDetail(d,a,'a'),/Accession a/);
  assert.match(filingDetail(d,a,'unknown'),/outside this capture/);
  assert.match(companyPage(d,a.cik,'a'),/company-filing-detail/);
  assert.equal(detailTarget('company',new URLSearchParams('filing=a')),'company-filing-detail');
  assert.equal(detailTarget('business',new URLSearchParams('page=2')),'business-headlines');
  assert.match(deskPage(d,'business',{}, {q:'ALPH'}),/value="ALPH"/);
});
test('untrusted search/source strings are escaped, unsafe source links remain unavailable',()=>{
  const bad={...a,name:'<script>Alpha</script>',filings:[filing('bad','8-K',{url:'javascript:alert(1)'})]};
  const html=businessPage({...d,corporate:{companies:[bad]}},{q:'<img>'});
  assert.doesNotMatch(html,/<script>|<img|href="javascript:/);
  assert.doesNotMatch(filingDetail(d,bad,'bad'),/href="javascript:/);
});
test('search blur never replaces a clicked result; the persistent status and typing focus nodes survive updates',async()=>{
  const listeners={},input={value:'V'},topic={value:'reports'},status={textContent:''},results={innerHTML:'old results',dataset:{}};
  const form={isConnected:true,querySelector:selector=>selector==='#business-q'?input:topic,addEventListener:(name,fn)=>listeners[name]=fn};
  const root={querySelector:selector=>({'#business-search':form,'#business-results':results,'#business-status':status})[selector]};
  const originalHistory=globalThis.history;globalThis.history={replaceState:()=>{}};
  try {
    bindBusiness(root,d);
    listeners.change({target:{id:'business-q'},stopPropagation:()=>{}});
    assert.equal(results.innerHTML,'old results');
    input.value='ALPH';listeners.input({stopPropagation:()=>{}});
    await new Promise(resolve=>setTimeout(resolve,180));
    assert.match(status.textContent,/1 matching companies/);
    assert.doesNotMatch(results.innerHTML,/id="business-status"/);
    assert.equal(form.querySelector('#business-q'),input);
    const rendered=results.innerHTML;
    listeners.change({target:{id:'business-q'},stopPropagation:()=>{}});
    assert.equal(results.innerHTML,rendered);
    topic.value='ownership';listeners.change({target:{id:'business-topic'},stopPropagation:()=>{}});
    assert.match(status.textContent,/1 matching filings/);
  } finally {globalThis.history=originalHistory;}
});
