/** Automated interface checks with actual explicit-saved API products. No human-study claim. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { chromium,firefox,webkit } from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
import AxeBuilder from '../../../backend/.cache/phase5/browser-tools/node_modules/@axe-core/playwright/dist/index.mjs';
const out=path.resolve('backend/.cache/phase5/browser-matrix');fs.mkdirSync(out,{recursive:true});
const results=[];
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
const url='http://127.0.0.1:5176/?source=saved&target=wise_0855';
async function ready(page){await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));await page.waitForTimeout(150);}
async function axe(page,scene){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();return{scene,violations:r.violations.map(v=>({id:v.id,impact:v.impact,help:v.help,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),incomplete:r.incomplete.map(v=>({id:v.id,nodes:v.nodes.length}))};}
for(const [name,engine]of Object.entries({chromium,firefox,webkit})){
let browser;
try{browser=await engine.launch({headless:true});}catch(error){results.push({engine:name,unavailable:error.message});save();continue;}
for(const width of [1440,390,320]){
 const row={engine:name,version:browser.version(),width,checks:[],axe:[],errors:[]};results.push(row);
 const context=await browser.newContext({viewport:{width,height:width===1440?1000:844},hasTouch:width<500});
 const page=await context.newPage();
 page.on('pageerror',e=>row.errors.push(e.message));
 try{
  const start=Date.now();await page.goto(url);await ready(page);row.savedLoadAndDecodeMs=Date.now()-start;
  assert.equal(await page.getByRole('button',{name:'Pause',exact:true}).count(),0,'Default must be paused');row.checks.push('default_paused');
  row.layout=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,buttons:[...document.querySelectorAll('button')].filter(b=>b.getClientRects().length&&!b.disabled).map(b=>{const r=b.getBoundingClientRect();return{name:b.getAttribute('aria-label')||b.textContent.trim(),width:r.width,height:r.height};})}));
  assert.ok(row.layout.document<=width+1,'Page horizontal overflow');
  await page.screenshot({path:path.join(out,`${name}-${width}-observe.png`),fullPage:true});
  row.axe.push(await axe(page,'observe'));
  const openSearch=page.getByRole('button',{name:'Search sky or choose a target'});
  await openSearch.click();const dialog=page.getByRole('dialog');await dialog.waitFor();
  assert.equal(await page.locator('#root').evaluate(el=>el.inert),true);
  await page.keyboard.press('Shift+Tab');assert.equal(await page.evaluate(()=>!!document.activeElement?.closest('[role="dialog"]')),true);
  await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>!!document.activeElement?.closest('[role="dialog"]')),true);
  await page.getByLabel('RA (ICRS)',{exact:true}).fill('361');await page.getByLabel('Dec (ICRS)',{exact:true}).fill('0');
  await page.getByRole('button',{name:'Resolve & load'}).click();assert.equal(await page.locator('#search-ra').getAttribute('aria-invalid'),'true');
  row.axe.push(await axe(page,'search_invalid'));
  await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),0);
  assert.equal(await openSearch.evaluate(el=>document.activeElement===el),true);row.checks.push('modal_inert_focus_wrap_escape_restore','coordinate_validation');
  await page.getByRole('button',{name:'Compare',exact:true}).click();
  const a=page.getByRole('combobox',{name:'Observation A',exact:true}),b=page.getByRole('combobox',{name:'Observation B',exact:true});
  assert.notEqual(await a.inputValue(),await b.inputValue());
  await page.getByRole('button',{name:'Side by side',exact:true}).click();await ready(page);
  assert.equal(await page.locator('.blink-canvas').count(),2);row.checks.push('explicit_AB_side_by_side');
  await page.screenshot({path:path.join(out,`${name}-${width}-compare.png`),fullPage:true});
  await page.getByRole('button',{name:'Spectrum',exact:true}).first().click();await page.locator('.spectrum-counts').waitFor();
  assert.equal(await page.locator('[data-molecular-reference]').count(),0);
  const plot=page.locator('.spectrum-plot');await plot.focus();await page.keyboard.press('Home');assert.equal(await page.locator('[data-selected="true"]').count(),1);
  await page.keyboard.press('ArrowRight');assert.equal(await page.locator('[data-selected="true"]').count(),1);
  if(width<500){await page.getByRole('button',{name:'Clear selection'}).click();assert.equal(await page.locator('[data-selected="true"]').count(),0);const point=page.locator('[data-spectrum-point]').nth(20);await point.scrollIntoViewIfNeeded();const rect=await point.boundingBox();await page.touchscreen.tap(rect.x+rect.width/2,rect.y+rect.height/2);assert.equal(await page.locator('[data-selected="true"]').count(),1);}
  row.axe.push(await axe(page,'spectrum'));
  await page.screenshot({path:path.join(out,`${name}-${width}-spectrum.png`),fullPage:true});row.checks.push('spectrum_keyboard_touch_signed_discrete');
  await page.keyboard.press('Escape');await page.getByRole('button',{name:'Help',exact:true}).click();await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Shift+Tab');assert.equal(await page.evaluate(()=>!!document.activeElement?.closest('[role="dialog"]')),true);
  row.axe.push(await axe(page,'help'));await page.keyboard.press('Escape');row.checks.push('help_modal');
  await page.emulateMedia({reducedMotion:'reduce'});await page.getByRole('button',{name:'Observe',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Play blink',exact:true}).isDisabled(),true);row.checks.push('reduced_motion_disables_playback');
  assert.deepEqual(row.errors,[]);
  row.status='pass';
 }catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:path.join(out,`${name}-${width}-failure.png`),fullPage:true}).catch(()=>{});}
 await context.close();save();console.log(JSON.stringify({engine:name,width,status:row.status,failure:row.failure?.split('\n')[0],serious:row.axe.flatMap(a=>a.violations).filter(v=>['serious','critical'].includes(v.impact)).map(v=>v.id)}));
}
await browser.close();
}
