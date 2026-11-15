/** Pure view/transport tests. Observation bytes come only from real saved products.
 * Invalid URLs and interrupted requests are isolated protocol inputs, not data.
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import ts from "typescript";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const moduleCache = new Map();
async function moduleUrl(relative) {
  if (moduleCache.has(relative)) return moduleCache.get(relative);
  let source = fs.readFileSync(path.join(root, relative), "utf8").replaceAll("import.meta.env", "({})");
  if (relative.endsWith("useUrlState.ts")) source = source
    .replace(/^import .* from "react";\r?\n/m, "")
    .replace("function parseUrl(", "export function parseUrl(")
    .replace("function serialise(", "export function serialise(");
  if (relative.endsWith("useRecentFields.ts")) source = source
    .replace(/^import .* from "react";\r?\n/m, "")
    .replace("function readRecent(", "export function readRecent(");
  if (relative.endsWith("triage.ts")) source = source.replace("function buildMarkdown(", "export function buildMarkdown(");
  let { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  });
  const imports = [...outputText.matchAll(/from ["'](\.[^"']+)["']/g)];
  for (const match of imports) {
    const dependency = path.posix.normalize(path.posix.join(path.posix.dirname(relative), match[1] + ".ts"));
    outputText = outputText.replace(match[0], `from "${await moduleUrl(dependency)}"`);
  }
  const url = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
  moduleCache.set(relative, url);
  return url;
}
const load = async relative => import(await moduleUrl(relative));
const urls = await load("src/hooks/useUrlState.ts");
const share = await load("src/lib/share.ts");
const api = await load("src/lib/api.ts");
// Protocol reason tests: no additional observation payloads.
const recovery = await load("src/lib/comparisonRecovery.ts");
const partial = recovery.comparisonRecovery("PARTIAL_DOWNLOAD_NO_MATCHED_PAIR");
assert.match(partial.explanation, /Some downloads did not complete/);
assert.match(partial.explanation, /completed observations did not establish/);
assert.doesNotMatch(partial.explanation, /prevented a matched pair/);
assert.equal(partial.smallerFieldMayHelp, false);
assert.equal(recovery.comparisonRecovery("NO_MATCHED_PAIR_IN_BOUNDED_SAMPLE").smallerFieldMayHelp, true);
assert.match(recovery.comparisonRecovery("COMPARISON_SEARCH_BUDGET_REACHED").title, /time limit/);
assert.match(recovery.comparisonRecovery("UNKNOWN_NEW_CODE").explanation, /unrecorded or not recognized/);
const incompleteSearch = recovery.comparisonRecovery(null, "partial");
assert.equal(incompleteSearch.title, "Archive search incomplete");
assert.match(incompleteSearch.explanation, /Some archive collections were unavailable/);
assert.match(incompleteSearch.explanation, /not a finding that the archive contains only one epoch/);
assert.equal(incompleteSearch.smallerFieldMayHelp, false);
assert.doesNotMatch(incompleteSearch.explanation, /specific limitation is unrecorded/);
assert.equal(recovery.comparisonRecovery(undefined, "partial").title, incompleteSearch.title);
assert.match(recovery.comparisonRecovery(null, "complete").explanation, /unrecorded or not recognized/);
assert.equal(recovery.comparisonRecovery("PARTIAL_DOWNLOAD_NO_MATCHED_PAIR", "partial").title, partial.title);
// Isolated error envelopes exercise distinctions without inventing observations.
const protocolError = (status, code, message = "isolated protocol test") => new api.ApiError(status, code, message, null);
assert.match(api.skyRequestError(protocolError(404, "NO_DATA"), "archive"), /No displayable/);
assert.match(api.skyRequestError(protocolError(404, "NO_DATA"), "archive"), /pixels may be unusable/);
assert.match(api.skyRequestError(protocolError(404, "NO_DATA"), "saved"), /saved example is unavailable/);
assert.match(api.skyRequestError(protocolError(503, "UPSTREAM_UNAVAILABLE"), "archive"), /does not establish missing sky coverage/);
assert.match(api.skyRequestError(protocolError(408, "REQUEST_TIMEOUT"), "archive"), /coverage is still unknown/);
assert.match(api.skyRequestError(protocolError(400, "INVALID_COORDINATES"), "archive"), /coordinates were rejected/);
assert.match(api.skyRequestError(protocolError(422, "VALIDATION_ERROR"), "archive"), /settings were rejected/);
assert.match(api.skyRequestError(protocolError(404, "NO_COMPARABLE"), "archive"), /No comparable observation pair/);
assert.doesNotMatch(api.skyRequestError(protocolError(500, "INTERNAL_ERROR", "NO_COMPARABLE no data"), "archive"), /No comparable|No displayable/);
assert.match(api.skyRequestError(protocolError(404, "HTTP_404"), "archive"), /coverage is unknown/);
assert.match(api.skyRequestError(new Error("NO_DATA"), "archive"), /coverage is unknown/);
assert.match(api.skyRequestError(new Error("network"), "saved"), /Archive coverage was not checked/);
const triage = await load("src/lib/triage.ts");
const semantics = await load("src/lib/semantics.ts");
// Metadata-only wording boundary: an intentionally known inventory is not a
// failed new search or evidence that any particular collection is unavailable.
assert.match(semantics.discoveryNotice({ discovery_mode: "known", discovery_status: "partial" }), /no new archive search/);
assert.doesNotMatch(semantics.discoveryNotice({ discovery_mode: "known", discovery_status: "partial" }), /Missing collections|search incomplete|unavailable/);
const knownSingle = recovery.comparisonRecovery(null, "partial", "known");
assert.equal(knownSingle.title, "Known exposure list");
assert.match(knownSingle.explanation, /No new archive search was performed/);
assert.doesNotMatch(knownSingle.explanation, /collections were unavailable/);
assert.equal(knownSingle.smallerFieldMayHelp, false);
const raw = fs.readFileSync(path.join(root, "../golden_cache/eps_indi_b/manifest.json"), "utf8");
const manifest = JSON.parse(raw);
// Saved storage wraps frame maps; the API flattens these same asset references.
manifest.differences = Object.fromEntries(Object.entries(manifest.differences).map(([key, value]) => [key, value.frames]));
const identity = `sha256:${createHash("sha256").update(raw).digest("hex")}`;
const realPair = Object.keys(manifest.differences).find(key => manifest.differences[key]["3"]);
assert.ok(realPair, "Real saved product must provide the selected test comparison");
const [realB, realA] = realPair.split("_minus_");

assert.equal(urls.parseUrl("").state.mode, "still");
assert.equal(urls.parseUrl("").state.discovery, "live");
const knownState = urls.parseUrl("?source=archive&target=wise_0855&discovery=known").state;
assert.equal(knownState.discovery, "known");
assert.equal(urls.parseUrl(urls.serialise(knownState)).state.discovery, "known");
for (const invalid of ["?source=saved&target=wise_0855&discovery=known", "?source=archive&ra=123&dec=10&discovery=known", "?discovery=unexpected"])
  assert.equal(urls.parseUrl(invalid).state.discovery, "live");
for (const build of [api.buildSkyUrl, api.buildSpectrumUrl]) {
  const request = { source: "archive", target: "wise_0855", ra: manifest.query.ra, dec: manifest.query.dec, size: .2 };
  assert.equal(new URL(build(request), "https://example.invalid").searchParams.get("discovery"), "live");
  assert.equal(new URL(build({ ...request, discovery: "known" }), "https://example.invalid").searchParams.get("discovery"), "known");
}
assert.doesNotThrow(() => api.assertDiscoveryMode("known", "known", "archive"));
assert.doesNotThrow(() => api.assertDiscoveryMode(undefined, "live", "archive"));
for (const actual of [undefined, null, "live", "unexpected", 1])
  assert.throws(() => api.assertDiscoveryMode(actual, "known", "archive"));
assert.throws(() => api.assertDiscoveryMode("known", "known", "saved"));
assert.throws(() => api.assertDiscoveryMode("known", "live", "archive"));
const recent = await load("src/hooks/useRecentFields.ts");
const recentQuery = { ra: manifest.query.ra, dec: manifest.query.dec, size: .2, target: "eps_indi_b", source: "archive", name: "Epsilon Indi B" };
globalThis.localStorage = { getItem: () => JSON.stringify([
  { ...recentQuery, discovery: "known", epochs: manifest.epochs },
  recentQuery,
  { ...recentQuery, source: "saved", discovery: "known" },
  { ...recentQuery, target: null, discovery: "known" },
]) };
const historyEntries = recent.readRecent();
assert.equal(historyEntries.length, 2);
assert.deepEqual(historyEntries.map(entry => entry.discovery), ["known", "live"]);
assert.deepEqual(Object.keys(historyEntries[0]).sort(), ["dec", "discovery", "name", "ra", "size", "source", "spectrumDiscovery", "target"]);
assert.deepEqual(historyEntries.map(entry => entry.spectrumDiscovery), ["inherit", "inherit"]);
globalThis.localStorage = { getItem: () => JSON.stringify([
  { ...recentQuery, spectrumDiscovery: "known" },
  { ...recentQuery, source: "saved", spectrumDiscovery: "known" },
  { ...recentQuery, target: null, spectrumDiscovery: "known" },
  { ...recentQuery, spectrumDiscovery: "unexpected" },
]) };
assert.equal(recent.readRecent().length, 1);
assert.equal(recent.readRecent()[0].spectrumDiscovery, "known");
const independentSpectrum = urls.parseUrl("?source=archive&target=rw_aurigae&discovery=live&spectrumDiscovery=known").state;
assert.equal(independentSpectrum.discovery, "live");
assert.equal(independentSpectrum.spectrumDiscovery, "known");
assert.equal(urls.parseUrl(urls.serialise(independentSpectrum)).state.spectrumDiscovery, "known");
assert.equal(urls.parseUrl("").state.spectrumDiscovery, "inherit");
for (const invalid of ["?source=saved&target=wise_0855&spectrumDiscovery=known", "?source=archive&ra=123&dec=10&spectrumDiscovery=known", "?spectrumDiscovery=unexpected"])
  assert.equal(urls.parseUrl(invalid).state.spectrumDiscovery, "inherit");
delete globalThis.localStorage;
assert.deepEqual(urls.parseUrl("").state.overlay, ["scale", "compass"]);
assert.equal(urls.parseUrl("?mode=blink").state.mode, "still");
assert.equal(urls.parseUrl("?mode=blink", false).state.mode, "blink");
const state = { ...urls.parseUrl("").state, source: "saved", target: "eps_indi_b",
  ra: manifest.query.ra, dec: manifest.query.dec, size: .123456, bands: "3",
  epoch: realA, epochA: realA, epochB: realB, pair: realPair,
  analysis: identity, colormap: "inferno", stretch: "asinh", contrast: 1.76, bias: -.12,
  pingpong: true, zoom: 3.25, panX: -.1234, panY: .2345, task: "compare", advanced: true,
  comparisonLayout: "side-by-side", track: true, pmra: -12.3456, pmdec: 23.4567, parallax: true, au: 12.34,
};
const encoded = urls.serialise(state);
assert.equal(new URLSearchParams(encoded).get("v"), "1");
assert.deepEqual(urls.parseUrl(encoded).state, state);
assert.equal(new URL(api.buildSkyUrl({ ...state, target: state.target }), "https://example.invalid").searchParams.get("size"), ".123456".replace(/^\./, "0."));
assert.ok(urls.parseUrl("?v=999&source=saved&target=eps_indi_b").warnings.some(value => /unsupported/.test(value)));
assert.equal(urls.parseUrl("?v=999&target=eps_indi_b").state.target, null);
const invalid = urls.parseUrl("?ra=NaN&dec=90&fps=999&contrast=Infinity&panX=999&epochA=garbage&analysis=bad&pair=bad&colormap=bad&source=saved&source=archive");
assert.equal(invalid.state.ra, null);
assert.equal(invalid.state.dec, null);
assert.equal(invalid.state.fps, 8);
assert.equal(invalid.state.panX, 2);
assert.equal(invalid.state.contrast, 1);
assert.equal(invalid.state.analysis, null);
assert.ok(invalid.warnings.length >= 8);
for (const [ra, dec] of [[359.9999999, 90], [0, -90]]) {
  const edge = urls.parseUrl(`?ra=${ra}&dec=${dec}`).state;
  assert.deepEqual([urls.parseUrl(urls.serialise(edge)).state.ra, edge.dec], [ra, dec]);
}
globalThis.window = { matchMedia: () => ({ matches: true }) };
assert.equal(urls.parseUrl("?mode=blink", false).state.mode, "still");
delete globalThis.window;
assert.equal(share.analysisIdentityNotice(identity, identity), null);
assert.match(share.analysisIdentityNotice(identity, null), /cannot be verified/);
assert.match(share.analysisIdentityNotice(identity, `sha256:${"0".repeat(64)}`), /differs/);
assert.deepEqual(share.selectionWarnings(state, manifest), []);
assert.ok(share.selectionWarnings({ ...state, epochA: "1900_E99" }, manifest).length);

const selected = triage.selectTriageEpochs(manifest, state.bands, state.pair, state.epochA, state.epochB);
assert.equal(selected.band, state.bands);
assert.deepEqual(selected.epochs.map(epoch => epoch.epoch_id), [state.epochA, state.epochB]);
assert.equal(selected.diffUrl, manifest.differences[state.pair][state.bands]);
const single = triage.selectTriageEpochs(manifest, state.bands, null, state.epochB, null);
assert.deepEqual(single.epochs.map(epoch => epoch.epoch_id), [state.epochB]);
assert.equal(single.diffUrl, null);
const unavailableBand = triage.selectTriageEpochs(manifest, "not-a-band", state.pair, state.epochA, state.epochB);
assert.equal(unavailableBand.band, "not-a-band");
assert.equal(unavailableBand.diffUrl, null);
assert.throws(() => triage.selectTriageEpochs(manifest, state.bands, state.pair, state.epochB, state.epochA), /does not match/);
assert.throws(() => triage.selectTriageEpochs(manifest, state.bands, null, "1900_E99", null), /unavailable/);
const spectrum = JSON.parse(fs.readFileSync(path.join(root, "../golden_cache/eps_indi_b/spectrum.json"), "utf8"));
const fullEpochOrder = spectrum.epochs.map(epoch => epoch.epoch_id);
for (const [subsetIndex, epoch] of spectrum.epochs.slice(-2).entries()) {
  assert.equal(triage.spectrumEpochColorIndex(epoch.epoch_id, subsetIndex, fullEpochOrder), fullEpochOrder.indexOf(epoch.epoch_id));
}
const realNullSpectrum = JSON.parse(fs.readFileSync(path.join(root, "../golden_cache/r_draconis/spectrum.json"), "utf8"));
const nullOrder = realNullSpectrum.epochs.map(epoch => epoch.epoch_id);
assert.equal(triage.spectrumEpochColorIndex(nullOrder[nullOrder.length - 1], 0, nullOrder), nullOrder.length - 1);

const selectedSpectrum = { ...spectrum, epochs: spectrum.epochs.filter(epoch => [state.epochA, state.epochB].includes(epoch.epoch_id)) };
const markdown = triage.buildMarkdown({ ...selected, manifest, spectrum: selectedSpectrum,
  gaia: { status: "idle", sources: [], isSimulatedFallback: false, attribution: null, error: null },
  shareUrl: `https://example.invalid/?${encoded}` }, semantics.channelStats(selectedSpectrum).total);
assert.match(markdown, new RegExp(`Epoch A:\\*\\* ${state.epochA}`));
assert.match(markdown, new RegExp(`Epoch B:\\*\\* ${state.epochB}`));
assert.match(markdown, /not a pinned-input replay/);
assert.match(markdown, /identity cannot be verified/i);
assert.match(markdown, /full frame; it does not apply the workspace camera/);

const knownReceiptPath = path.join(root, "../backend/.cache/phase5/discovery-outage/recovery-final/barnards_star-sky-known-response.json");
if (fs.existsSync(knownReceiptPath)) {
  const knownSky = JSON.parse(fs.readFileSync(knownReceiptPath, "utf8"));
  const knownPair = Object.keys(knownSky.differences)[0];
  const [knownB, knownA] = knownPair.split("_minus_");
  const selection = triage.selectTriageEpochs(knownSky, "all", knownPair, knownA, knownB);
  const report = triage.buildMarkdown({ ...selection, manifest: knownSky, spectrum: null,
    gaia: { status: "idle", sources: [], isSimulatedFallback: false, attribution: null, error: null },
    shareUrl: "https://example.invalid/?source=archive&target=barnards_star&discovery=known" }, 0);
  assert.match(report, /Sky discovery mode:\*\* known/);
  assert.match(report, /No new archive coverage search/);
  for (const epoch of knownSky.epochs) {
    assert.ok(report.includes(epoch.observation_range.date_start_iso));
    assert.ok(report.includes(epoch.mjd_mean.toFixed(2)));
  }
  console.log("Actual known Barnard report preserves discovery mode and observed dates; epoch IDs are not compared across inventories.");
} else console.log("Known-receipt export check unavailable: local ignored archive receipt is absent.");

const originalFetch = globalThis.fetch;
// Real independently acquired inventories must not be joined by epoch label.
const phase6SkyPath = path.join(root, "../backend/.cache/phase5/recurrent-download-diagnosis/final/rw_aurigae-response.json");
const phase6SpectrumPath = path.join(root, "../backend/.cache/phase6/spectrum-final/rw_aurigae-known-response.json");
if (fs.existsSync(phase6SkyPath) && fs.existsSync(phase6SpectrumPath)) {
  const sky = JSON.parse(fs.readFileSync(phase6SkyPath, "utf8"));
  const native = JSON.parse(fs.readFileSync(phase6SpectrumPath, "utf8"));
  const ids = new Set([sky.epochs[0].epoch_id]);
  assert.equal(triage.selectSpectrumForReport(sky, native, ids), native);
  const key = Object.keys(sky.differences)[0];
  const [b, a] = key.split("_minus_");
  const report = triage.buildMarkdown({ ...triage.selectTriageEpochs(sky, "all", key, a, b), manifest: sky, spectrum: native,
    gaia: { status: "idle", sources: [], isSimulatedFallback: false, attribution: null, error: null },
    shareUrl: "https://example.invalid/?source=archive&target=rw_aurigae&spectrumDiscovery=known" }, semantics.channelStats(native).total);
  assert.match(report, /epoch IDs are not matched across these inventories/);
  assert.match(report, /Spectrum discovery mode: known/);
  console.log("Actual live image/known spectrum report retains native epochs and labels separate inventory.");
} else console.log("Cross-inventory real receipt test unavailable: ignored Phase 6 inputs absent.");
assert.deepEqual(triage.selectSpectrumForReport(manifest, spectrum, new Set([state.epochA])).epochs.map(epoch => epoch.epoch_id), [state.epochA]);
for (const reason of ["SERVER_BUSY", "STORAGE_UNAVAILABLE", "STORAGE_BUDGET_EXCEEDED", "PROCESSING_SOURCE_CHANGED"]) {
  const error = new api.ApiError(503, "UPSTREAM_UNAVAILABLE", "server detail", { reason });
  assert.equal(api.canRecoverKnownExposures(error), false);
}
assert.equal(api.canRecoverKnownExposures(protocolError(503, "UPSTREAM_UNAVAILABLE")), true);
assert.equal(api.canRecoverKnownExposures(protocolError(404, "NO_DATA")), false);
// Generated protocol error only; no observational values are invented.
const restartError = new api.ApiError(503, "UPSTREAM_UNAVAILABLE", "server detail", { reason: "PROCESSING_SOURCE_CHANGED" });
assert.equal(api.skyRequestError(restartError, "archive"), "The server needs to restart after an update before new observations can be processed. Retry once it has restarted.");
for (const error of [
  new api.ApiError(503, "UPSTREAM_UNAVAILABLE", "PROCESSING_SOURCE_CHANGED", null),
  new api.ApiError(503, "UPSTREAM_UNAVAILABLE", "server detail", { reason: "OTHER_REASON" }),
  new api.ApiError(500, "UPSTREAM_UNAVAILABLE", "server detail", { reason: "PROCESSING_SOURCE_CHANGED" }),
]) assert.doesNotMatch(api.skyRequestError(error, "archive"), /server needs to restart/);
try {
  let observedSignal;
  let calls = 0;
  globalThis.fetch = async (_url, options) => {
    calls += 1;
    observedSignal = options.signal;
    return new Promise(() => {}); // Isolated stalled transport; no response data.
  };
  await assert.rejects(api.fetchJsonWithTimeout("https://example.invalid/stalled", undefined, 10), error => error.code === "REQUEST_TIMEOUT");
  assert.equal(observedSignal.aborted, true);
  const caller = new AbortController();
  const pending = api.fetchJsonWithTimeout("https://example.invalid/cancel", caller.signal, 10_000);
  caller.abort();
  await assert.rejects(pending, api.isAbortError);
  assert.equal(observedSignal.aborted, true);
  const before = calls;
  await assert.rejects(api.fetchJsonWithTimeout("https://example.invalid/already", caller.signal), api.isAbortError);
  assert.equal(calls, before);
  globalThis.fetch = async () => new Response(raw, { status: 200, headers: { "Content-Type": "application/json" } });
  assert.deepEqual(await api.fetchJsonWithTimeout("https://example.invalid/saved", undefined, 1000), JSON.parse(raw));
} finally {
  globalThis.fetch = originalFetch;
}
console.log("Phase 5 share, selected export, and abortable transport checks passed; real saved metadata only.");
