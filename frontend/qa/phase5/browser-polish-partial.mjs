/** Exact final fresh Epsilon Indi B response: partial discovery and no comparison reason. */
import assert from 'node:assert/strict';import fs from 'node:fs';import crypto from 'node:crypto';
import {chromium} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const source='backend/.cache/phase5/comparison-first/evidence/final/eps_indi_b-response.json',body=fs.readFileSync(source,'utf8'),sky=JSON.parse(body);
assert.equal(sky.epochs.length,1);assert.equal(sky.provenance.comparison_reason,null);assert.equal(sky.provenance.discovery_status,'partial');assert.equal(sky.provenance.missing_collections.length,3);
const out='backend/.cache/phase5-polish/partial';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch(),page=await browser.newPage({viewport:{width:390,height:844}});const requests=[];
await page.route('**/api/v1/sky?*',route=>{requests.push(route.request().url());return route.fulfill({status:200,contentType:'application/json',body});});
await page.route('**/api/v1/assets/**',async route=>{const url=new URL(route.request().url());const response=await route.fetch({url:`http://127.0.0.1:8185${url.pathname}`});await route.fulfill({response});});
await page.goto('http://127.0.0.1:5176/?source=archive&target=eps_indi_b');await page.locator('[data-live-single-epoch="1"]').waitFor();
await page.getByRole('heading',{name:'Archive search incomplete',exact:true}).waitFor();
assert.equal(await page.getByRole('button',{name:'Play blink',exact:true}).isDisabled(),true);
assert.equal(await page.getByRole('button',{name:'Try a 0.05 degree field'}).count(),0);
const before=requests.length;await page.getByRole('button',{name:'Retry comparison',exact:true}).click();await page.getByRole('heading',{name:'Archive search incomplete',exact:true}).waitFor();assert.ok(requests.length>before);assert.ok(requests.every(url=>url===requests[0]));
assert.equal(new URL(page.url()).searchParams.get('source'),'archive');
await page.screenshot({path:`${out}/real-eps-partial-mobile390.png`,fullPage:true});
fs.writeFileSync(`${out}/results.json`,JSON.stringify({status:'pass',engine:browser.version(),viewport:{width:390,height:844},source:{path:source,sha256:crypto.createHash('sha256').update(body).digest('hex'),scope:'Exact real fresh response replayed locally; actual immutable8185assets; no new discovery'},checks:['known_partial_discovery_explained_despite_null_reason','single_epoch_not_blinkable','retry_exact_archive_query','no_automatic_fallback','no_unjustified_smaller_field'],requests},null,2));await browser.close();console.log('Actual Epsilon Indi partial-discovery/no-reason recovery passes.');
