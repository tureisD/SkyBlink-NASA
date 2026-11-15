/** Single bounded Chromium navigation to an official SIA discovery URL.
 * Diagnostic only: no application fallback, invented data, or repeated query.
 */
import fs from 'node:fs';
import crypto from 'node:crypto';
import {chromium} from '../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='backend/.cache/phase5-discovery-outage/browser-sia';fs.mkdirSync(out,{recursive:true});
const url='https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_dr1&POS=CIRCLE+76.95608953+30.40113001+0&RESPONSEFORMAT=VOTABLE&MAXREC=100000';
const browser=await chromium.launch();const page=await browser.newPage();
const result={started_at:new Date().toISOString(),url,browser:browser.version(),attempts:1,scope:'Direct browser navigation, not Python transport or application API',network:[]};
page.on('requestfailed',r=>result.network.push({url:r.url(),failure:r.failure()}));
const start=performance.now();
try{
 const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:20000});
 if(!response)throw new Error('No browser response object');
 result.http_status=response.status();result.headers=await response.allHeaders();
 const body=await response.body();fs.writeFileSync(`${out}/response.bin`,body);result.bytes=body.length;result.sha256=crypto.createHash('sha256').update(body).digest('hex');
 result.body_prefix=body.toString('utf8').slice(0,400);
}catch(error){result.error=String(error);}
result.elapsed_seconds=(performance.now()-start)/1000;
fs.writeFileSync(`${out}/result.json`,JSON.stringify(result,null,2));console.log(JSON.stringify(result));await browser.close();
