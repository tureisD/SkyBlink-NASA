/** One unintercepted archive request through the actual user Vite 5173 -> API 8000.
 * Run only after the catalog acquisition matrix, to avoid competing archive load.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import {chromium} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='backend/.cache/phase5-catalog-reliability/user-browser';
fs.mkdirSync(out,{recursive:true});
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
const browser=await chromium.launch();
const page=await browser.newPage({viewport:{width:1440,height:1080}});
const row={started_at:new Date().toISOString(),browser:browser.version(),scope:'Actual unmodified browser request through user Vite5173 and API8000; no route interception',requests:[],network:[],checks:[]};
page.on('request',r=>{if(r.url().includes('/api/v1/sky?'))row.requests.push(r.url());});
page.on('requestfailed',r=>{if(r.url().includes('/api/v1/sky?'))row.network.push({event:'failed',url:r.url(),failure:r.failure()});});
page.on('response',r=>{if(r.url().includes('/api/v1/sky?'))row.network.push({event:'response',url:r.url(),status:r.status()});});
try{
 const start=performance.now();
 const received=page.waitForResponse(r=>r.url().includes('/api/v1/sky?'),{timeout:135000});
 await page.goto('http://localhost:5173/?source=archive&target=barnards_star');
 const response=await received;const bytes=await response.body();fs.writeFileSync(`${out}/barnards_star-response.json`,bytes);
 row.response_ms=Math.round(performance.now()-start);row.http_status=response.status();row.response_sha256=sha(bytes);
 assert.equal(response.status(),200);
 const sky=JSON.parse(bytes);row.provenance=sky.provenance;row.epochs=sky.epochs.map(e=>e.epoch_id);
 assert.equal(sky.provenance.data_access,'archive');assert.equal(sky.provenance.is_simulated_fallback,false);
 assert.equal(sky.provenance.processing_version,'matched_image_comparison/12');assert.equal(sky.provenance.comparison_status,'matched_visual');assert.equal(sky.epochs.length,2);
 const recordBytes=await(await page.request.get(new URL(sky.provenance.analysis_record_url,page.url()).href)).body();fs.writeFileSync(`${out}/barnards_star-analysis.json`,recordBytes);
 await page.locator('.blink-canvas').first().waitFor({timeout:15000});await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
 await page.evaluate(()=>window.__liveCanvas=document.querySelector('.blink-canvas'));
 await page.getByRole('button',{name:'Play blink',exact:true}).click();
 const paints=[];for(let i=0;i<10;i++){paints.push(await page.locator('.blink-canvas').evaluate(e=>e.toDataURL()));await page.waitForTimeout(90);}
 row.unique_paints=new Set(paints).size;assert.ok(row.unique_paints>1);assert.ok(await page.evaluate(()=>window.__liveCanvas===document.querySelector('.blink-canvas')));
 await page.getByRole('button',{name:'Pause',exact:true}).click();
 await page.locator('.task-nav').getByRole('button',{name:'Compare',exact:true}).click();await page.getByRole('button',{name:'Side by side',exact:true}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.blink-canvas').length===2&&!document.querySelector('.canvas-status'));
 row.frame_hashes=[];for(const epoch of sky.epochs){const data=await(await page.request.get(new URL(epoch.frames.all,page.url()).href)).body();row.frame_hashes.push(sha(data));}
 assert.notEqual(row.frame_hashes[0],row.frame_hashes[1]);
 await page.getByRole('checkbox',{name:'Difference (B minus A)'}).check();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
 // Development StrictMode can mount/clean up/remount a request effect. Verify
 // query/source identity, not the number of browser request-start events.
 assert.ok(row.requests.length>=1);assert.equal(new Set(row.requests).size,1);assert.ok(row.requests.every(u=>new URL(u).searchParams.get('source')==='archive'));
 row.checks.push('actual_user_proxy_path','fresh_method12_matched_pair','persistent_canvas_blink_changes_real_pixels','distinct_actual_AB_assets','paired_and_difference_enabled','no_saved_fallback');
 await page.screenshot({path:`${out}/user-matched-comparison.png`});row.status='pass';
}catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:`${out}/failure.png`}).catch(()=>{});}
fs.writeFileSync(`${out}/result.json`,JSON.stringify(row,null,2));console.log(JSON.stringify(row));await browser.close();
process.exitCode=row.status==='pass'?0:1;
