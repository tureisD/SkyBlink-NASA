/** Earliest-ready chart interaction: one Home key, no readiness delay/retry.
 * Real saved observations only. Regression for post-key passive-effect reset.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='backend/.cache/phase5-catalog-reliability/spectrum-final';fs.mkdirSync(out,{recursive:true});const results=[];
for(const [name,engine]of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();
 for(let attempt=1;attempt<=12;attempt++){
  const page=await browser.newPage({viewport:{width:1024,height:1080}});const row={engine:name,attempt,home_presses:1};results.push(row);
  try{
   await page.goto('http://127.0.0.1:5176/?source=saved&target=wise_0855');
   await page.locator('.task-nav').getByRole('button',{name:'Spectrum',exact:true}).click();
   await page.locator('.spectrum-counts').waitFor();await page.locator('.spectrum-plot').focus();
   await page.keyboard.press('Home');await page.locator('[data-selected="true"]').waitFor({timeout:2000});
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   assert.equal(await page.locator('[data-selected="true"]').count(),1);row.status='pass';
  }catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:`${out}/${name}-${attempt}.png`});}
  await page.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify(results,null,2));
 }
 await browser.close();console.log(JSON.stringify({engine:name,passed:results.filter(r=>r.engine===name&&r.status==='pass').length,attempts:12}));
}
process.exitCode=results.every(r=>r.status==='pass')?0:1;
