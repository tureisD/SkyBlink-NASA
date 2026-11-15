/** Before-layout evidence, real explicit-saved WISE data only. */
import fs from 'node:fs';import crypto from 'node:crypto';
import {chromium} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='backend/.cache/phase5-centered/before';fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch();const results=[];
for(const width of[1440,1920,390]){
 const page=await browser.newPage({viewport:{width,height:width<500?844:1080}});
 await page.goto('http://127.0.0.1:5176/?source=saved&target=wise_0855');await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
 await page.screenshot({path:`${out}/${width}.png`,fullPage:true});
 results.push({width,url:page.url(),canvas:await page.locator('.blink-canvas').first().boundingBox(),documentWidth:await page.evaluate(()=>document.documentElement.scrollWidth)});await page.close();
}
const sources=fs.readdirSync('frontend/src',{recursive:true}).filter(p=>/\.(tsx?|css)$/.test(p)).map(p=>`frontend/src/${p.replaceAll('\\','/')}`).sort();
fs.writeFileSync(`${out}/results.json`,JSON.stringify({captured_at:new Date().toISOString(),source:'Actual saved WISE revision3; unvalidated historical comparison',sources:sources.map(path=>({path,sha256:crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex')})),results},null,2));await browser.close();console.log('Baseline1440/1920/390 captured.');
