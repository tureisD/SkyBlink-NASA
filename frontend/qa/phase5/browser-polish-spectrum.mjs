/** Signed real saved spectrum, tooltip geometry, complete export and honest clipboard outcomes. */
import assert from 'node:assert/strict';import fs from 'node:fs';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='backend/.cache/phase5-polish/spectrum';fs.mkdirSync(out,{recursive:true});const results=[];
for(const [engineName,engine] of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();
 for(const width of [1440,390,320]){
  const context=await browser.newContext({viewport:{width,height:width===1440?1000:844}}),page=await context.newPage();const row={engine:engineName,width};results.push(row);
  if(engineName==='chromium')await context.grantPermissions(['clipboard-read','clipboard-write']);
  try{
   await page.goto('http://127.0.0.1:5176/?source=saved&target=eps_indi_b');await page.locator('.blink-canvas').waitFor();
   await page.getByRole('button',{name:'Spectrum',exact:true}).first().click();await page.locator('.spectrum-plot').waitFor();
   const plot=page.locator('.spectrum-plot');await plot.scrollIntoViewIfNeeded();
   assert.equal(await plot.locator('path').count(),0);
   assert.equal(await plot.locator('[data-spectrum-point]').count(),245);
   assert.equal(await plot.locator('[data-spectrum-point]').evaluateAll(points=>points.filter(p=>Number(p.dataset.flux)<0).length),1);
   await plot.focus();await page.keyboard.press('Home');
   const point=await plot.evaluate(svg=>{const circle=svg.querySelector('[data-selected="true"] circle');const p=svg.createSVGPoint();p.x=circle.cx.baseVal.value;p.y=circle.cy.baseVal.value;const s=p.matrixTransform(svg.getScreenCTM());return{x:s.x,y:s.y};});
   await page.mouse.move(point.x,point.y);await page.locator('.spectrum-tooltip').waitFor();
   row.tooltip=await page.locator('.spectrum-tooltip').evaluate(g=>{const svg=g.ownerSVGElement,box=g.getBBox(),x=g.transform.baseVal.getItem(0).matrix.e;return{left:x+box.x,right:x+box.x+box.width,width:svg.viewBox.baseVal.width,textSizes:[...g.querySelectorAll('text')].map(t=>parseFloat(getComputedStyle(t).fontSize)*svg.getScreenCTM().a)};});
   assert.ok(row.tooltip.left>=0&&row.tooltip.right<=row.tooltip.width);
   assert.ok(row.tooltip.textSizes.every(size=>size>=12.8));
   await page.getByRole('button',{name:'Copy sample metadata',exact:true}).click();
   await page.waitForFunction(()=>!!document.querySelector('.spectrum-copy-status')?.textContent);
   row.clipboard=await page.locator('.spectrum-copy-status').innerText();assert.match(row.clipboard,/copied|Clipboard unavailable/);
   if(engineName==='chromium'){assert.match(row.clipboard,/copied/);const copied=await page.evaluate(()=>navigator.clipboard.readText());assert.match(copied,/Flux \(\u00b5Jy\):/);assert.match(copied,/Extraction ICRS \(deg\): not recorded/);row.clipboardText=copied;}
   await page.locator('.spec-table-wrap summary').click();await page.getByLabel('Measurement status',{exact:true}).selectOption('unavailable');assert.equal(await page.locator('.spec-table tbody tr').count(),1);
   const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Export measurements CSV',exact:true}).click();const download=await downloadPromise;const csv=fs.readFileSync(await download.path(),'utf8');assert.equal(csv.trim().split(/\r?\n/).length,247);
   row.exportRows=246;row.status='pass';
  }catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:`${out}/${engineName}-${width}-failure.png`});}
  await context.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify(results,null,2));console.log(JSON.stringify({engine:engineName,width,status:row.status,failure:row.failure?.split('\n')[0]}));
 }
 await browser.close();
}
