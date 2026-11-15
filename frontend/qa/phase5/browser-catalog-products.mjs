/** Layout regression with unchanged retained real API bodies and actual immutable assets. */
import assert from 'node:assert/strict';import fs from 'node:fs';import crypto from 'node:crypto';import path from 'node:path';
import {chromium,firefox,webkit} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='backend/.cache/phase5-catalog-reliability/products';fs.mkdirSync(out,{recursive:true});const results=[];
const cases=[
 {name:'matched',target:'barnards_star',path:'backend/.cache/phase5/comparison-first/evidence/barnards_star-response.json',title:null},
 {name:'single_download',target:'wise_0855',path:'backend/.cache/phase5/browser-retained-data/wise_0855-sky.json',title:'Some downloads did not complete'},
 {name:'partial_discovery',target:'eps_indi_b',path:'backend/.cache/phase5/comparison-first/evidence/final/eps_indi_b-response.json',title:'Archive search incomplete'},
];
for(const [engineName,engine]of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();
 for(const item of cases){
  const width=item.name==='matched'?1440:390,body=fs.readFileSync(item.path,'utf8'),sky=JSON.parse(body);
  const context=await browser.newContext({viewport:{width,height:width===1440?1080:844}}),page=await context.newPage();
  const row={engine:engineName,case:item.name,width,source:{path:item.path,sha256:crypto.createHash('sha256').update(body).digest('hex')},requests:[],assets:[],checks:[]};results.push(row);
  await page.route('**/api/v1/sky?*',route=>{row.requests.push(route.request().url());return route.fulfill({status:200,contentType:'application/json',body});});
  // The acquisition run used an isolated cache. Serve those exact retained bytes,
  // without copying them into the normal runtime cache or rewriting the response.
  const assetRoot=item.name==='single_download'?'backend/.cache/live':'backend/.cache/phase5/comparison-first/live';
  await page.route('**/api/v1/assets/**',async route=>{
   const relative=new URL(route.request().url()).pathname.split('/api/v1/assets/')[1];const source=path.resolve(assetRoot,relative);
   assert.ok(source.startsWith(path.resolve(assetRoot)+path.sep));
   if(!fs.existsSync(source))return route.abort('failed');
   const bytes=fs.readFileSync(source);row.assets.push({url:relative,path:source,sha256:crypto.createHash('sha256').update(bytes).digest('hex')});
   await route.fulfill({status:200,contentType:source.endsWith('.webp')?'image/webp':source.endsWith('.json')?'application/json':'application/octet-stream',body:bytes});
  });
  try{
   await page.goto(`http://127.0.0.1:5176/?source=archive&target=${item.target}`);await page.locator('.blink-canvas').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.canvas-status'));
   assert.equal(await page.locator('#comparison-notification').isVisible(),false);
   await page.getByRole('button',{name:/^Comparison details/}).click();
   await page.locator('#comparison-notification').waitFor();
   assert.equal(await page.locator('#root').evaluate(e=>e.inert),false);
   row.checks.push('details_not_expanded_by_default','nonmodal_details_outside_image');
   if(item.title){
    assert.equal(sky.epochs.length,1);await page.getByRole('heading',{name:item.title,exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Play blink',exact:true}).isDisabled(),true);
    const before=row.requests.length;await page.getByRole('button',{name:'Retry comparison',exact:true}).click();await page.locator('.blink-canvas').first().waitFor();
    if(!await page.locator('#comparison-notification').isVisible())await page.getByRole('button',{name:/^Comparison details/}).click();
    await page.getByRole('heading',{name:item.title,exact:true}).waitFor();
    assert.ok(row.requests.length>before);assert.ok(row.requests.every(url=>url===row.requests[0]));
    await page.getByRole('button',{name:'Compare',exact:true}).click();assert.equal(await page.getByRole('combobox',{name:'Observation B',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('button',{name:'Try a 0.05 degree field'}).count(),0);
    row.checks.push('real_single_epoch_not_blinkable','specific_limitation_preserved','retry_same_archive_query','B_unavailable','no_unjustified_smaller_field');
   }else{
    assert.equal(sky.provenance.comparison_status,'matched_visual');assert.equal(sky.epochs.length,2);
    await page.getByRole('button',{name:'Play blink',exact:true}).click();await page.getByRole('button',{name:'Pause',exact:true}).click();
    await page.getByRole('button',{name:'Compare',exact:true}).click();await page.getByRole('button',{name:'Side by side',exact:true}).click();assert.equal(await page.locator('.blink-canvas').count(),2);
    row.frameHashes=sky.epochs.map(epoch=>{const relative=epoch.frames.all.split('/api/v1/assets/')[1];const asset=row.assets.find(a=>a.url===relative);assert.ok(asset,'Actual frame bytes were served');return asset.sha256;});assert.notEqual(row.frameHashes[0],row.frameHashes[1]);
    const diff=page.getByRole('checkbox',{name:'Difference (B minus A)'});await diff.check();assert.ok(await diff.isChecked());
    row.checks.push('real_matched_pair','play_pause','distinct_real_AB_assets','paired_canvas','difference_enabled');
   }
   assert.equal(new URL(page.url()).searchParams.get('source'),'archive');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   row.status='pass';
  }catch(error){row.status='failed';row.failure=error.stack;await page.screenshot({path:`${out}/${engineName}-${item.name}-failure.png`,fullPage:true}).catch(()=>{});}
  await context.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify({scope:'Isolated unchanged real-response replay, actual local immutable assets, no new upstream acquisition',results},null,2));console.log(JSON.stringify({engine:engineName,case:item.name,status:row.status,failure:row.failure?.split('\n')[0]}));
 }
 await browser.close();
}
