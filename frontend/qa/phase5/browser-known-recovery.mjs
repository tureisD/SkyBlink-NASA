/** Explicit recovery with unchanged real outage and fresh-known API receipts.
 * All sky/spectrum responses are isolated replay; asset bytes remain actual.
 * No upstream discovery or FITS requests are made by this browser test.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
import AxeBuilder from '../../../backend/.cache/phase5/browser-tools/node_modules/@axe-core/playwright/dist/index.mjs';
const skyPath=process.env.QA_KNOWN_SKY,spectrumPath=process.env.QA_KNOWN_SPECTRUM;
assert.ok(skyPath&&spectrumPath,'Supply unchanged same-target known sky/spectrum receipts');
const errorPath='backend/.cache/phase5/discovery-outage/rw-before-response.json';
const skyBytes=fs.readFileSync(skyPath),spectrumBytes=fs.readFileSync(spectrumPath),errorBytes=fs.readFileSync(errorPath);
const sky=JSON.parse(skyBytes),spectrum=JSON.parse(spectrumBytes),target=sky.query.target_id;
assert.equal(spectrum.target_id,target);assert.equal(sky.provenance.discovery_mode,'known');assert.equal(spectrum.provenance.discovery_mode,'known');
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
const out=process.env.QA_OUTPUT||'backend/.cache/phase5-discovery-outage/browser-known';fs.mkdirSync(out,{recursive:true});const results=[];
for(const [engineName,engine]of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();
 for(const width of[1440,320]){
  const context=await browser.newContext({viewport:{width,height:width===320?844:1080}}),page=await context.newPage();
  const row={engine:engineName,width,requests:[],spectrumRequests:[],assets:[],checks:[]};results.push(row);
  let release;const pending=new Promise(resolve=>release=resolve);
  await page.route('**/api/v1/sky?*',async route=>{
   const url=route.request().url();row.requests.push(url);
   const known=new URL(url).searchParams.get('discovery')==='known';
   if(!known)await pending;
   await route.fulfill({status:known?200:503,contentType:'application/json',body:known?skyBytes:errorBytes}).catch(()=>{});
  });
  await page.route('**/api/v1/spectrum?*',async route=>{
   row.spectrumRequests.push(route.request().url());assert.equal(new URL(route.request().url()).searchParams.get('discovery'),'known');
   await route.fulfill({status:200,contentType:'application/json',body:spectrumBytes});
  });
  await page.route('**/api/v1/assets/**',async route=>{
   const relative=new URL(route.request().url()).pathname.split('/api/v1/assets/')[1];
   const base=path.resolve('backend/.cache/live'),asset=path.resolve(base,relative);assert.ok(asset.startsWith(base+path.sep));
   const data=fs.readFileSync(asset);row.assets.push({url:relative,sha256:sha(data)});
   await route.fulfill({status:200,contentType:asset.endsWith('.webp')?'image/webp':asset.endsWith('.json')?'application/json':'application/octet-stream',body:data});
  });
  try{
   await page.goto(`http://localhost:5173/?source=archive&target=${target}`);
   await page.getByRole('button',{name:'Cancel request',exact:true}).waitFor();
   const source=page.getByRole('combobox',{name:'Data source'});const bounds=await source.boundingBox();
   assert.ok(bounds.x>=0&&bounds.x+bounds.width<=width+1);assert.equal(await source.inputValue(),'archive');
   release();await page.getByRole('button',{name:'Fetch known exposures online',exact:true}).waitFor();
   assert.ok(row.requests.every(url=>new URL(url).searchParams.get('discovery')==='live'));assert.equal(await page.locator('.blink-canvas').count(),0);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.getByRole('button',{name:'Fetch known exposures online',exact:true}).click();
   await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
   await page.waitForURL(url=>url.searchParams.get('discovery')==='known',{timeout:2000});
   assert.match(await page.locator('.workspace-heading .eyebrow').textContent(),/Known exposures \/ fresh downloads/);
   await page.locator('.task-nav').getByRole('button',{name:'Compare',exact:true}).click();await page.getByRole('button',{name:'Side by side',exact:true}).click();
   for(const epoch of sky.epochs)assert.ok((await page.locator('.observation-caption').textContent()).includes(epoch.observation_range.date_start_iso));
   await page.getByRole('button',{name:/^Comparison details/}).click();
   assert.match(await page.locator('#comparison-notification').textContent(),/no new archive search/i);
   assert.doesNotMatch(await page.locator('#comparison-notification').textContent(),/Some archive collections were unavailable/);
   await page.getByRole('button',{name:'Dismiss notification',exact:true}).click();
   const history=await page.evaluate(()=>JSON.parse(localStorage.getItem('skyblink.recent-fields.v1')||'[]'));
   assert.equal(history[0].discovery,'known');assert.deepEqual(Object.keys(history[0]).sort(),['dec','discovery','name','ra','size','source','target']);
   await page.locator('.task-nav').getByRole('button',{name:'Spectrum',exact:true}).click();await page.locator('.spectrum-counts').waitFor();
   assert.match(await page.locator('.spectrum-drawer').textContent(),/KNOWN EXPOSURES \/ FRESH DOWNLOADS/);
   assert.match(await page.locator('.spectrum-drawer').textContent(),/no new archive search/i);assert.ok(row.spectrumRequests.length);
   await page.keyboard.press('Escape');
   const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();row.axe={violations:axe.violations.map(v=>({id:v.id,impact:v.impact})),incomplete:axe.incomplete.map(v=>v.id)};
   assert.equal(row.axe.violations.length,0);assert.ok(row.requests.every(url=>new URL(url).searchParams.get('source')==='archive'));
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   row.checks.push('pending_source_fits','live_error_preserved','no_automatic_recovery','explicit_known_action','known_warning','known_history_only_settings','same_mode_spectrum','no_saved_fallback');row.status='pass';
   await page.screenshot({path:`${out}/${engineName}-${width}.png`});
  }catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:`${out}/${engineName}-${width}-failure.png`}).catch(()=>{});}
  await context.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify({scope:'Isolated unchanged real API receipts; no archive acquisition',sources:[skyPath,spectrumPath,errorPath].map(p=>({path:p,sha256:sha(fs.readFileSync(p))})),results},null,2));
  console.log(JSON.stringify({engine:engineName,width,status:row.status,failure:row.failure?.split('\n')[0]}));
 }
 await browser.close();
}
process.exitCode=results.every(row=>row.status==='pass')?0:1;
