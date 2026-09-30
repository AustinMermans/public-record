import test from 'node:test';
import assert from 'node:assert/strict';
import {archivedPceModel,pceReleaseState,pceReleasePage,pceReleaseTeaser} from '../site/pce-releases.mjs';

const july={target:'2026-07',published_at:'2026-08-26',embargo_at:'2026-08-26T12:30:00+00:00',
  values:{headline_mom:0.2,core_mom:0.2,headline_yoy:3.7,core_yoy:3.3},
  display_values:{headline_mom:'0.2',core_mom:'0.2',headline_yoy:'3.7',core_yoy:'3.3'},
  url:'https://www.bea.gov/news/2026/personal-income-and-outlays-july-2026',
  captured_at:'2026-09-29T20:00:00+00:00',sha256:'a'.repeat(64),source_locator:'News Release body'};
const bundle={status:'ok',last_success:'2026-09-29T20:00:00+00:00',releases:[july],
  scheduled:[{target:'2026-08',date:'2026-09-30',title:'Personal Income and Outlays, August 2026'}]};
const sample={bea_pce:bundle,inflation:{history:[
  {captured_at:'2026-09-29T23:56:16+00:00',rows:[{basis:'mom',target:'2026-08',updated_on:'2026-09-29',values:{pce:'0.34',core_pce:'0.27'}}]},
  {captured_at:'2026-09-30T13:45:00+00:00',rows:[{basis:'mom',target:'2026-08',updated_on:'2026-09-30',values:{pce:'0.40',core_pce:'0.32'}}]}
]}};

test('dated release state keeps pending August separate from published July',()=>{
  const state=pceReleaseState(bundle);
  assert.deepEqual(state.targets,['2026-08','2026-07']);
  assert.equal(state.latest,'2026-07');
  assert.equal(state.byTarget.has('2026-08'),false);
  const html=pceReleasePage(sample,'2026-08');
  assert.match(html,/No verified BEA actual yet/);
  assert.match(html,/headline <strong>0\.40%<\/strong>, core <strong>0\.32%/);
  assert.doesNotMatch(html,/0\.40% headline<\/strong> PCE inflation/);
});

test('pre-release model comparison uses only retained snapshots before embargo',()=>{
  const august={...july,target:'2026-08',published_at:'2026-09-30',embargo_at:'2026-09-30T12:30:00+00:00',
    values:{headline_mom:0.3,core_mom:0.2,headline_yoy:3.8,core_yoy:3.4},
    display_values:{headline_mom:'0.3',core_mom:'0.2',headline_yoy:'3.8',core_yoy:'3.4'}};
  const model=archivedPceModel(sample.inflation,'2026-08',august.embargo_at);
  assert.equal(model.pce,0.34);
  assert.equal(model.core,0.27);
  const html=pceReleasePage({...sample,bea_pce:{...bundle,releases:[july,august],scheduled:[]}},'2026-08');
  assert.match(html,/Cleveland Fed pre-release model: <strong>0\.34%/);
  assert.doesNotMatch(html,/Cleveland Fed pre-release model: <strong>0\.40%/);
  assert.match(html,/Less than 0\.1 pp apart at the published precision/);
  assert.match(html,/Exact BEA release/);
});

test('July actual has no invented historical model vintage and links to its BEA source',()=>{
  const html=pceReleasePage(sample,'2026-07');
  assert.match(html,/0\.2% headline/);
  assert.match(html,/3\.7% <span>from the same month one year earlier/);
  assert.match(html,/No verified pre-release Cleveland Fed snapshot/);
  assert.match(html,/aria-label="July 2026 published BEA PCE price results"/);
  assert.match(html,/<h2><span class="sr-only">Headline PCE: <\/span>0\.2/);
  assert.match(html,/<h2><span class="sr-only">Excluding food &amp; energy: <\/span>0\.2/);
  assert.match(html,/https:\/\/www\.bea\.gov\/news\/2026\/personal-income-and-outlays-july-2026/);
  assert.match(pceReleaseTeaser(sample),/#pce-releases\?target=2026-07/);
});

test('invalid release values and unsafe links do not become actuals',()=>{
  const state=pceReleaseState({...bundle,releases:[{...july,url:'javascript:alert(1)'},{...july,values:{...july.values,core_yoy:Infinity}}]});
  assert.equal(state.latest,null);
  const html=pceReleasePage({bea_pce:{...bundle,releases:[]}},'2026-07');
  assert.doesNotMatch(html,/Exact BEA release/);
});

test('negative model gap does not round to false zero',()=>{
  const august={...july,target:'2026-08',published_at:'2026-09-30',embargo_at:'2026-09-30T12:30:00+00:00',
    values:{...july.values,headline_mom:0.4},display_values:{...july.display_values,headline_mom:'0.4'}};
  const history=[{captured_at:'2026-09-29T23:56:16+00:00',rows:[{basis:'mom',target:'2026-08',updated_on:'2026-09-29',values:{pce:'0.25',core_pce:'0.27'}}]}];
  const html=pceReleasePage({...sample,inflation:{history},bea_pce:{...bundle,releases:[august],scheduled:[]}},'2026-08');
  assert.match(html,/Model about 0\.2 pp below the published actual/);
  assert.doesNotMatch(html,/0\.0 pp model/);
});
