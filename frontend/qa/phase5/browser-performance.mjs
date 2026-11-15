/** Local developer-build observations, not release performance or a leak-proof claim. */
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';import os from 'node:os';
import {chromium}from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out=path.resolve('backend/.cache/phase5/browser-performance');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch();const context=await browser.newContext({viewport:{width:1440,height:1000}});
await context.addInitScript(()=>{
 window.__qaBitmaps={created:0,closed:0};const original=window.createImageBitmap;
 window.createImageBitmap=async function(...args){const bitmap=await original.apply(this,args);window.__qaBitmaps.created++;const close=bitmap.close.bind(bitmap);let closed=false;bitmap.close=()=>{if(!closed){closed=true;window.__qaBitmaps.closed++;}return close();};return bitmap;};
});
const page=await context.newPage();const client=await context.newCDPSession(page);
const started=Date.now();await page.goto('http://127.0.0.1:5176/?source=saved&target=wise_0855');
await page.locator('.blink-canvas').waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));await page.waitForTimeout(150);
const result={browser:browser.version(),platform:process.platform,cpu:os.cpus()[0].model,build:'Vite development server, local FastAPI saved data, no network throttling',loadAndDecodeMs:Date.now()-started};
result.bitmapCountsBefore=await page.evaluate(()=>({...window.__qaBitmaps}));
await client.send('HeapProfiler.collectGarbage');result.heapBefore=(await client.send('Runtime.getHeapUsage')).usedSize;
await page.evaluate(()=>window.__qaCanvas=document.querySelector('.blink-canvas'));
for(let i=0;i<20;i++){await page.getByRole('combobox',{name:'Image bands'}).selectOption(['1','6','thermal','all'][i%4]);await page.waitForTimeout(120);await page.waitForFunction(()=>!document.querySelector('.canvas-status'));}
for(let i=0;i<20;i++){await page.getByRole('button',{name:'Next',exact:true}).click();await page.waitForTimeout(40);}
assert.equal(await page.evaluate(()=>window.__qaCanvas===document.querySelector('.blink-canvas')),true);
await client.send('HeapProfiler.collectGarbage');result.heapAfter=(await client.send('Runtime.getHeapUsage')).usedSize;
result.bitmapCounts=await page.evaluate(()=>window.__qaBitmaps);result.manualSteps=20;result.bandSwitches=20;result.canvasPreserved=true;
result.contrast=await page.evaluate(()=>{
 const parse=color=>{const m=color.match(/[\d.]+/g)?.map(Number)??[0,0,0];return[m[0],m[1],m[2],m[3]??1];};
 const blend=(over,under)=>over.slice(0,3).map((v,i)=>v*over[3]+under[i]*(1-over[3]));
 const luminance=rgb=>rgb.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
 return [...document.querySelectorAll('button,select')].filter(e=>e.getClientRects().length&&!e.disabled).map(e=>{
  const ancestors=[];for(let p=e;p;p=p.parentElement)ancestors.push(p);let bg=[255,255,255];for(const a of ancestors.reverse())bg=blend(parse(getComputedStyle(a).backgroundColor),bg);
  const fg=blend(parse(getComputedStyle(e).color),bg);const a=luminance(fg),b=luminance(bg);
  return{name:e.getAttribute('aria-label')||e.textContent.trim(),ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),fontSize:getComputedStyle(e).fontSize};
 });
});
await page.setViewportSize({width:320,height:256});await page.waitForTimeout(200);
result.reflow={scenario:'320x256 CSS viewport: 1280x1024 at400% equivalent, not native browser zoom test',documentWidth:await page.evaluate(()=>document.documentElement.scrollWidth),viewport:320};
assert.ok(result.reflow.documentWidth<=321);await page.getByRole('button',{name:'Search sky or choose a target'}).click();await page.getByRole('dialog').waitFor();
await page.getByRole('button',{name:'Resolve & load'}).scrollIntoViewIfNeeded();assert.equal(await page.getByRole('button',{name:'Resolve & load'}).isVisible(),true);
await page.screenshot({path:path.join(out,'reflow-400-equivalent.png')});
await page.keyboard.press('Escape');await page.route('**/api/v1/sky?*',route=>route.abort('failed'));
await page.getByRole('button',{name:'Search sky or choose a target'}).click();await page.getByRole('button',{name:/ε Indi B/}).click();await page.getByRole('button',{name:'Retry request',exact:true}).waitFor();
result.bitmapCountsAfterUnmount=await page.evaluate(()=>({...window.__qaBitmaps}));
assert.equal(result.bitmapCountsAfterUnmount.created,result.bitmapCountsAfterUnmount.closed,'Every decoded frame must close when field unmounts');
result.limits='JS heap after forced GC and bitmap close counts only; excludes GPU/process memory, long sessions, slower hardware, live-archive latency, native400% zoom, screen reader and flash-threshold analysis.';
fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({...result,contrast:{count:result.contrast.length,min:Math.min(...result.contrast.map(r=>r.ratio))}},null,2));
await browser.close();
