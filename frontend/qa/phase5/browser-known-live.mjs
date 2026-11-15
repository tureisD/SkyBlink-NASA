/** One actual user action: failed live search -> explicit known fresh download.
 * Run only after backend acceptance requests complete. No route interception.
 */
import assert from 'node:assert/strict';import fs from 'node:fs';import crypto from 'node:crypto';
import {chromium} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='backend/.cache/phase5-discovery-outage/user-known';fs.mkdirSync(out,{recursive:true});
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
const browser=await chromium.launch();const page=await browser.newPage({viewport:{width:1440,height:1080}});
const row={started_at:new Date().toISOString(),scope:'Unintercepted user Vite5173 to API8000; explicit recovery click',requests:[],network:[],checks:[]};
page.on('request',r=>{if(r.url().includes('/api/v1/sky?'))row.requests.push(r.url());});
page.on('requestfailed',r=>{if(r.url().includes('/api/v1/sky?'))row.network.push({event:'failed',url:r.url(),failure:r.failure()});});
page.on('response',r=>{if(r.url().includes('/api/v1/sky?'))row.network.push({event:'response',url:r.url(),status:r.status()});});
try{
 const liveResponse=page.waitForResponse(r=>r.url().includes('/api/v1/sky?')&&new URL(r.url()).searchParams.get('discovery')==='live',{timeout:135000});
 await page.goto('http://localhost:5173/?source=archive&target=rw_aurigae');
 const failed=await liveResponse;const failedBytes=await failed.body();fs.writeFileSync(`${out}/live-error.json`,failedBytes);row.live_status=failed.status();
 assert.equal(failed.status(),503);await page.getByRole('button',{name:'Fetch known exposures online',exact:true}).waitFor();
 assert.ok(row.requests.every(url=>new URL(url).searchParams.get('discovery')==='live'));assert.equal(await page.locator('.blink-canvas').count(),0);
 const start=performance.now();const knownResponse=page.waitForResponse(r=>r.url().includes('/api/v1/sky?')&&new URL(r.url()).searchParams.get('discovery')==='known',{timeout:135000});
 await page.getByRole('button',{name:'Fetch known exposures online',exact:true}).click();
 const response=await knownResponse;const bytes=await response.body();row.known_elapsed_seconds=(performance.now()-start)/1000;row.known_status=response.status();fs.writeFileSync(`${out}/rw_aurigae-response.json`,bytes);assert.equal(response.status(),200);
 const sky=JSON.parse(bytes);row.provenance=sky.provenance;row.response_sha256=sha(bytes);
 assert.equal(sky.provenance.discovery_mode,'known');assert.equal(sky.provenance.data_access,'archive');assert.equal(sky.provenance.discovery_status,'partial');assert.equal(sky.provenance.is_simulated_fallback,false);
 const record=await(await page.request.get(new URL(sky.provenance.analysis_record_url,page.url()).href)).body();fs.writeFileSync(`${out}/rw_aurigae-analysis.json`,record);
 await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
 assert.match(await page.locator('.workspace-heading .eyebrow').textContent(),/Known exposures/);assert.equal(sky.epochs.length,2);
 await page.evaluate(()=>window.__canvas=document.querySelector('.blink-canvas'));await page.getByRole('button',{name:'Play blink',exact:true}).click();
 const paints=[];for(let i=0;i<10;i++){paints.push(await page.locator('.blink-canvas').evaluate(e=>e.toDataURL()));await page.waitForTimeout(90);}
 row.unique_paints=new Set(paints).size;assert.ok(row.unique_paints>1);assert.ok(await page.evaluate(()=>window.__canvas===document.querySelector('.blink-canvas')));
 await page.getByRole('button',{name:'Pause',exact:true}).click();await page.getByRole('button',{name:/^Comparison details/}).click();
 assert.match(await page.locator('#comparison-notification').textContent(),/no new archive search/i);await page.getByRole('button',{name:'Dismiss notification',exact:true}).click();
 assert.ok(row.requests.every(url=>new URL(url).searchParams.get('source')==='archive'));
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:`${out}/known-live.png`});
 row.checks.push('actual_live503','explicit_user_recovery_action','fresh_known200','bounded_inventory_label','no_saved_fallback','real_persistent_blink');row.status='pass';
}catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:`${out}/failure.png`}).catch(()=>{});}
fs.writeFileSync(`${out}/result.json`,JSON.stringify(row,null,2));console.log(JSON.stringify(row));await browser.close();process.exitCode=row.status==='pass'?0:1;
