/** Isolated timing/failure scenarios. Delayed bodies are unchanged real saved API responses. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { chromium,firefox,webkit } from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out=path.resolve('backend/.cache/phase5/browser-requests');fs.mkdirSync(out,{recursive:true});
const results=[];const base='http://127.0.0.1:5176';
for(const[name,engine]of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();const context=await browser.newContext({viewport:{width:390,height:844}});
 const row={engine:name,checks:[]};results.push(row);
 const manifest=JSON.parse(fs.readFileSync('golden_cache/wise_0855/manifest.json','utf8'));
 const q=new URLSearchParams({source:'saved',target_id:'wise_0855',ra:String(manifest.query.ra),dec:String(manifest.query.dec),size:'.2'});
 const actual=await context.request.get(`${base}/api/v1/sky?${q}`);assert.equal(actual.status(),200);const body=await actual.body();
 row.realSavedResponseSha256=crypto.createHash('sha256').update(body).digest('hex');
 const page=await context.newPage();
 try{
  // Archive failure is injected as a failed transport, never as a made-up scientific response.
  await page.route('**/api/v1/sky?*',route=>route.abort('failed'));
  await page.goto(`${base}/?source=archive&target=wise_0855`);await page.getByRole('button',{name:'Retry request',exact:true}).waitFor();
  assert.equal(await page.getByRole('combobox',{name:'Data source'}).inputValue(),'archive');assert.equal(await page.locator('.blink-canvas').count(),0);
  await page.getByRole('button',{name:'Search sky or choose a target'}).waitFor();
  await page.screenshot({path:path.join(out,`${name}-failure.png`),fullPage:true});row.checks.push('archive_failure_keeps_navigation_no_saved_fallback');
  await page.unroute('**/api/v1/sky?*');await page.getByRole('button',{name:'Open saved WISE example'}).click();await page.locator('.blink-canvas').waitFor();row.checks.push('explicit_saved_recovery');
  // Hold every StrictMode duplicate of the same actual response until after cancel.
  let release;let gate=new Promise(resolve=>release=resolve);
  await page.route('**/api/v1/sky?*',async route=>{await gate;await route.fulfill({status:200,contentType:'application/json',body}).catch(()=>{});});
  await page.goto(`${base}/?source=saved&target=wise_0855`);await page.getByRole('button',{name:'Cancel request',exact:true}).click();
  await page.getByRole('button',{name:'Retry request',exact:true}).waitFor();release();await page.waitForTimeout(300);
  assert.equal(await page.locator('.blink-canvas').count(),0);row.checks.push('cancel_does_not_accept_late_completion');
  await page.unroute('**/api/v1/sky?*');await page.getByRole('button',{name:'Retry request',exact:true}).click();await page.locator('.blink-canvas').waitFor();row.checks.push('cancelled_request_retry');
  gate=new Promise(resolve=>release=resolve);
  await page.route('**/api/v1/sky?*',async route=>{
   if(!route.request().url().includes('target_id=wise_0855'))return route.continue();
   await gate;await route.fulfill({status:200,contentType:'application/json',body}).catch(()=>{});
  });
  await page.goto(`${base}/?source=saved&target=wise_0855`);await page.getByRole('button',{name:'Cancel request',exact:true}).waitFor();
  await page.getByRole('button',{name:'Search sky or choose a target'}).click();await page.getByRole('button',{name:/ε Indi B/}).click();
  await page.locator('.blink-canvas').waitFor();assert.match(await page.locator('.workspace-heading h1').innerText(),/Epsilon|Indi/i);
  release();await page.waitForTimeout(300);assert.match(await page.locator('.workspace-heading h1').innerText(),/Epsilon|Indi/i);row.checks.push('late_previous_target_cannot_replace_current');
  await page.unroute('**/api/v1/sky?*');
  // Spectrum cancellation uses the same transport hold, without fabricating channel values.
  let releaseSpectrum;const spectrumGate=new Promise(resolve=>releaseSpectrum=resolve);
  await page.route('**/api/v1/spectrum?*',async route=>{await spectrumGate;await route.continue().catch(()=>{});});
  await page.getByRole('button',{name:'Spectrum',exact:true}).first().click();await page.getByRole('button',{name:'Cancel spectrum request'}).click();
  await page.getByRole('button',{name:'Retry spectrum'}).waitFor();releaseSpectrum();await page.waitForTimeout(200);assert.equal(await page.locator('.spectrum-counts').count(),0);
  await page.unroute('**/api/v1/spectrum?*');await page.getByRole('button',{name:'Retry spectrum'}).click();await page.locator('.spectrum-counts').waitFor();row.checks.push('spectrum_cancel_retry');
  row.status='pass';
 }catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:path.join(out,`${name}-unexpected.png`),fullPage:true}).catch(()=>{});}
 await context.close();await browser.close();fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(row));
}
