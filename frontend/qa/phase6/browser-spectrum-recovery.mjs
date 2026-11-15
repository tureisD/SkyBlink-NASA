/** Isolated replay of unchanged real API products; no archive queries. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
import AxeBuilder from '../../../backend/.cache/phase5/browser-tools/node_modules/@axe-core/playwright/dist/index.mjs';
const base='http://127.0.0.1:8177',out=process.env.QA_OUTPUT||'backend/.cache/phase6/spectrum-browser';fs.mkdirSync(out,{recursive:true});
const root='backend/.cache/phase6/spectrum-final';
const skyRoot='backend/.cache/phase5/recurrent-download-diagnosis/final';
const sources=new Map(),results=[];
function bytes(file){const body=fs.readFileSync(file);sources.set(file,crypto.createHash('sha256').update(body).digest('hex'));return body;}
async function task(page,name){if(!await page.locator('[data-workspace-region="fields"]').isVisible())await page.getByRole('button',{name:'Show fields',exact:true}).click();await page.locator('.task-nav').getByRole('button',{name,exact:true}).click();}
for(const [engineName,engine] of Object.entries({chromium,firefox,webkit})){
 if(process.env.QA_ENGINES&&!process.env.QA_ENGINES.split(',').includes(engineName))continue;
 const browser=await engine.launch();
 for(const width of [1440,320]){
  const context=await browser.newContext({viewport:{width,height:width===320?844:1080}}),page=await context.newPage();
  const row={engine:engineName,version:browser.version(),width,skyRequests:[],spectrumRequests:[],checks:[]};results.push(row);
  let target='rw_aurigae';
  await page.route('**/api/v1/sky?*',async route=>{row.skyRequests.push(route.request().url());await route.fulfill({status:200,contentType:'application/json',body:bytes(`${skyRoot}/${target}-response.json`)});});
  await page.route('**/api/v1/spectrum?*',async route=>{
   const url=new URL(route.request().url());row.spectrumRequests.push(url.href);
   const known=url.searchParams.get('discovery')==='known';
   await route.fulfill({status:known?200:503,contentType:'application/json',body:bytes(`${root}/${known?target+'-known':'rw_aurigae-live'}-response.json`)});
  });
  await page.route('**/api/v1/assets/**',async route=>{
   const relative=new URL(route.request().url()).pathname.split('/api/v1/assets/')[1];
   const cache=path.resolve('backend/.cache/live'),file=path.resolve(cache,relative);assert.ok(file.startsWith(cache+path.sep));
   await route.fulfill({status:200,contentType:file.endsWith('.webp')?'image/webp':file.endsWith('.json')?'application/json':'application/octet-stream',body:fs.readFileSync(file)});
  });
  try{
   await page.goto(`${base}/?source=archive&target=rw_aurigae&discovery=live`);await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
   await page.evaluate(()=>window.__spectrumImageCanvas=document.querySelector('.blink-canvas'));
   const skyCount=row.skyRequests.length;
   await task(page,'Spectrum');await page.getByRole('button',{name:'Fetch known spectrum online',exact:true}).waitFor();
   assert.equal(await page.locator('.spectrum-counts').count(),0);assert.ok(row.spectrumRequests.every(url=>new URL(url).searchParams.get('discovery')==='live'));
   await page.getByRole('button',{name:'Fetch known spectrum online',exact:true}).click();await page.locator('.spectrum-counts').waitFor();
   await page.waitForURL(url=>url.searchParams.get('spectrumDiscovery')==='known',{timeout:2000});
   assert.equal(new URL(page.url()).searchParams.get('discovery'),'live');assert.equal(row.skyRequests.length,skyCount);
   assert.match(await page.locator('.spectrum-counts').innerText(),/Fetched 7 samples; 0 recorded eligible/);
   assert.match(await page.locator('.spectrum-drawer').innerText(),/image keeps its own discovery mode/);
   assert.equal(await page.locator('[data-spectrum-point]').count(),7);assert.equal(await page.locator('.spectrum-plot path').count(),0);
   assert.equal(await page.getByRole('button',{name:'Fetch known spectrum online',exact:true}).count(),0);
   assert.equal(await page.evaluate(()=>window.__spectrumImageCanvas===document.querySelector('.blink-canvas')),true);
   const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();row.axe=audit.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}));assert.equal(row.axe.length,0);
   await page.screenshot({path:`${out}/${engineName}-${width}-rw-spectrum.png`});
   await page.keyboard.press('Escape');assert.match(await page.locator('.workspace-heading .eyebrow').innerText(),/Archive/i);
   const history=await page.evaluate(()=>JSON.parse(localStorage.getItem('skyblink.recent-fields.v1')));assert.equal(history[0].discovery,'live');assert.equal(history[0].spectrumDiscovery,'known');
   const restored=page.url();await page.goto(restored);await page.locator('.blink-canvas').first().waitFor();await task(page,'Spectrum');await page.locator('.spectrum-counts').waitFor();
   assert.equal(new URL(row.spectrumRequests.at(-1)).searchParams.get('discovery'),'known');
   row.checks.push('real_live_error','explicit_spectrum_only_recovery','no_sky_reload','image_canvas_preserved','finite_excluded_success','native_samples_not_connected','distinct_modes_share_history_restore');
   await page.keyboard.press('Escape');target='r_draconis';
   await page.goto(`${base}/?source=archive&target=${target}&discovery=live&spectrumDiscovery=known`);await page.locator('.blink-canvas').first().waitFor();await task(page,'Spectrum');await page.locator('.spectrum-counts').waitFor();
   assert.match(await page.locator('.spectrum-counts').innerText(),/Fetched 3 samples; 0 recorded eligible/);assert.match(await page.locator('.spectrum-banner').innerText(),/All recorded flux values are unavailable/);
   assert.equal(await page.locator('.spectrum-plot').count(),0);assert.equal(await page.getByRole('button',{name:'Retry spectrum',exact:true}).count(),0);await page.screenshot({path:`${out}/${engineName}-${width}-null-spectrum.png`});row.checks.push('real_all_null_success_not_transport_failure');
   await page.keyboard.press('Escape');target='wise_0855';
   await page.goto(`${base}/?source=archive&target=${target}&discovery=live&spectrumDiscovery=known`);await page.locator('.blink-canvas').first().waitFor();await task(page,'Spectrum');await page.locator('.spectrum-counts').waitFor();
   assert.match(await page.locator('.spectrum-counts').innerText(),/Fetched 4 samples; 4 recorded eligible/);assert.equal(await page.locator('[data-spectrum-point]').count(),4);row.checks.push('real_eligible_sparse_spectrum');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));row.status='pass';
  }catch(error){row.status='failed';row.error=error.stack;await page.screenshot({path:`${out}/${engineName}-${width}-failure.png`}).catch(()=>{});}
  await context.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify({scope:'Unchanged actual retained API bodies and assets, isolated browser routes',sources:[...sources].map(([path,sha256])=>({path,sha256})),results},null,2));console.log(JSON.stringify({engine:engineName,width,status:row.status,error:row.error?.split('\n')[0]}));
 }
 await browser.close();
}
process.exitCode=results.every(row=>row.status==='pass')?0:1;
