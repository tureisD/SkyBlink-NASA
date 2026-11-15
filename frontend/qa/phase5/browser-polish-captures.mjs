/** Approved documentation screenshots: actual saved data, with file and source hashes. */
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import{chromium}from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out=path.resolve('docs/screenshots/polish');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch();const context=await browser.newContext();const images=[];
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
async function capture(page,file,target,description){const destination=path.join(out,file);await page.screenshot({path:destination});images.push({file,sha256:sha(destination),url:page.url(),description,viewport:page.viewportSize(),data_access:'saved',is_simulated_fallback:false,source_files:['manifest.json','spectrum.json'].map(name=>{const p=`golden_cache/${target}/${name}`;return{path:p,sha256:sha(p)};})});}
for(const width of[1440,390,320]){
 const page=await context.newPage();await page.setViewportSize({width,height:width===1440?1000:844});
 await page.goto('http://127.0.0.1:5176/?source=saved&target=wise_0855');await page.locator('.blink-canvas').waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));await page.waitForTimeout(150);
 await capture(page,width===1440?'workspace-desktop.png':`workspace-mobile-${width}.png`,'wise_0855','Real historical saved WISE; paused Observe workspace, unvalidated comparison explicitly labeled.');
 if(width<500){
  await page.getByRole('button',{name:'Spectrum',exact:true}).first().click();await page.locator('.spectrum-counts').waitFor();await page.locator('.spectrum-plot').scrollIntoViewIfNeeded();
  await capture(page,`spectrum-mobile-${width}.png`,'wise_0855','Real saved WISE discrete signed spectrum; responsive 13px axes, full error limits, no fitted connector.');await page.keyboard.press('Escape');
 }
 if(width===1440){
  await page.getByRole('button',{name:'Compare',exact:true}).click();await page.getByRole('button',{name:'Side by side',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
  await capture(page,'comparison-desktop.png','wise_0855','Actual saved A/B frames with shared display controls; dates and comparison limitations remain visible.');
  await page.getByRole('checkbox',{name:'Difference (B minus A)'}).check();await page.getByRole('button',{name:'Evidence',exact:true}).click();
  const captions=await page.locator('.observation-caption').allTextContents();
  assert.ok(captions.some(c=>c.includes('A:')&&c.includes('B:')),'Difference evidence must retain both dates');
  const smallFonts=await page.evaluate(()=>[...document.querySelectorAll('.rail-search,.rail-search span,.shield .switch-row > span:first-child')].map(el=>({selector:el.className,font:getComputedStyle(el).fontSize,minHeight:getComputedStyle(el).minHeight})));
  assert.ok(smallFonts.every(row=>parseFloat(row.font)>=14));
  fs.writeFileSync(path.resolve('backend/.cache/phase5-polish/browser-matrix/final-targeted-checks.json'),JSON.stringify({captions,smallFonts},null,2));
 }
 await page.close();
}
for(const target of['eps_indi_b','r_draconis']){
 const page=await context.newPage();await page.setViewportSize({width:1440,height:1000});
 await page.goto(`http://127.0.0.1:5176/?source=saved&target=${target}`);await page.locator('.blink-canvas').waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));await page.getByRole('button',{name:'Spectrum',exact:true}).first().click();await page.locator('.spectrum-counts').waitFor();
 await capture(page,target==='eps_indi_b'?'spectrum-signed.png':'spectrum-unavailable.png',target,target==='eps_indi_b'?'Actual saved Epsilon Indi spectrum retains its negative flux sample and complete error range.':'Actual saved R Draconis: all240 flux values unavailable; metadata and reasons remain accessible.');
 await page.close();
}
const health=await(await context.request.get('http://127.0.0.1:8176/api/v1/health')).json();
const sourcePaths=fs.readdirSync('frontend/src',{recursive:true}).filter(p=>/\.(tsx?|css)$/.test(p)).map(p=>`frontend/src/${p.replaceAll('\\','/')}`).sort();
const buildPaths=fs.readdirSync('frontend/dist/assets').map(p=>`frontend/dist/assets/${p}`).sort();
const captureScript='frontend/qa/phase5/browser-polish-captures.mjs';
fs.writeFileSync(path.join(out,'origins.json'),JSON.stringify({captured_at:new Date().toISOString(),browser:browser.version(),api_version:health.version,mode:'Live local API explicit saved mode; no route interception and no new observation discovery or cutouts',source_revision:sourcePaths.map(p=>({path:p,sha256:sha(p)})),build_artifacts:buildPaths.map(p=>({path:p,sha256:sha(p)})),capture_script:{path:captureScript,sha256:sha(captureScript)},images},null,2));
console.log(JSON.stringify({images:images.map(i=>i.file),api:health.version}));await browser.close();
