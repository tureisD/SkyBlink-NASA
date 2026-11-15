import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';import assert from 'node:assert/strict';
import {chromium} from '../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='docs/screenshots/guide-20261115';fs.mkdirSync(out,{recursive:true});
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');const sources=new Map();
function bytes(file){const body=fs.readFileSync(file);sources.set(file,{path:file,sha256:sha(body)});return body;}
const paths={wiseSky:'backend/.cache/phase6/discovery-diagnosis/known-postfix/wise_0855-response.json',wiseAnalysis:'backend/.cache/phase6/discovery-diagnosis/known-postfix/wise_0855-analysis.json',rSky:'backend/.cache/phase5/discovery-outage/recovery-final/r_draconis-sky-known-response.json',rSpectrum:'backend/.cache/phase6/spectrum-final/r_draconis-known-response.json',rSpectrumAnalysis:'backend/.cache/phase6/spectrum-final/r_draconis-known-analysis.json'};
const products=Object.fromEntries(Object.entries(paths).map(([k,p])=>[k,JSON.parse(bytes(p))]));
paths.rSkyAnalysis='backend/.cache/phase5/discovery-outage/recovery-final/r_draconis-sky-known-analysis.json';products.rSkyAnalysis=JSON.parse(bytes(paths.rSkyAnalysis));
for(const [response,record] of [[products.wiseSky,products.wiseAnalysis],[products.rSky,products.rSkyAnalysis],[products.rSpectrum,products.rSpectrumAnalysis]]){assert.equal(response.provenance.analysis_id,record.analysis_id);assert.equal(Math.floor(Date.parse(response.provenance.generated_at)/1000),Math.floor(Date.parse(record.created_at)/1000));assert.equal(response.provenance.is_simulated_fallback,false);}
function assertRecorded(actual,expected){if(Array.isArray(expected)){assert.equal(actual.length,expected.length);expected.forEach((v,i)=>assertRecorded(actual[i],v));}else if(expected&&typeof expected==="object"){for(const [k,v] of Object.entries(expected))assertRecorded(actual[k],v);}else assert.deepEqual(actual,expected);} assertRecorded(products.rSpectrum.epochs,products.rSpectrumAnalysis.identity.outputs.epochs);
assert.equal(products.wiseSky.epochs.length,2);assert.equal(products.wiseSky.provenance.comparison_status,'matched_visual');
const channels=products.rSpectrum.epochs.flatMap(e=>e.channels);assert.equal(channels.length,3);assert.ok(channels.every(c=>c.flux_ujy===null&&!c.is_used_in_photometry));
const assets=new Map();for(const key of ['wise','r']){const sky=products[key==='wise'?'wiseSky':'rSky'],record=products[key==='wise'?'wiseAnalysis':'rSkyAnalysis'];const prefix=sky.provenance.analysis_record_url.slice(0,sky.provenance.analysis_record_url.lastIndexOf('/')+1);for(const [name,hash] of Object.entries(record.identity.outputs.assets)){const url=prefix+name,file='backend/.cache/live/'+url.split('/api/v1/assets/')[1],body=bytes(file);assert.equal(sha(body),hash);assets.set(url,{file,body,sha256:hash});}}
const requests=[],captures=[],errors=[];const browser=await chromium.launch();
for(const view of ['workspace','compare','spectrum']){
 const target=view==='spectrum'?'r_draconis':'wise_0855';
 const context=await browser.newContext({viewport:{width:1600,height:view==='spectrum'?1450:1200},reducedMotion:'reduce'}),page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{const u=new URL(route.request().url());requests.push({target,url:u.href});let body;
 if(u.pathname==='/api/v1/sky')body=bytes(target==='wise_0855'?paths.wiseSky:paths.rSky);
 else if(u.pathname==='/api/v1/spectrum'&&target==='r_draconis')body=bytes(paths.rSpectrum);
 else if(u.pathname==='/api/v1/targets')body=bytes('backend/.cache/phase6/spectrum-final/targets.json');
 else if(assets.has(u.pathname)){const a=assets.get(u.pathname);return route.fulfill({status:200,contentType:a.file.endsWith('.webp')?'image/webp':'application/octet-stream',body:a.body});}
 else {errors.push('Blocked unexpected API request: '+u.pathname);return route.abort();}
 return route.fulfill({status:200,contentType:'application/json',body});});
 const params=new URLSearchParams({target,source:'archive',discovery:'known',bands:target==='wise_0855'?'6':'all',task:view==='compare'?'compare':'observe'});
 await page.goto('http://localhost:5173/?'+params);await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
 if(view==='compare'){await page.getByRole('button',{name:'Side by side',exact:true}).click();await page.locator('.image-pair .blink-canvas').nth(1).waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));assert.match(await page.locator('.observation-caption').innerText(),/2025-05-05/);}
 else if(view==='spectrum') {await page.locator('.task-nav').getByRole('button',{name:'Spectrum',exact:true}).click();await page.locator('.spectrum-counts').waitFor();assert.match(await page.locator('.spectrum-counts').innerText(),/Fetched 3 samples; 0 recorded eligible/);assert.equal(await page.locator('.spectrum-plot').count(),0);await page.locator('.spectrum-method-details summary').click();assert.match(await page.locator('.spectrum-method-details').innerText(),/HARD_BAD_EXTRACTION_CENTRE/);}
 await page.waitForTimeout(500);

 const annotationSelectors=view==='workspace'?['.search-primary','.fields-sidebar .task-nav','.field-source','.inspector-sidebar .quality-dimensions']:view==='compare'?['.comparison-controls','.observation-selectors label:first-child','.observation-caption','.observation-status']:['.spectrum-counts','.spectrum-banner','.spec-table-wrap','.spectrum-method-details'];
 const annotations=await page.evaluate(selectors=>{
  const layer=document.createElement('div');layer.id='guide-annotations';layer.style.cssText='position:fixed;inset:0;z-index:10000;pointer-events:none;';document.body.append(layer);
  return selectors.map((selector,index)=>{const el=document.querySelector(selector);if(!el)throw Error('Missing annotation selector: '+selector);const r=el.getBoundingClientRect();
   const outline=document.createElement('div');outline.style.cssText=`position:absolute;left:${r.x-3}px;top:${r.y-3}px;width:${r.width+6}px;height:${r.height+6}px;border:2px solid #ffca70;border-radius:4px;box-sizing:border-box;box-shadow:0 0 0 1px #07111e;`;layer.append(outline);
   const badge=document.createElement('span');badge.textContent=String(index+1);badge.style.cssText=`position:absolute;left:${Math.max(2,r.right-16)}px;top:${Math.max(2,r.y-15)}px;width:30px;height:30px;display:grid;place-items:center;border-radius:50%;background:#ffca70;color:#101b2c;font:bold 17px system-ui;border:2px solid #091321;box-shadow:0 2px 6px #0008;`;layer.append(badge);
   return{number:index+1,selector,rect:{x:r.x,y:r.y,width:r.width,height:r.height}};
  });
 },annotationSelectors);
 const filename='guide-'+view+'.png';await page.screenshot({path:out+'/'+filename});
 fs.mkdirSync('frontend/public/help',{recursive:true});fs.copyFileSync(out+'/'+filename,'frontend/public/help/'+filename);

 captures.push({path:out+'/'+filename,runtime_help_path:'frontend/public/help/'+filename,annotations,sha256:sha(fs.readFileSync(out+'/'+filename)),url:page.url(),viewport:{width:1600,height:view==='spectrum'?1450:1200},caption:'Retained real-response playback in an isolated browser; no new live acquisition.',response_paths:target==='wise_0855'?[paths.wiseSky]:[paths.rSky,paths.rSpectrum],analysis_ids:target==='wise_0855'?[products.wiseSky.provenance.analysis_id]:[products.rSky.provenance.analysis_id,products.rSpectrum.provenance.analysis_id],generated_at:target==='wise_0855'?[products.wiseSky.provenance.generated_at]:[products.rSky.provenance.generated_at,products.rSpectrum.provenance.generated_at],visible_text:await page.locator(target==='wise_0855'?'#workspace':'.spectrum-drawer').innerText()});await context.close();
}
assert.deepEqual(errors,[]);const sourceFiles=[];function walk(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=dir+'/'+e.name;if(e.isDirectory())walk(p);else sourceFiles.push({path:p,sha256:sha(fs.readFileSync(p))});}}walk('frontend/src');walk('frontend/dist');
fs.writeFileSync(out+'/origins.json',JSON.stringify({captured_at:new Date().toISOString(),browser:browser.version(),scope:'Unchanged retained real HTTP bodies and analysis-verified immutable assets; isolated browser route playback, no new live acquisition. Screenshot only; no astrophysical certification.',captures,source_and_build:sourceFiles,retained_sources:[...sources.values()],asset_verification:[...assets].map(([url,a])=>({url,path:a.file,sha256:a.sha256,analysis_hash_verified:true})),requests,errors,capture_script:{path:'scripts/capture_user_guide.mjs',sha256:sha(fs.readFileSync('scripts/capture_user_guide.mjs'))}},null,2));await browser.close();console.log(JSON.stringify(captures.map(({path,analysis_ids})=>({path,analysis_ids}))));

