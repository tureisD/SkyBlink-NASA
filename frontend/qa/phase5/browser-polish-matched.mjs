/** Playback of the exact fresh method-12 Barnard API response; no additional discovery. */
import assert from 'node:assert/strict';import fs from 'node:fs';import crypto from 'node:crypto';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const source='backend/.cache/phase5/comparison-first/evidence/barnards_star-response.json';
const body=fs.readFileSync(source,'utf8'),sky=JSON.parse(body);
const out='backend/.cache/phase5-polish/matched';fs.mkdirSync(out,{recursive:true});const results=[];
assert.equal(sky.provenance.processing_version,'matched_image_comparison/12');
assert.equal(sky.provenance.comparison_status,'matched_visual');assert.equal(sky.epochs.length,2);
for(const [name,engine] of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();
 for(const width of [1440,390,320]){
  const context=await browser.newContext({viewport:{width,height:width===1440?1000:844}}),page=await context.newPage();const row={engine:name,width,assetRequests:[]};results.push(row);
  await page.route('**/api/v1/sky?*',route=>route.fulfill({status:200,contentType:'application/json',body}));
  await page.route('**/api/v1/assets/**',async route=>{const u=new URL(route.request().url());row.assetRequests.push(u.pathname);const response=await route.fetch({url:`http://127.0.0.1:8185${u.pathname}`});await route.fulfill({response});});
  try{
   await page.goto('http://127.0.0.1:5176/?source=archive&target=barnards_star');
   await page.locator('.blink-canvas').waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
   const play=page.getByRole('button',{name:'Play blink',exact:true});assert.equal(await play.isEnabled(),true);await play.click();await page.getByRole('button',{name:'Pause',exact:true}).click();
   await page.getByRole('button',{name:'Compare',exact:true}).click();
   const a=page.getByRole('combobox',{name:'Observation A',exact:true}),b=page.getByRole('combobox',{name:'Observation B',exact:true});
   assert.equal(await b.isEnabled(),true);assert.notEqual(await a.inputValue(),await b.inputValue());
   await page.getByRole('button',{name:'Side by side',exact:true}).click();assert.equal(await page.locator('.blink-canvas').count(),2);
   const urls=sky.epochs.map(e=>e.frames.all);assert.notEqual(urls[0],urls[1]);
   row.frameSha256=[];for(const url of urls){assert.ok(row.assetRequests.includes(url));const r=await context.request.get(`http://127.0.0.1:8185${url}`);assert.equal(r.status(),200);row.frameSha256.push(crypto.createHash('sha256').update(await r.body()).digest('hex'));}assert.notEqual(row.frameSha256[0],row.frameSha256[1]);
   const difference=page.getByRole('checkbox',{name:'Difference (B minus A)'});assert.equal(await difference.isEnabled(),true);await difference.check();
   await page.waitForFunction(()=>!document.querySelector('.canvas-status'));assert.ok(await difference.isChecked());
   row.checks=['real_method12_pair','play_pause_enabled','distinct_A_B_selection_and_actual_asset_bytes','side_by_side','difference_enabled'];row.status='pass';
  }catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:`${out}/${name}-${width}-failure.png`});}
  await context.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify({source:{path:source,sha256:crypto.createHash('sha256').update(body).digest('hex'),scope:'Exact fresh API response played back by isolated routing; actual assets on8185; no new discovery'},results},null,2));console.log(JSON.stringify({engine:name,width,status:row.status,failure:row.failure?.split('\n')[0]}));
 }
 await browser.close();
}
