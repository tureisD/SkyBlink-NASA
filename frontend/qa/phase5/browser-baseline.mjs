/** Real explicit-saved baseline only; no observation stubs or upstream requests. */
import { chromium } from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';
const output=path.resolve('backend/.cache/phase5/browser-baseline');
fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
const results=[];
for(const width of [1440,390,320]){
  const page=await browser.newPage({viewport:{width,height:width===1440?1000:844},reducedMotion:'reduce'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:5176/?source=saved&target=wise_0855');
  await page.waitForSelector('.blink-canvas',{timeout:30000}).catch(()=>{});
  await page.waitForTimeout(1500);
  await page.screenshot({path:path.join(output,`baseline-${width}.png`),fullPage:true});
  results.push({width,errors,bodyWidth:await page.evaluate(()=>document.documentElement.scrollWidth),buttons:await page.getByRole('button').allTextContents()});
  const spectrum=page.getByRole('button',{name:/spectrum/i}).first();
  if(await spectrum.count()){
    await spectrum.click();await page.waitForTimeout(1000);
    await page.screenshot({path:path.join(output,`baseline-spectrum-${width}.png`),fullPage:true});
  }
  await page.close();
}
await browser.close();
fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));
console.log(JSON.stringify(results,null,2));
