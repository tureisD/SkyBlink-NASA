/** Isolated playback of unchanged real retained products, not a fresh archive request. */
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
import{chromium}from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const directory=path.resolve('backend/.cache/phase5/browser-retained-data');const results=[];
const browser=await chromium.launch();
for(const target of['eps_indi_b','r_draconis','wise_0855']){
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const skyBody=fs.readFileSync(path.join(directory,`${target}-sky.json`),'utf8');const spectrumBody=fs.readFileSync(path.join(directory,`${target}-spectrum.json`),'utf8');
 const sky=JSON.parse(skyBody),spectrum=JSON.parse(spectrumBody);
 await page.route('**/api/v1/sky?*',route=>route.fulfill({status:200,contentType:'application/json',body:skyBody}));
 await page.route('**/api/v1/spectrum?*',route=>route.fulfill({status:200,contentType:'application/json',body:spectrumBody}));
 await page.goto(`http://127.0.0.1:5176/?source=archive&target=${target}`);await page.locator('.blink-canvas').first().waitFor();
 if(sky.epochs.length===1){assert.equal(await page.getByRole('button',{name:'Play blink',exact:true}).isDisabled(),true);}
 await page.getByRole('button',{name:'Spectrum',exact:true}).first().click();await page.locator('.spectrum-counts').waitFor();
 const samples=spectrum.epochs.flatMap(epoch=>epoch.channels.map(channel=>({epoch,channel})));
 const finite=samples.filter(s=>s.channel.flux_ujy!==null),eligible=finite.filter(s=>s.channel.is_used_in_photometry&&!s.channel.is_flagged_bad);
 assert.equal(await page.locator('.spectrum-plot').count(),finite.length?1:0);
 assert.equal(await page.locator('[data-no-eligible]').count(),eligible.length?0:1);
 const sample=finite.find(s=>!s.channel.is_used_in_photometry)??samples[0];
 await page.locator('.spec-table-wrap summary').click();
 if(!await page.getByRole('button',{name:`Inspect ${sample.epoch.epoch_id} detector ${sample.channel.detector} at ${sample.channel.wavelength_um.toFixed(3)} micrometers`,exact:true}).isVisible())await page.locator('.spec-table-wrap summary').click();
 await page.getByRole('button',{name:`Inspect ${sample.epoch.epoch_id} detector ${sample.channel.detector} at ${sample.channel.wavelength_um.toFixed(3)} micrometers`,exact:true}).click();
 if(finite.length&&!eligible.length)assert.match(await page.locator('.spectrum-selection').innerText(),/Excluded/);
 assert.ok((await page.locator('.spectrum-selection').innerText()).includes(sample.channel.input_id));
 const record=await page.request.get(`http://127.0.0.1:5176${spectrum.provenance.analysis_record_url}`);assert.equal(record.status(),200);
 results.push({target,skyEpochs:sky.epochs.length,recorded:samples.length,finite:finite.length,eligible:eligible.length,lineageLinkStatus:record.status(),scope:'Retained real Phase4 responses serialized by current API; isolated browser routing, no fresh upstream calls'});
 await page.close();
}
await browser.close();fs.writeFileSync(path.join(directory,'browser-results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));
