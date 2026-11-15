import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
import AxeBuilder from '../../../backend/.cache/phase5/browser-tools/node_modules/@axe-core/playwright/dist/index.mjs';
import fs from 'node:fs';import assert from 'node:assert/strict';
const out='docs/screenshots/visual-polish';fs.mkdirSync(out,{recursive:true});const results=process.env.QA_ENGINE ? JSON.parse(fs.readFileSync(out+'/results.json','utf8')).filter(r=>r.engine!==process.env.QA_ENGINE) : [];
for(const [name,engine] of Object.entries({chromium,firefox,webkit})){
 if(process.env.QA_ENGINE && name!==process.env.QA_ENGINE)continue;const browser=await engine.launch();
 for(const width of [1440,390,320]){
 const context=await browser.newContext({viewport:{width,height:1000}});const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://localhost:5173/?source=saved&target=wise_0855');await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
 async function check(state){
  await page.waitForTimeout(650);await page.waitForFunction(()=>!document.querySelector('.canvas-status'));await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(400);
  const result=await page.evaluate(async()=>{
   const sheet=[...document.styleSheets].find(s=>s.ownerNode?.getAttribute('data-vite-dev-id')?.endsWith('/observatory.css'));if(!sheet)throw Error('Missing polish stylesheet');
   const snapshot=()=>({rects:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().width).map(e=>({tag:e.tagName,cls:typeof e.className==='string'?e.className:'svg',rect:e.getBoundingClientRect().toJSON()})),pixels:[...document.querySelectorAll('.blink-canvas')].map(e=>e.toDataURL()),text:document.body.innerText});
   const after=snapshot();sheet.disabled=true;await new Promise(r=>setTimeout(r,300));const before=snapshot();sheet.disabled=false;await new Promise(r=>setTimeout(r,650));
   const differences=after.rects.filter((e,i)=>JSON.stringify(e)!==JSON.stringify(before.rects[i]));return{elements:after.rects.length,differences,pixelsUnchanged:JSON.stringify(after.pixels)===JSON.stringify(before.pixels),textUnchanged:after.text===before.text,overflow:document.documentElement.scrollWidth>innerWidth};
  });
  results.push({engine:name,width,state,...result});assert.equal(result.differences.length,0,JSON.stringify({engine:name,width,state,differences:result.differences.slice(0,3)}));assert.ok(result.pixelsUnchanged);assert.ok(result.textUnchanged);assert.equal(result.overflow,false);
 }
 await check('observe');
 if(name==='chromium')await page.screenshot({path:out+`/after-${width}.png`});
 const fields=page.locator('[data-workspace-region="fields"]');if(!await fields.isVisible())await page.getByRole('button',{name:'Show fields',exact:true}).click();
 await fields.locator('.task-nav').getByRole('button',{name:'Compare',exact:true}).click();await check('compare');
 if(name==='chromium'&&width===1440){const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();results.push({engine:name,width,state:'axe',violations:axe.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))});}
 await fields.locator('.task-nav').getByRole('button',{name:'Spectrum',exact:true}).click();await page.locator('.spectrum-counts').waitFor();await check('spectrum');await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Help',exact:true}).click();await page.getByRole('dialog').waitFor();await check('help');await page.keyboard.press('Escape');
 await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(200);const motion=await page.evaluate(()=>document.getAnimations().filter(a=>a.playState==='running').map(a=>a.animationName));assert.deepEqual(motion,[]);assert.deepEqual(errors,[]);
 await context.close();console.log(name,width,'passed');fs.writeFileSync(out+'/results.json',JSON.stringify(results,null,2));
 }
 await browser.close();
}
