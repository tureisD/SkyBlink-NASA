/** Real saved observations; metadata-only test variations never enter products. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
async function loadModule(relative, transform = value => value) {
  const text = transform(fs.readFileSync(path.join(root, relative), "utf8"));
  const { outputText } = ts.transpileModule(text, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}
const api = await loadModule("src/lib/api.ts", text => text.replaceAll("import.meta.env", "({})"));
api.assertDataAccess("archive", "archive");
api.assertDataAccess("saved", "saved");
api.assertDataAccess(undefined, "archive");
assert.throws(() => api.assertDataAccess("saved", "archive"), /source mismatch/);
assert.throws(() => api.assertDataAccess("archive", "saved"), /source mismatch/);
const targets = await loadModule("src/lib/targets.ts");
const profile = JSON.parse(fs.readFileSync(path.join(root, "../backend/core/staged_astrometry.json"), "utf8"));
for (const target of profile.targets) {
  const corrected = targets.targetSeed(target.target_id, "archive");
  assert.equal(corrected.ra, target.query_2025_8_tt.ra_deg);
  assert.equal(corrected.dec, target.query_2025_8_tt.dec_deg);
  const historical = JSON.parse(fs.readFileSync(path.join(root, "../golden_cache", target.target_id, "manifest.json"), "utf8"));
  const saved = targets.targetSeed(target.target_id, "saved");
  assert.equal(saved.ra, historical.query.ra);
  assert.equal(saved.dec, historical.query.dec);
}
for (const source of ["archive", "saved"]) {
  const target = targets.targetSeed("wise_0855", source);
  for (const build of [api.buildSkyUrl, api.buildSpectrumUrl]) {
    const url = new URL(build({source, ra:target.ra,dec:target.dec,target:target.id,size:0.2}), "https://example.invalid");
    assert.equal(url.searchParams.get("source"), source);
    assert.equal(Number(url.searchParams.get("ra")), target.ra);
    assert.equal(Number(url.searchParams.get("dec")), target.dec);
  }
}
const boundary = new URL(api.buildSkyUrl({ra:359.9999999,dec:90,target:null,size:0.2}), "https://example.invalid");
assert.equal(boundary.searchParams.get("source"), "archive");
assert.equal(Number(boundary.searchParams.get("ra")), 359.9999999);
assert.equal(boundary.searchParams.has("target_id"), false);
// Exercise actual URL parsing/serialization without mounting React. Hook imports
// are unused by these pure functions; no observation payload is generated here.
const urls = await loadModule("src/hooks/useUrlState.ts", text => text
  .replace(/^import .*;\r?\n/gm, "")
  .replace("function parseUrl(", "export function parseUrl(")
  .replace("function serialise(", "export function serialise(")
  .replaceAll("KNOWN_TARGET_IDS.has(target)", "['wise_0855','barnards_star','eps_indi_b','rw_aurigae','r_draconis'].includes(target)"));
for (const source of ["archive", "saved"]) {
  const parsed = urls.parseUrl(`?source=${source}&target=wise_0855`);
  assert.equal(parsed.state.source, source);
  assert.equal(new URLSearchParams(urls.serialise(parsed.state)).get("source"), source);
}
assert.equal(urls.parseUrl("").state.source, "archive");
assert.equal(urls.parseUrl("?source=unsupported").state.source, "archive");
assert.ok(urls.parseUrl("?source=unsupported").warnings.length);
const boundaryState = urls.parseUrl("?ra=359.9999999&dec=-90").state;
assert.equal(urls.parseUrl(`?${urls.serialise(boundaryState)}`).state.ra, 359.9999999);
const source = fs.readFileSync(path.join(root, "src/lib/semantics.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
});
const { channelStats, observationDateLabel, coordinateEpochLabel, telemetryDescription, discoveryNotice } =
  await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const read = (target, name) => JSON.parse(fs.readFileSync(path.join(root, "../golden_cache", target, name), "utf8"));
const wise = read("wise_0855", "spectrum.json");
// Metadata-only discovery variations preserve every real channel unchanged.
for (const status of ["complete", "partial", "unknown", undefined]) {
  const provenance = {...wise.provenance, discovery_status:status, missing_collections:status==="partial"?["spherex_qr3_deep"]:[]};
  api.assertSpectrumResponse({...wise, provenance});
  if (status === "partial") {
    assert.match(discoveryNotice(provenance), /Archive search incomplete; showing retrieved observations/);
    assert.match(discoveryNotice(provenance), /Coverage\/latest-epoch inventory is not complete/);
    assert.match(discoveryNotice(provenance), /spherex_qr3_deep/);
  } else assert.equal(discoveryNotice(provenance), null);
}
for (const bad of ["finished", ["complete"], true]) {
  assert.throws(()=>api.assertSpectrumResponse({...wise,provenance:{...wise.provenance,discovery_status:bad}}), /discovery status/);
}
assert.throws(()=>api.assertSpectrumResponse({...wise,provenance:{...wise.provenance,missing_collections:"spherex_dr1"}}), /missing-collection/);
assert.throws(()=>api.assertSpectrumResponse({...wise,provenance:{...wise.provenance,missing_collections:[1]}}), /missing-collection/);
const realChannel = wise.epochs.flatMap(e => e.channels).find(c => c.flux_ujy !== null && c.is_used_in_photometry);
assert.ok(realChannel);
const oneChannel = channel => ({ ...wise, epochs: [{ ...wise.epochs[0], channels: [channel] }] });

// A finite but excluded channel must never affect a claimed usable-flux summary.
const excluded = channelStats(oneChannel({ ...realChannel, is_used_in_photometry: false }));
assert.equal(excluded.finite, 1);
assert.equal(excluded.usable, 0);
assert.equal(excluded.medianFlux, null);
assert.equal(channelStats(oneChannel(realChannel)).medianFlux, realChannel.flux_ujy);

const rdra = read("r_draconis", "spectrum.json");
const nulls = channelStats(rdra);
assert.equal(nulls.total, 240);
assert.equal(nulls.finite, 0);
assert.equal(nulls.usable, 0);
assert.equal(nulls.medianFlux, null);
assert.equal(channelStats(null).total, 0);

for (const target of ["wise_0855", "barnards_star", "eps_indi_b", "rw_aurigae", "r_draconis"]) {
  const spectrum = read(target, "spectrum.json");
  const channels = spectrum.epochs.flatMap(e => e.channels);
  const stats = channelStats(spectrum);
  assert.equal(stats.total, channels.length);
  assert.ok(stats.usable <= stats.finite && stats.finite <= stats.total);
  for (const channel of channels.filter(c => c.flux_ujy !== null && c.flux_ujy < 0 && c.is_used_in_photometry)) {
    assert.equal(channelStats(oneChannel(channel)).medianFlux, channel.flux_ujy, "Preserve measured flux sign");
  }
}

const oldSky = read("r_draconis", "manifest.json");
assert.equal(oldSky.epochs[0].epoch_id, "2024_E1");
assert.match(observationDateLabel(oldSky.epochs[0]), /^Mean 2025-/);
assert.doesNotMatch(observationDateLabel(oldSky.epochs[0]), /2024/);
assert.equal(observationDateLabel(rdra.epochs[0]), "Observation dates unavailable");
// Protocol-only range scenario, using existing real recorded dates/MJDs.
const first = oldSky.epochs[0], last = oldSky.epochs.at(-1);
const range = {mjd_min:first.mjd_mean,mjd_max:last.mjd_mean,date_start_iso:first.date_iso,date_end_iso:last.date_iso};
assert.equal(observationDateLabel({observation_range:range}), `${first.date_iso} to ${last.date_iso}`);
assert.equal(coordinateEpochLabel(null), "coordinate epoch unspecified");
assert.match(coordinateEpochLabel({id:"catalog"}), /2025\.8/);

const asset = read("wise_0855", "manifest.json").epochs[0].telemetry;
assert.equal(asset.flux_band, "thermal");
const legacy = telemetryDescription(asset, "all");
assert.match(legacy.detail, /quantity metadata unavailable/);
assert.match(legacy.detail, /normalization metadata unavailable/);
assert.match(legacy.detail, /displayed image: all/);
assert.doesNotMatch(legacy.label, /Normalized/);
const known = telemetryDescription({...asset, quantity:"normalized_display_intensity",normalization_applied:true}, "all");
assert.match(known.label, /Normalized display intensity \(thermal\)/);
assert.match(known.detail, /thermal plane; displayed image: all/);
assert.match(known.detail, /not calibrated source flux/);
const unscaled = telemetryDescription({...asset,quantity:"normalized_display_intensity",normalization_applied:false}, "thermal");
assert.doesNotMatch(unscaled.label, /Normalized/);
assert.match(unscaled.detail, /normalization not applied/);
assert.doesNotMatch(unscaled.detail, /displayed image/);
console.log("Phase 4 semantics: archive/saved URL and corrected/historical coordinates; real null/excluded/signed flux, dates and telemetry passed.");
