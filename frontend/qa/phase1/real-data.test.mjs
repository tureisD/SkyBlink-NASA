/** Real cache-derived payloads; negative cases mutate protocol metadata only. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
async function loadTs(relative) {
  const source = fs.readFileSync(path.join(root, relative), "utf8").replaceAll("import.meta.env", "({})");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}
const api = await loadTs("src/lib/api.ts");
const gaia = await loadTs("src/lib/gaia.ts");
const golden = path.resolve(root, "../golden_cache");
for (const target of ["wise_0855", "barnards_star", "eps_indi_b", "rw_aurigae", "r_draconis"]) {
  const read = (name) => JSON.parse(fs.readFileSync(path.join(golden, target, name), "utf8"));
  const manifest = read("manifest.json");
  // The API supplies this fixed grid; the observations below remain unchanged.
  const sky = { ...manifest, wcs: { width: 240 } };
  const spectrum = read("spectrum.json");
  api.assertSkyResponse(sky);
  api.assertSpectrumResponse(spectrum);
  for (const [validate, payload] of [[api.assertSkyResponse, sky], [api.assertSpectrumResponse, spectrum]]) {
    for (const marker of [true, undefined, "false"]) {
      assert.throws(() => validate({ ...payload, provenance: { ...payload.provenance, is_simulated_fallback: marker } }), /real observations|simulated data/);
    }
  }
  const catalog = read("gaia_dr3.json");
  assert.ok(gaia.parseGaiaCatalog(catalog).sources.length > 0);
  for (const marker of [true, undefined, "false"]) {
    assert.throws(() => gaia.parseGaiaCatalog({ ...catalog, is_simulated_fallback: marker }), /real observations/);
  }
}
for (const url of ["/mock/manifest.json", "https://example.org/mock/a.webp", "/api/v1/assets/fallback_wise_0855/a.webp", "/%6dock/a.webp", "data:image/webp;base64,AA==", "javascript:alert(1)", "file:///private.json"]) {
  assert.throws(() => api.resolveAssetUrl(url), /not supported/);
}
assert.equal(api.resolveAssetUrl("/api/v1/assets/wise_0855/a.webp"), "/api/v1/assets/wise_0855/a.webp");
console.log("Five real target payloads accepted; simulated/unknown provenance and retired URLs rejected.");
