/** Narrow source-selector text bounds after the header typography correction. */
import assert from 'node:assert/strict';import fs from 'node:fs';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='backend/.cache/phase5-centered/header';fs.mkdirSync(out,{recursive:true});const results=[];
for(const [engineName,engine]of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();
 for(const width of[1440,320]){
  const context=await browser.newContext({viewport:{width,height:width===1440?900:844}}),page=await context.newPage();const row={engine:engineName,width};results.push(row);let release;
  try{
   if(width===320){const gate=new Promise(resolve=>release=resolve);await page.route('**/api/v1/sky?*',async route=>{await gate;await route.abort('failed').catch(()=>{});});await page.goto('http://127.0.0.1:5176/?source=archive&target=wise_0855');await page.getByRole('button',{name:'Cancel request',exact:true}).waitFor();}
   else{await page.goto('http://127.0.0.1:5176/?source=saved&target=wise_0855');await page.locator('.blink-canvas').waitFor();await page.getByRole('button',{name:'Focus image',exact:true}).click();}
   const selector=page.locator('.topbar .source-selector');await selector.waitFor();
   row.bounds=await selector.evaluate(label=>{
    const rect=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height};};
    const text=[...label.childNodes].find(node=>node.nodeType===Node.TEXT_NODE&&node.textContent.trim());const range=document.createRange();range.selectNodeContents(text);const r=range.getBoundingClientRect();
    return{label:rect(label),text:{x:r.x,y:r.y,width:r.width,height:r.height},header:rect(label.closest('.topbar')),select:rect(label.querySelector('select')),font:getComputedStyle(label).fontSize,lineHeight:getComputedStyle(label).lineHeight,viewport:innerWidth};
   });
   const {text,header,select,font}=row.bounds;assert.ok(text.y>=header.y&&text.y+text.height<=header.y+header.height);assert.ok(text.x>=0&&text.x+text.width<=width);assert.ok(select.x>=0&&select.x+select.width<=width);assert.ok(parseFloat(font)>=13);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   if(width===1440){const play=await page.getByRole('button',{name:'Play blink',exact:true}).boundingBox();assert.ok(play.y+play.height<=900);}
   row.status='pass';
  }catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:`${out}/${engineName}-${width}-failure.png`});}
  release?.();await context.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify(results,null,2));console.log(JSON.stringify({engine:engineName,width,status:row.status,failure:row.failure?.split('\n')[0]}));
 }
 await browser.close();
}
