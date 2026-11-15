/** Real saved observations; measured layout and persistent-canvas regression checks. */
import assert from 'node:assert/strict';import fs from 'node:fs';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
import AxeBuilder from '../../../backend/.cache/phase5/browser-tools/node_modules/@axe-core/playwright/dist/index.mjs';
const out=process.env.QA_OUTPUT||'backend/.cache/phase5-centered/matrix';fs.mkdirSync(out,{recursive:true});const results=[];
async function settled(page){await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));await page.waitForTimeout(100);}
async function geometry(page){return page.evaluate(()=>{const rect=selector=>{const e=document.querySelector(selector);if(!e||!e.getClientRects().length)return null;const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height};};return{viewport:{width:innerWidth,height:innerHeight},documentWidth:document.documentElement.scrollWidth,fields:rect('[data-workspace-region="fields"]'),stage:rect('[data-workspace-region="stage"]'),inspector:rect('[data-workspace-region="inspector"]'),canvas:rect('.blink-canvas')};});}
async function axe(page,scene){const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();return{scene,violations:a.violations.map(v=>({id:v.id,impact:v.impact,help:v.help,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),incomplete:a.incomplete.map(v=>({id:v.id,nodes:v.nodes.length}))};}
for(const [engineName,engine]of Object.entries({chromium,firefox,webkit})){
 if(process.env.QA_ENGINES&&!process.env.QA_ENGINES.split(',').includes(engineName))continue;
 const browser=await engine.launch();
 for(const width of(process.env.QA_WIDTHS?process.env.QA_WIDTHS.split(',').map(Number):[1440,1920,1024,390,320])){
  const context=await browser.newContext({viewport:{width,height:width<500?844:1080},hasTouch:width<500}),page=await context.newPage();
  const row={engine:engineName,version:browser.version(),width,checks:[],axe:[],errors:[],skyRequests:[]};results.push(row);
  page.on('pageerror',e=>row.errors.push(e.message));page.on('request',r=>{if(r.url().includes('/api/v1/sky?'))row.skyRequests.push(r.url());});
  try{
   await page.goto('http://127.0.0.1:5176/?source=saved&target=wise_0855');await settled(page);
   const fields=page.locator('[data-workspace-region="fields"]'),stage=page.locator('[data-workspace-region="stage"]'),inspector=page.locator('[data-workspace-region="inspector"]');
   row.initial=await geometry(page);assert.ok(row.initial.documentWidth<=width+1,'Page overflow');
   const {canvas,stage:s}=row.initial;assert.ok(Math.abs(canvas.x+canvas.width/2-s.x-s.width/2)<=2,'Canvas centered within stage');assert.ok(canvas.y<row.initial.viewport.height,'Image starts in first screen');
   if(width>=1280){assert.ok(row.initial.fields&&row.initial.inspector);assert.ok(s.width>row.initial.fields.width&&s.width>row.initial.inspector.width,'Center stage wider than either rail');assert.ok(row.initial.fields.x+row.initial.fields.width<=s.x+1);assert.ok(s.x+s.width<=row.initial.inspector.x+1);}
   if(width<1000){assert.equal(row.initial.fields,null);assert.equal(row.initial.inspector,null);}
   await page.evaluate(()=>window.__centeredCanvas=document.querySelector('.blink-canvas'));
   row.axe.push(await axe(page,'initial_workspace'));await page.screenshot({path:`${out}/${engineName}-${width}-initial.png`});
   await page.getByRole('button',{name:'Focus image',exact:true}).click();await page.waitForTimeout(100);row.focus=await geometry(page);
   assert.equal(row.focus.fields,null);assert.equal(row.focus.inspector,null);assert.ok(row.focus.canvas.width>=canvas.width-1);
   assert.ok(await page.locator('.workspace-heading .eyebrow').isVisible());assert.match(await page.locator('.workspace-heading .eyebrow').innerText(),/Saved real observations/);
   assert.ok(await page.locator('.comparison-summary').isVisible());assert.match(await page.locator('.comparison-summary').innerText(),/Historical comparison: unvalidated/);
   assert.equal(await page.evaluate(()=>window.__centeredCanvas===document.querySelector('.blink-canvas')),true);
   await page.getByRole('button',{name:'Exit focus',exact:true}).click();
   if(!await fields.isVisible())await page.getByRole('button',{name:'Show fields',exact:true}).click();
   assert.ok(await fields.isVisible());assert.equal(await fields.getByRole('combobox',{name:'Data source'}).inputValue(),'saved');
   row.axe.push(await axe(page,'fields_open'));
   await page.getByRole('button',{name:'Close fields panel',exact:true}).click();assert.equal(await fields.isVisible(),false);assert.equal(await page.locator('#fields-toggle').evaluate(e=>document.activeElement===e),true);
   if(!await inspector.isVisible())await page.getByRole('button',{name:'Show inspector',exact:true}).click();
   await inspector.getByRole('button',{name:'Evidence inspector',exact:true}).click();assert.match(await inspector.locator('.quality-dimensions').innerText(),/Origin[\s\S]*Comparison[\s\S]*Measurement[\s\S]*Validation scope/);
   await inspector.getByRole('button',{name:'Display inspector',exact:true}).click();await inspector.getByRole('button',{name:'Evidence inspector',exact:true}).click();
   await page.getByRole('button',{name:'Close inspector panel',exact:true}).click();assert.equal(await inspector.isVisible(),false);assert.equal(await page.locator('#inspector-toggle').evaluate(e=>document.activeElement===e),true);
   assert.equal(await page.evaluate(()=>window.__centeredCanvas===document.querySelector('.blink-canvas')),true);
   row.checks.push('actual_layout_geometry','image_in_first_screen','center_stage_dominance','focus_retains_source_and_warning','rails_close_restore_focus','inspector_quality_dimensions','canvas_persists_through_layout');
   await page.getByRole('button',{name:'Play blink',exact:true}).click();
   row.blink=await page.evaluate(async()=>{const frames=new Set();for(let i=0;i<10;i++){frames.add(document.querySelector('.blink-canvas').toDataURL());await new Promise(resolve=>setTimeout(resolve,90));}return{uniqueCanvasRenders:frames.size,sameCanvas:window.__centeredCanvas===document.querySelector('.blink-canvas')};});
   assert.ok(row.blink.uniqueCanvasRenders>1,'Playback paints distinct real frames');assert.ok(row.blink.sameCanvas);await page.getByRole('button',{name:'Pause',exact:true}).click();
   await stage.locator('.task-nav').getByRole('button',{name:'Compare',exact:true}).click();const a=page.getByRole('combobox',{name:'Observation A',exact:true}),b=page.getByRole('combobox',{name:'Observation B',exact:true});assert.notEqual(await a.inputValue(),await b.inputValue());
   await page.getByRole('button',{name:'Side by side',exact:true}).click();await settled(page);assert.equal(await page.locator('.blink-canvas').count(),2);
   await page.getByRole('checkbox',{name:'Difference (B minus A)'}).check();await settled(page);assert.ok(await page.getByRole('checkbox',{name:'Difference (B minus A)'}).isChecked());
   row.checks.push('blink_changes_pixels_without_canvas_remount','explicit_AB','paired_canvas','difference');
   const search=page.getByRole('button',{name:'Search sky or choose a target'});await search.click();await page.getByRole('dialog').waitFor();assert.ok(await page.locator('#root').evaluate(e=>e.inert));await page.keyboard.press('Shift+Tab');assert.ok(await page.evaluate(()=>!!document.activeElement.closest('[role="dialog"]')));await page.keyboard.press('Escape');assert.ok(await search.evaluate(e=>document.activeElement===e));
   await stage.locator('.task-nav').getByRole('button',{name:'Spectrum',exact:true}).click();await page.locator('.spectrum-counts').waitFor();await page.locator('.spectrum-plot').focus();
   await page.evaluate(()=>{window.__selectionTrace=[];window.__selectionObserver=new MutationObserver(()=>{const count=document.querySelectorAll('[data-selected="true"]').length;const last=window.__selectionTrace.at(-1);if(!last||last.count!==count)window.__selectionTrace.push({time:performance.now(),count});});window.__selectionObserver.observe(document.querySelector('.spectrum-drawer'),{subtree:true,childList:true,attributes:true,attributeFilter:['data-selected']});});
   const selectionStart=Date.now();await page.keyboard.press('Home');row.selectionImmediate=await page.locator('[data-selected="true"]').count();await page.locator('[data-selected="true"]').waitFor({timeout:2000});row.selectionWaitMs=Date.now()-selectionStart;
   row.selectionTrace=await page.evaluate(async()=>{await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));window.__selectionObserver.disconnect();return window.__selectionTrace;});assert.equal(await page.locator('[data-selected="true"]').count(),1);await page.keyboard.press('Escape');
   await page.getByRole('button',{name:'Help',exact:true}).click();await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
   row.history=await page.evaluate(()=>JSON.parse(localStorage.getItem('skyblink.recent-fields.v1')||'[]'));assert.ok(row.history.length);for(const entry of row.history){assert.deepEqual(Object.keys(entry).sort(),['dec','name','ra','size','source','target']);assert.equal(entry.source,'saved');}
   assert.ok(row.skyRequests.every(url=>new URL(url).searchParams.get('source')==='saved'));row.checks.push('keyboard_modals_and_spectrum','history_contains_query_settings_only','source_preserved');
   await page.emulateMedia({reducedMotion:'reduce'});await stage.locator('.task-nav').getByRole('button',{name:'Observe',exact:true}).click();assert.ok(await page.getByRole('button',{name:'Play blink',exact:true}).isDisabled());row.checks.push('reduced_motion_disables_blink');
   assert.deepEqual(row.errors,[]);row.status='pass';
  }catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:`${out}/${engineName}-${width}-failure.png`,fullPage:true}).catch(()=>{});}
  await context.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify(results,null,2));console.log(JSON.stringify({engine:engineName,width,status:row.status,failure:row.failure?.split('\n')[0],violations:row.axe.flatMap(a=>a.violations).map(v=>v.id)}));
 }
 await browser.close();
}
