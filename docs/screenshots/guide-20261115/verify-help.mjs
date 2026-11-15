import assert from 'node:assert/strict';import fs from 'node:fs';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
import AxeBuilder from '../../../backend/.cache/phase5/browser-tools/node_modules/@axe-core/playwright/dist/index.mjs';
const out='docs/screenshots/guide-20261115/help-qa';fs.mkdirSync(out,{recursive:true});const results=[];
for(const[name,engine]of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();
 for(const width of [1440,390,320]){
 const context=await browser.newContext({viewport:{width,height:1000},reducedMotion:'reduce'}),page=await context.newPage(),row={engine:name,width,errors:[]};
 page.on('pageerror',e=>row.errors.push(e.message));
 await page.goto('http://localhost:5173/?source=saved&target=wise_0855');await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
 await page.evaluate(()=>window.__guideCanvas=document.querySelector('.blink-canvas'));
 const help=page.getByRole('button',{name:'Help',exact:true});await help.click();const dialog=page.getByRole('dialog');await dialog.waitFor();assert.equal(await dialog.locator('.guide-figure').count(),3);
 await page.keyboard.press('Shift+Tab');assert.equal(await page.evaluate(()=>!!document.activeElement.closest('[role=dialog]')),true);
 row.images=[];
 for(const label of ['workspace','compare','spectrum']){
 const expand=page.getByRole('button',{name:`Enlarge ${label} image`,exact:true});await expand.scrollIntoViewIfNeeded();await expand.click();
 const region=page.locator('#help-image-'+label),img=region.locator('img');await img.evaluate(e=>e.decode());assert.equal(await page.getByRole('button',{name:'Fit image to panel',exact:true}).getAttribute('aria-expanded'),'true');await region.focus();
 const size=await region.evaluate(e=>({width:e.clientWidth,scrollWidth:e.scrollWidth,natural:e.querySelector('img').naturalWidth,doc:document.documentElement.scrollWidth,viewport:innerWidth}));assert.ok(size.scrollWidth>size.width);assert.equal(size.natural,1600);assert.ok(size.doc<=size.viewport);row.images.push({label,...size});
 await page.keyboard.press('ArrowRight');await page.waitForTimeout(100);assert.ok(await region.evaluate(e=>e.scrollLeft)>0);row.images.at(-1).keyboardScroll=await region.evaluate(e=>({left:e.scrollLeft,focused:document.activeElement===e}));
 await page.getByRole('button',{name:'Fit image to panel',exact:true}).click();assert.equal(await region.getAttribute('tabindex'),null);
 }
 if(name==='chromium'){
 const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();row.axe=result.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}));assert.deepEqual(row.axe,[]);
 await dialog.evaluate(e=>e.scrollTop=0);await page.screenshot({path:out+`/help-${width}.png`});
 }
 await page.getByText('Move around the image and use the keyboard',{exact:true}).click();assert.equal(await dialog.locator('.keyboard-reference').isVisible(),true);
 await page.keyboard.press('Escape');assert.equal(await help.evaluate(e=>document.activeElement===e),true);assert.equal(await page.evaluate(()=>window.__guideCanvas===document.querySelector('.blink-canvas')),true);assert.equal(await page.locator('#root').evaluate(e=>e.inert),false);assert.deepEqual(row.errors,[]);
 row.status='pass';results.push(row);fs.writeFileSync(out+'/results.json',JSON.stringify(results,null,2));console.log(name,width,'pass');await context.close();
 }
 await browser.close();
}
