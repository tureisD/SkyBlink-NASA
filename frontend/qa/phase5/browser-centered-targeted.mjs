/** Pending/error navigation and short-desktop transport visibility; failures are transport-only. */
import assert from 'node:assert/strict';import fs from 'node:fs';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='backend/.cache/phase5-centered/targeted';fs.mkdirSync(out,{recursive:true});const results=[];
for(const [engineName,engine]of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();
 for(const width of[320,390,1440]){
  const context=await browser.newContext({viewport:{width,height:width===1440?900:844}}),page=await context.newPage();const row={engine:engineName,width,checks:[]};results.push(row);
  try{
   if(width<500){
    let release;const gate=new Promise(resolve=>release=resolve);
    await page.route('**/api/v1/sky?*',async route=>{await gate;await route.abort('failed').catch(()=>{});});
    await page.goto('http://127.0.0.1:5176/?source=archive&target=wise_0855');await page.getByRole('button',{name:'Cancel request',exact:true}).waitFor();
    const source=page.getByRole('combobox',{name:'Data source'});assert.ok(await source.isVisible());assert.equal(await source.inputValue(),'archive');
    const bounds=await source.boundingBox();assert.ok(bounds.x>=0&&bounds.x+bounds.width<=width+1);assert.ok(await page.getByRole('button',{name:'Search sky or choose a target'}).isVisible());
    release();await page.getByRole('button',{name:'Retry request',exact:true}).waitFor();assert.ok(await source.isVisible());assert.equal(await source.inputValue(),'archive');assert.equal(await page.locator('.blink-canvas').count(),0);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));row.checks.push('loading_source_selector_visible','error_source_selector_visible','navigation_available','no_automatic_fallback','no_page_overflow');
   }else{
    await page.goto('http://127.0.0.1:5176/?source=saved&target=wise_0855');await page.locator('.blink-canvas').waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
    const play=page.getByRole('button',{name:'Play blink',exact:true});row.normal=await play.boundingBox();assert.ok(row.normal.y+row.normal.height<=900,'Initial playback control below900pxviewport');
    await page.getByRole('button',{name:'Focus image',exact:true}).click();row.focus=await play.boundingBox();assert.ok(row.focus.y+row.focus.height<=900,'Focused playback control below900pxviewport');row.checks.push('initial_Play_within900pxviewport','focused_Play_within900pxviewport');
   }
   row.status='pass';
  }catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:`${out}/${engineName}-${width}-failure.png`,fullPage:true});}
  await context.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify(results,null,2));console.log(JSON.stringify({engine:engineName,width,status:row.status,failure:row.failure?.split('\n')[0]}));
 }
 await browser.close();
}
