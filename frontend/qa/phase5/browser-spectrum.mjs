/** Browser regression against real explicit-saved API data; never invents flux. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const output=path.resolve('backend/.cache/phase5/browser-spectrum');fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
const results=[];
try {
for(const target of ['wise_0855','eps_indi_b','r_draconis']){
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:5176/?source=saved&target=${target}`);
  await page.getByRole('button',{name:/spectrum/i}).first().waitFor();
  const responsePromise=page.waitForResponse(r=>r.url().includes('/spectrum?')&&r.status()===200);
  await page.getByRole('button',{name:/spectrum/i}).first().click();
  const observed=await responsePromise;
  const spectrum=await (await page.request.get(observed.url())).json();
  await page.locator('.spectrum-counts').waitFor();
  const channels=spectrum.epochs.flatMap(e=>e.channels),finite=channels.filter(c=>Number.isFinite(c.flux_ujy)&&c.flux_ujy!==null);
  assert.equal(await page.locator('[data-molecular-reference]').count(),0);
  if(finite.length){
    const plot=page.locator('.spectrum-plot');
    const lower=Number(await plot.getAttribute('data-domain-min')),upper=Number(await plot.getAttribute('data-domain-max'));
    for(const channel of finite){assert.ok(lower<=channel.flux_ujy-(channel.flux_err_ujy??0));assert.ok(upper>=channel.flux_ujy+(channel.flux_err_ujy??0));}
    assert.equal(await plot.locator('path').count(),0,'Sparse samples must not be joined');
    assert.equal(await page.locator('[data-spectrum-point]').count(),finite.length);
    await plot.focus();await page.keyboard.press('Home');
    assert.equal(await page.locator('[data-selected="true"]').count(),1);
    await page.keyboard.press('End');
    assert.equal(await page.locator('[data-selected="true"]').count(),1);
    await page.getByRole('checkbox',{name:'Show molecular reference wavelengths'}).check();
    assert.equal(await page.locator('[data-molecular-reference]').count(),spectrum.molecular_features.length);
    await page.getByRole('checkbox',{name:'Show molecular reference wavelengths'}).uncheck();
    await page.screenshot({path:path.join(output,`${target}-signed-spectrum.png`),fullPage:true});
    results.push({target,total:channels.length,finite:finite.length,negative:finite.filter(c=>c.flux_ujy<0).length,lower,upper});
  }else{
    assert.equal(await page.locator('.spectrum-plot').count(),0);
    assert.match(await page.locator('[data-no-eligible]').innerText(),/No usable flux measurements/);
    await page.getByRole('button',{name:/Inspect .* detector/}).first().click();
    assert.match(await page.locator('.spectrum-selection').innerText(),/No flux measurement/);
    await page.getByRole('button',{name:'Export channel metadata CSV'}).waitFor();
    await page.screenshot({path:path.join(output,`${target}-unavailable.png`),fullPage:true});
    results.push({target,total:channels.length,finite:0,allNullState:true});
  }
  assert.deepEqual(errors,[]);await page.close();
}
fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));
}finally{await browser.close();}
