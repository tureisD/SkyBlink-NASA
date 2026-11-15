/** Keyboard/coordinate regression on real saved products; transport abort only for arbitrary search. */
import assert from 'node:assert/strict';import fs from 'node:fs';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const base='http://127.0.0.1:8177',out=process.env.QA_OUTPUT||'backend/.cache/phase6/shortcuts';fs.mkdirSync(out,{recursive:true});const results=[];
async function ready(page){await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));}
async function task(page,name){if(!await page.locator('[data-workspace-region="fields"]').isVisible())await page.getByRole('button',{name:'Show fields',exact:true}).click();await page.locator('.task-nav').getByRole('button',{name,exact:true}).click();}
for(const [engineName,engine]of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();const row={engine:engineName,checks:[]};results.push(row);
 try{
  await page.goto(`${base}/?source=saved&target=wise_0855&fps=999`);await ready(page);const canvas=page.locator('.blink-canvas').first();await canvas.focus();
  await page.keyboard.press('Space');await page.getByRole('button',{name:'Pause',exact:true}).waitFor();await page.waitForURL(url=>url.searchParams.get('mode')==='blink');
  assert.equal(new URL(page.url()).searchParams.get('fps'),'8');
  await canvas.dispatchEvent('keydown',{key:' ',code:'Space',repeat:true});assert.ok(await page.getByRole('button',{name:'Pause',exact:true}).isVisible());
  await page.keyboard.press('Space');await page.getByRole('button',{name:'Play blink',exact:true}).waitFor();
  const date=page.getByRole('combobox',{name:'Observation date',exact:true}),first=await date.inputValue();
  await canvas.focus();await page.keyboard.press('ArrowRight');await page.waitForFunction(value=>document.querySelector('select[aria-label="Observation date"]').value!==value,first);const next=await date.inputValue();
  await canvas.dispatchEvent('keydown',{key:'ArrowRight',repeat:true});assert.equal(await date.inputValue(),next);
  await page.keyboard.press('ArrowLeft');await page.waitForFunction(value=>document.querySelector('select[aria-label="Observation date"]').value===value,first);
  await page.keyboard.press('Shift+ArrowRight');await page.waitForURL(url=>Number(url.searchParams.get('panX'))>0);assert.equal(await date.inputValue(),first);
  await page.keyboard.press('r');await page.waitForURL(url=>!url.searchParams.has('panX')||Number(url.searchParams.get('panX'))===0);
  await page.keyboard.press('3');assert.equal(await page.getByRole('combobox',{name:'Image bands'}).inputValue(),'3');await page.keyboard.press('a');assert.equal(await page.getByRole('combobox',{name:'Image bands'}).inputValue(),'all');
  await page.keyboard.press('d');assert.ok(await page.getByRole('checkbox',{name:'Difference (B minus A)'}).isChecked());
  await page.keyboard.press('Space');assert.equal(await page.getByRole('button',{name:'Pause',exact:true}).count(),0);await canvas.dispatchEvent('keydown',{key:'d',repeat:true});assert.ok(await page.getByRole('checkbox',{name:'Difference (B minus A)'}).isChecked());await page.keyboard.press('d');
  row.checks.push('space_toggle','repeat_ignored','8fps_cap','arrow_steps','shift_arrow_pan','reset_camera','band_keys','difference_blocks_play');
  if(!await page.locator('[data-workspace-region="fields"]').isVisible())await page.getByRole('button',{name:'Show fields',exact:true}).click();
  const sidebarButton=page.locator('.task-nav').getByRole('button',{name:'Observe',exact:true});await sidebarButton.focus();const before=await date.inputValue();await page.keyboard.press('ArrowRight');assert.equal(await date.inputValue(),before);
  const play=page.getByRole('button',{name:'Play blink',exact:true});await play.focus();await page.keyboard.press('Space');await page.getByRole('button',{name:'Pause',exact:true}).waitFor();await page.getByRole('button',{name:'Pause',exact:true}).click();
  await canvas.focus();await page.keyboard.press('?');await page.getByRole('dialog').waitFor();assert.match(await page.getByRole('dialog').innerText(),/Space/);await page.keyboard.press('Space');assert.equal(await page.getByRole('button',{name:'Pause',exact:true}).count(),0);await page.keyboard.press('Escape');
  await canvas.focus();await page.keyboard.press('/');await page.getByRole('dialog').waitFor();const ra=page.getByLabel('RA (ICRS)',{exact:true}),dec=page.getByLabel('Dec (ICRS)',{exact:true});await ra.fill('12');await ra.press('Space');assert.equal(await ra.inputValue(),'12 ');await ra.fill('359.9999999');await dec.fill('-90');
  const requests=[];await page.route('**/api/v1/sky?*',route=>{requests.push(route.request().url());return route.abort('failed');});await page.locator('.search-form button[type="submit"]').click();await page.getByRole('button',{name:'Retry request',exact:true}).waitFor();
  assert.ok(requests.length);for(const request of requests){const q=new URL(request).searchParams;assert.equal(Number(q.get('ra')),359.9999999);assert.equal(Number(q.get('dec')),-90);assert.equal(q.get('source'),'archive');assert.equal(q.get('target_id'),null);assert.equal(q.get('discovery'),'live');}
  row.checks.push('sidebar_arrows_do_not_step','native_button_space_once','help_modal_isolation','editable_space','exact_coordinate_search_no_catalog_snap');await page.unroute('**/api/v1/sky?*');
  await page.goto(`${base}/?source=saved&target=r_draconis&epoch=2024_E1&bands=1`);await page.locator('.blink-canvas').waitFor();await page.getByText('Band 1 is unavailable in shared observation 2024_E1.',{exact:true}).waitFor();assert.equal(await page.locator('select[aria-label="Observation date"] option[value="2024_E1"]').count(),0);assert.notEqual(await page.getByRole('combobox',{name:'Observation date',exact:true}).inputValue(),'2024_E1');row.checks.push('real_missing_band_warning_valid_epoch_dates');
  await page.emulateMedia({reducedMotion:'reduce'});await page.goto(`${base}/?source=saved&target=wise_0855&mode=blink`);await ready(page);await page.locator('.blink-canvas').focus();await page.keyboard.press('Space');assert.equal(await page.getByRole('button',{name:'Pause',exact:true}).count(),0);assert.ok(await page.getByRole('button',{name:'Play blink',exact:true}).isDisabled());row.checks.push('reduced_motion_blocks_keyboard_play','shared_view_restores_paused');row.status='pass';
 }catch(error){row.status='failed';row.error=error.stack;await page.screenshot({path:`${out}/${engineName}-failure.png`}).catch(()=>{});}
 await context.close();await browser.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify(results,null,2));console.log(JSON.stringify(row));
}
process.exitCode=results.every(row=>row.status==='pass')?0:1;
