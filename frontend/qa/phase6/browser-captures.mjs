/** Final build documentation captures, explicit real saved observations only. */
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';import assert from 'node:assert/strict';
import {chromium} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='docs/screenshots/phase6';fs.mkdirSync(out,{recursive:true});const captures=[],bodies=new Map();
const browser=await chromium.launch();
for(const width of [1440,390,320]){
 const context=await browser.newContext({viewport:{width,height:width===1440?1000:844}}),page=await context.newPage();
 page.on('response',async response=>{if(response.url().includes('/api/v1/sky?')||response.url().includes('/api/v1/spectrum?')){const body=await response.body().catch(()=>null);if(body)bodies.set(response.url(),crypto.createHash('sha256').update(body).digest('hex'));}});
 await page.goto('http://127.0.0.1:8177/?source=saved&target=wise_0855');await page.locator('.blink-canvas').waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 const filename=`workspace-${width}.png`;await page.screenshot({path:`${out}/${filename}`});captures.push({path:`${out}/${filename}`,url:page.url(),width,height:width===1440?1000:844,source:'Explicit saved real WISE0855 revision3'});
 if(width===1440){await page.getByRole('button',{name:/^Keyboard shortcuts/}).click();await page.getByRole('dialog').waitFor();await page.screenshot({path:`${out}/shortcuts-1440.png`});captures.push({path:`${out}/shortcuts-1440.png`,url:page.url(),width,height:1000,source:'Same explicit saved observation; help overlay'});}
 await context.close();
}
await browser.close();
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const files=[];function walk(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const file=path.join(dir,entry.name);if(entry.isDirectory())walk(file);else files.push(file.replaceAll('\\','/'));}}
walk('frontend/src');walk('frontend/dist');walk('frontend/qa/phase6');
const observations=['golden_cache/wise_0855/manifest.json','golden_cache/wise_0855/spectrum.json'];
fs.writeFileSync(`${out}/origins.json`,JSON.stringify({created_at:new Date().toISOString(),scope:'Real saved observations, final production build; screenshots are UI evidence, not scientific products',captures:captures.map(item=>({...item,sha256:sha(item.path)})),source_and_build:files.map(file=>({path:file,sha256:sha(file)})),observation_sources:observations.map(file=>({path:file,sha256:sha(file)})),http_response_hashes:[...bodies].map(([url,sha256])=>({url,sha256}))},null,2));
console.log(JSON.stringify({screenshots:captures.length,source_files:files.length}));
