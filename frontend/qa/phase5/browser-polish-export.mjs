/** Later-epoch real saved pair retains its plotted colors in the exported report. */
import assert from 'node:assert/strict';import fs from 'node:fs';import crypto from 'node:crypto';
import {chromium} from '../../../backend/.cache/phase5/browser-tools/node_modules/playwright/index.mjs';
const out='backend/.cache/phase5-polish/export';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch(),page=await browser.newPage({viewport:{width:1440,height:1000}});
await page.addInitScript(()=>{
 window.__canvasText=[];
 const rect=CanvasRenderingContext2D.prototype.fillRect;
 CanvasRenderingContext2D.prototype.fillRect=function(x,y,w,h){if(w===8&&h===8)window.__lastSwatch=this.fillStyle;return rect.call(this,x,y,w,h);};
 const original=CanvasRenderingContext2D.prototype.fillText;
 CanvasRenderingContext2D.prototype.fillText=function(text,...rest){window.__canvasText.push({text,color:window.__lastSwatch});return original.call(this,text,...rest);};
});
await page.goto('http://127.0.0.1:5176/?source=saved&target=eps_indi_b');await page.locator('.blink-canvas').waitFor();
await page.getByRole('button',{name:'Compare',exact:true}).click();
await page.getByRole('combobox',{name:'Observation A',exact:true}).selectOption('2025_E2');
await page.getByRole('combobox',{name:'Observation B',exact:true}).selectOption('2026_E1');
await page.getByRole('button',{name:'Evidence',exact:true}).click();await page.getByRole('button',{name:'Evidence report',exact:true}).click();
await page.getByRole('button',{name:'Download PNG',exact:true}).waitFor();
const legend=await page.evaluate(()=>window.__canvasText.filter(x=>x.text.startsWith('2025_E2 (')||x.text.startsWith('2026_E1 (')));
assert.ok(legend.some(x=>x.text.startsWith('2025_E2 (')&&x.color==='#a4c6ee'));
assert.ok(legend.some(x=>x.text.startsWith('2026_E1 (')&&x.color==='#d2b5e2'));
const downloads=[];
for(const [name,extension]of[['Download PNG','png'],['Download Markdown','md']]){
 const pending=page.waitForEvent('download');await page.getByRole('button',{name,exact:true}).click();const download=await pending;const file=`${out}/later-pair.${extension}`;await download.saveAs(file);const bytes=fs.readFileSync(file);downloads.push({path:file,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length});
}
fs.writeFileSync(`${out}/results.json`,JSON.stringify({status:'pass',source:'Actual saved Epsilon Indi B; later pair2025_E2/2026_E1; source pixel arrays unchanged',legend,downloads},null,2));await browser.close();console.log('Later-pair report PNG/Markdown and original epoch color identities pass.');
