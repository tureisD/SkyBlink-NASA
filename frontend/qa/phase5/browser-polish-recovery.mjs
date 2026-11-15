/** Actual retained single-epoch response, unchanged; isolated routing, no new archive request. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {chromium, firefox, webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const input='backend/.cache/phase5/browser-retained-data/wise_0855-sky.json';
const body=fs.readFileSync(input,'utf8'),sky=JSON.parse(body);
const out='backend/.cache/phase5-polish/recovery';fs.mkdirSync(out,{recursive:true});
const results=[];
for(const [engineName,engine] of Object.entries({chromium,firefox,webkit})) {
 const browser=await engine.launch();
 for(const width of [1440,390,320]) {
  const context=await browser.newContext({viewport:{width,height:width===1440?1000:844}}),page=await context.newPage();
  const row={engine:engineName,width,checks:[],requests:[]};results.push(row);
  await page.route('**/api/v1/sky?*',route=>{row.requests.push(route.request().url());return route.fulfill({status:200,contentType:'application/json',body});});
  try {
   await page.goto('http://127.0.0.1:5176/?source=archive&target=wise_0855');
   await page.locator('[data-live-single-epoch="1"]').waitFor();
   assert.equal(sky.epochs.length,1);
   assert.equal(await page.getByRole('button',{name:'Play blink',exact:true}).isDisabled(),true);
   assert.match(await page.locator('.comparison-recovery').innerText(),/Some downloads did not complete/);
   assert.equal(await page.getByRole('button',{name:'Try a 0.05 degree field'}).count(),0);
   const before=row.requests.length;
   await page.getByRole('button',{name:'Retry comparison',exact:true}).click();
   await page.waitForFunction(()=>!!document.querySelector('[data-live-single-epoch="1"]'));
   await page.waitForTimeout(250);
   assert.ok(row.requests.length>before);
   assert.ok(row.requests.every(url=>url===row.requests[0]),'Retry must preserve exact archive query');
   assert.equal(new URL(page.url()).searchParams.get('source'),'archive');
   assert.ok(row.requests.every(url=>new URL(url).searchParams.get('source')==='archive'));
   await page.getByRole('button',{name:'Compare',exact:true}).click();
   assert.equal(await page.getByRole('combobox',{name:'Observation B',exact:true}).isDisabled(),true);
   assert.match(await page.getByRole('combobox',{name:'Observation B',exact:true}).textContent(),/No second epoch returned/);
   row.checks.push('unavailable_B_explicit', 'single_epoch_not_blinkable','partial_download_explained','retry_exact_archive_query','no_automatic_saved_fallback','no_unjustified_smaller_field');
   await page.locator('.blink-canvas').focus();await page.keyboard.press('/');
   await page.getByRole('dialog').waitFor();
   const recent=page.getByRole('region',{name:'Recent successful fields'});
   assert.equal(await recent.count(),1);
   await recent.locator('summary').click();
   await recent.locator('.recent-field-list button').first().click();
   await page.locator('[data-live-single-epoch="1"]').waitFor();
   assert.equal(new URL(page.url()).searchParams.get('source'),'archive');
   await page.locator('.blink-canvas').focus();await page.keyboard.press('/');
   await recent.locator('summary').click();
   await page.getByRole('button',{name:'Clear history',exact:true}).click();
   assert.equal(await recent.count(),0);
   await page.keyboard.press('Escape');
   row.checks.push('slash_search_shortcut','successful_field_history_explicit_reopen','clear_history');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   row.status='pass';
  } catch(error) {row.status='failed';row.failure=error.stack;await page.screenshot({path:path.join(out,`${engineName}-${width}-failure.png`)});}
  await context.close();fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({source:{path:input,sha256:crypto.createHash('sha256').update(body).digest('hex'),scope:'Unchanged retained real response; controlled local replay, not fresh archive acquisition'},results},null,2));
  console.log(JSON.stringify({engine:engineName,width,status:row.status,failure:row.failure?.split('\n')[0]}));
 }
 await browser.close();
}
