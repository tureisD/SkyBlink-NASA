/** Narrow relocation check: explicit saved observations, no archive acquisition. */
import assert from 'node:assert/strict';import fs from 'node:fs';import crypto from 'node:crypto';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out=process.env.QA_OUTPUT||'backend/.cache/phase6/compare-sidebar';fs.mkdirSync(out,{recursive:true});const results=[];
const base=process.env.QA_BASE||'http://127.0.0.1:5173';
for(const [name,engine] of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();
 for(const width of [1440,320]){
  const context=await browser.newContext({viewport:{width,height:width===320?844:1000}}),page=await context.newPage(),row={engine:name,width,requests:[],checks:[]};results.push(row);
  page.on('request',request=>{if(request.url().includes('/api/v1/sky?'))row.requests.push(request.url());});
  try{
   await page.goto(`${base}/?source=saved&target=eps_indi_b`);await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
   await page.evaluate(()=>window.__compareCanvas=document.querySelector('.blink-canvas'));
   const fields=page.locator('[data-workspace-region="fields"]'),stage=page.locator('[data-workspace-region="stage"]');
   if(!await fields.isVisible())await page.getByRole('button',{name:'Show fields',exact:true}).click();
   await fields.locator('.task-nav').getByRole('button',{name:'Compare',exact:true}).click();
   const controls=fields.locator('.comparison-controls');await controls.waitFor();assert.equal(await stage.locator('.comparison-controls').count(),0);
   row.geometry=await controls.evaluate(element=>{const box=element.getBoundingClientRect(),rail=element.closest('[data-workspace-region="fields"]').getBoundingClientRect();return{box:{x:box.x,y:box.y,width:box.width,height:box.height},rail:{x:rail.x,y:rail.y,width:rail.width,height:rail.height},documentWidth:document.documentElement.scrollWidth,viewport:innerWidth};});
   assert.ok(row.geometry.box.x>=row.geometry.rail.x&&row.geometry.box.x+row.geometry.box.width<=row.geometry.rail.x+row.geometry.rail.width+1);assert.ok(row.geometry.documentWidth<=width+1);
   const a=controls.getByRole('combobox',{name:'Observation A',exact:true}),b=controls.getByRole('combobox',{name:'Observation B',exact:true});
   const values=await a.locator('option').evaluateAll(options=>options.map(option=>option.value));assert.ok(values.length>=3);
   await a.selectOption(values.at(-2));await b.selectOption(values.at(-1));assert.equal(await a.inputValue(),values.at(-2));assert.equal(await b.inputValue(),values.at(-1));
   await a.focus();await page.keyboard.press('Tab');assert.equal(await b.evaluate(element=>document.activeElement===element),true);
   await page.keyboard.press('Tab');const paired=controls.getByRole('button',{name:'Side by side',exact:true});assert.equal(await paired.evaluate(element=>document.activeElement===element),true);await page.keyboard.press('Enter');
   await page.waitForFunction(()=>document.querySelectorAll('.blink-canvas').length===2);assert.equal(await paired.getAttribute('aria-pressed'),'true');
   await controls.getByRole('button',{name:'Show B',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.blink-canvas').length===1);assert.equal(await page.getByRole('combobox',{name:'Observation date',exact:true}).inputValue(),values.at(-1));
   assert.equal(await page.evaluate(()=>window.__compareCanvas===document.querySelector('.blink-canvas')),true);
   await controls.getByRole('button',{name:'Show A',exact:true}).click();assert.equal(await page.getByRole('combobox',{name:'Observation date',exact:true}).inputValue(),values.at(-2));
   if(name==='chromium'){await controls.scrollIntoViewIfNeeded();await page.screenshot({path:`${out}/compare-${width}.png`});}
   await page.getByRole('button',{name:'Close fields panel',exact:true}).click();await page.waitForFunction(()=>document.activeElement?.id==='fields-toggle');assert.equal(await fields.isVisible(),false);
   assert.equal(await page.evaluate(()=>window.__compareCanvas===document.querySelector('.blink-canvas')),true);
   await page.getByRole('button',{name:'Play blink',exact:true}).click();await page.getByRole('button',{name:'Pause',exact:true}).waitFor();
   const renders=await page.evaluate(async()=>{const samples=new Set();for(let index=0;index<10;index++){samples.add(document.querySelector('.blink-canvas').toDataURL());await new Promise(resolve=>setTimeout(resolve,90));}return samples.size;});assert.ok(renders>1);assert.equal(await page.evaluate(()=>window.__compareCanvas===document.querySelector('.blink-canvas')),true);await page.getByRole('button',{name:'Pause',exact:true}).click();
   await page.getByRole('button',{name:'Show fields',exact:true}).click();assert.equal(await a.inputValue(),values.at(-2));assert.equal(await b.inputValue(),values.at(-1));assert.equal(await stage.locator('.comparison-controls').count(),0);
   await fields.locator('.task-nav').getByRole('button',{name:'Observe',exact:true}).click();assert.equal(await page.evaluate(()=>window.__compareCanvas===document.querySelector('.blink-canvas')),true);assert.equal(await page.locator('.comparison-controls').count(),0);
   assert.ok(row.requests.every(url=>new URL(url).searchParams.get('source')==='saved'));
   row.checks.push('compare_box_left_rail_only','no_horizontal_overflow','AB_selection','keyboard_order','paired_layout','show_A_B','persistent_canvas','observe_compare_observe_same_canvas','collapse_focus_restore','blink_distinct_real_frames','selection_survives_collapse','explicit_saved_only');row.status='pass';
  }catch(error){row.status='failed';row.error=error.stack;await page.screenshot({path:`${out}/${name}-${width}-failure.png`}).catch(()=>{});}
  await context.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify(results,null,2));console.log(JSON.stringify({engine:name,width,status:row.status,error:row.error?.split('\n')[0]}));
 }
 await browser.close();
}
const sourceFiles=['frontend/src/App.tsx','frontend/src/styles/global.css','frontend/src/components/FieldsPanel.tsx','frontend/src/components/TimelineDock.tsx','frontend/qa/phase6/browser-compare-sidebar.mjs','golden_cache/eps_indi_b/manifest.json',...fs.readdirSync('frontend/dist/assets').map(file=>'frontend/dist/assets/'+file)];
fs.writeFileSync(`${out}/origins.json`,JSON.stringify({created_at:new Date().toISOString(),scope:'Actual explicit saved Epsilon Indi B; existing development UI, no archive queries',files:sourceFiles.map(path=>({path,sha256:crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex')}))},null,2));
process.exitCode=results.every(row=>row.status==='pass')?0:1;
