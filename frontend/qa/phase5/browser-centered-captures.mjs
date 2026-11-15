/** Final documentation images from actual saved API data; source/build/observation hashes retained. */
import assert from 'node:assert/strict';import fs from 'node:fs';import crypto from 'node:crypto';
import {chromium} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='docs/screenshots/centered';fs.mkdirSync(out,{recursive:true});const images=[];
const sha=path=>crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex');
const manifest=JSON.parse(fs.readFileSync('golden_cache/wise_0855/manifest.json','utf8'));
const dataPaths=['golden_cache/wise_0855/manifest.json',...manifest.epochs.map(e=>`golden_cache/wise_0855/${e.frames.all.split('/').pop()}`)];
const browser=await chromium.launch();
async function ready(page){await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));await page.waitForTimeout(100);}
async function capture(page,file,description){await page.screenshot({path:`${out}/${file}`});images.push({file,sha256:sha(`${out}/${file}`),url:page.url(),viewport:page.viewportSize(),description,data_access:'saved',is_simulated_fallback:false,source_files:dataPaths.map(path=>({path,sha256:sha(path)})),canvas_boxes:await Promise.all((await page.locator('.blink-canvas').all()).map(locator=>locator.boundingBox()))});}
for(const width of[1920,1440,1024,390,320]){
 const page=await browser.newPage({viewport:{width,height:width<500?844:1080}});await page.goto('http://127.0.0.1:5176/?source=saved&target=wise_0855');await ready(page);
 await capture(page,`workspace-${width}.png`,'Initial paused centered workspace; real saved WISE observations, historical comparison unvalidated.');
 if(width===1440){
  await page.getByRole('button',{name:'Focus image',exact:true}).click();await page.waitForTimeout(100);await capture(page,'focus-1440.png','Both secondary rails collapsed in focus mode; origin and historical-comparison limitation retained.');await page.getByRole('button',{name:'Exit focus',exact:true}).click();
  await page.locator('.task-nav').getByRole('button',{name:'Compare',exact:true}).click();await page.getByRole('button',{name:'Side by side',exact:true}).click();await ready(page);assert.equal(await page.locator('.blink-canvas').count(),2);await capture(page,'comparison-1440.png','Actual distinct saved A/B frames in a shared-camera paired comparison; no scientific validation inferred.');
 }
 if(width===390){await page.getByRole('button',{name:'Show inspector',exact:true}).click();await page.locator('[data-workspace-region="inspector"]').scrollIntoViewIfNeeded();await capture(page,'inspector-390.png','Phone inspector intentionally opened and scrolled into view; source, comparison and measurement meaning remain separate.');}
 await page.close();
}
const sourcePaths=fs.readdirSync('frontend/src',{recursive:true}).filter(p=>/\.(tsx?|css)$/.test(p)).map(p=>`frontend/src/${p.replaceAll('\\','/')}`).sort();const buildPaths=fs.readdirSync('frontend/dist/assets').map(p=>`frontend/dist/assets/${p}`).sort();const script='frontend/qa/phase5/browser-centered-captures.mjs';
const response=await browser.newContext();const schema=await(await response.request.get('http://127.0.0.1:8176/openapi.json')).json();await response.close();
fs.writeFileSync(`${out}/origins.json`,JSON.stringify({captured_at:new Date().toISOString(),browser:browser.version(),api_version:schema.info.version,scope:'Actual explicit-saved API responses and real assets; no route interception or new upstream observation acquisition',source_revision:sourcePaths.map(path=>({path,sha256:sha(path)})),build_artifacts:buildPaths.map(path=>({path,sha256:sha(path)})),capture_script:{path:script,sha256:sha(script)},images},null,2));await browser.close();console.log(JSON.stringify({images:images.map(i=>i.file),api:schema.info.version}));
