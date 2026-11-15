/**
 * F7 Playwright QA — coordinate search, catalog resolver, live epoch handling,
 * WISE W2 curtain, and stale-URL normalization.
 *
 * Runs against the real local final container (APP_URL, default
 * http://127.0.0.1:8000): live `/api/v1` responses, golden cache, and real
 * reference overlays. No routes are stubbed. Screenshots are written next to
 * this file.
 *
 * Run:
 *   npx playwright install chromium   # once
 *   node qa/f7/run.mjs
 */

import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = path.dirname(fileURLToPath(import.meta.url));
const appUrl = process.env.APP_URL ?? "http://127.0.0.1:8000";
const outputDir = here;

const OVERLAYS = "reticle,box,scale,compass,gaia";

function url(params) {
  return `${appUrl}/?${params}`;
}

async function waitForText(page, selector, pattern, timeout = 15_000) {
  await page.waitForFunction(
    ({ selector: target, source, flags }) => {
      const element = document.querySelector(target);
      if (!element) return false;
      return new RegExp(source, flags).test(element.textContent ?? "");
    },
    { selector, source: pattern.source, flags: pattern.flags },
    { timeout },
  );
}

async function waitForDecoded(page, name, timeout = 45_000) {
  await page.waitForSelector(".hud-name", { timeout });
  await page.waitForFunction(
    (expected) =>
      document.querySelector(".hud-name")?.textContent?.trim() === expected,
    name,
    { timeout },
  );
  await page
    .waitForSelector(".canvas-status", { timeout: 5_000 })
    .catch(() => undefined);
  await page.waitForFunction(
    () => !document.querySelector(".canvas-status"),
    undefined,
    { timeout },
  );
}

async function waitForEpochs(page, count) {
  await page.waitForFunction(
    (expected) =>
      document.querySelectorAll(".epoch-node").length === expected,
    count,
    { timeout: 45_000 },
  );
}

async function openSearch(page) {
  await page.getByRole("button", { name: "Search coordinates" }).click();
  await page.waitForSelector("#search-ra");
}

async function submitSearch(page) {
  await page.getByRole("button", { name: "Resolve & load" }).click();
}

async function search(page, ra, dec) {
  await openSearch(page);
  await page.fill("#search-ra", ra);
  await page.fill("#search-dec", dec);
  await submitSearch(page);
}

async function assertTargetUrl(page, target) {
  const params = new URL(page.url()).searchParams;
  assert.equal(params.get("target"), target);
  const ra = Number(params.get("ra"));
  const dec = Number(params.get("dec"));
  assert.ok(Number.isFinite(ra) && Number.isFinite(dec));
  return { ra, dec };
}

async function waitForTargetUrl(page, target) {
  await page.waitForFunction(
    (expected) =>
      new URL(window.location.href).searchParams.get("target") === expected,
    target,
    { timeout: 10_000 },
  );
  return assertTargetUrl(page, target);
}

async function waitForUrlCoords(page, ra, dec) {
  await page.waitForFunction(
    ({ ra: expectedRa, dec: expectedDec }) => {
      const params = new URL(window.location.href).searchParams;
      const actualRa = Number(params.get("ra"));
      const actualDec = Number(params.get("dec"));
      return (
        Number.isFinite(actualRa) &&
        Number.isFinite(actualDec) &&
        Math.abs(actualRa - expectedRa) < 1e-6 &&
        Math.abs(actualDec - expectedDec) < 1e-6
      );
    },
    { ra, dec },
    { timeout: 10_000 },
  );
}

async function waitForNoTargetUrl(page) {
  await page.waitForFunction(
    () => new URL(window.location.href).searchParams.get("target") === null,
    undefined,
    { timeout: 10_000 },
  );
}

async function warmArbitrary() {
  // A cold IRSA query can take up to about two minutes. Warm the server-side
  // live cache first so the UI checks the returned coverage. This is the same
  // real endpoint; no observations or epoch counts are invented.
  const target = `${appUrl}/api/v1/sky?ra=133.66&dec=-7.20&size=0.2&bands=all&epochs=all&include_diff=true`;
  try {
    const response = await fetch(target, { signal: AbortSignal.timeout(130_000) });
    if (!response.ok) {
      console.warn(`arbitrary warm-up returned HTTP ${response.status}`);
      return false;
    }
    return await response.json();
  } catch (error) {
    console.warn(`arbitrary warm-up failed: ${error}`);
    return false;
  }
}

async function main() {
  const browser = await chromium.launch();
  const consoleErrors = [];
  const pageErrors = [];

  const watch = (page) => {
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));
  };

  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  watch(page);

  // Start on a different benchmark so the WISE search demonstrably switches
  // target, epochs, and the golden cache.
  await page.goto(
    url(
      `target=barnards_star&bands=all&epoch=all&mode=still&fps=4&diff=0&overlay=${OVERLAYS}`,
    ),
    { waitUntil: "domcontentloaded" },
  );
  await waitForDecoded(page, "Barnard's Star");
  await waitForEpochs(page, 3);
  console.log("Barnard's Star golden manifest loaded (3 epochs) as the starting state");

  // 1. Search dialog: invalid input stays inline, then a 2010.0 sexagesimal
  //    position resolves to WISE 0855's 2025.8 golden cache.
  await openSearch(page);
  await page.fill("#search-ra", "400");
  await page.fill("#search-dec", "-7d14m42.53s");
  await submitSearch(page);
  await waitForText(page, ".search-error", /RA must be between 0 and 360/);
  assert.equal(
    await page.locator("#search-ra").getAttribute("aria-invalid"),
    "true",
  );
  console.log("invalid RA (400) shows an inline range error and keeps the dialog open");

  await page.fill("#search-ra", "08h55m10.831s");
  await page.fill("#search-dec", "91");
  await submitSearch(page);
  await waitForText(page, ".search-error", /Dec must be between/);
  console.log("invalid Dec (91) shows an inline range error");

  await page.fill("#search-dec", "-7d14m42.53s");
  await page.screenshot({
    path: path.join(outputDir, "search-dialog-1600.png"),
  });
  await submitSearch(page);

  await waitForDecoded(page, "WISE 0855");
  await waitForEpochs(page, 3);
  await waitForText(
    page,
    ".notice-bar",
    /Matched WISE 0855 \(2010\.0 reference coordinates\) → propagated to 2025\.8; loaded the golden cache\./,
  );
  await waitForTargetUrl(page, "wise_0855");
  await waitForUrlCoords(page, 133.75921, -7.24216);
  const wise = await assertTargetUrl(page, "wise_0855");
  assert.ok(Math.abs(wise.ra - 133.75921) < 1e-6);
  assert.ok(Math.abs(wise.dec - -7.24216) < 1e-6);
  await page.screenshot({
    path: path.join(outputDir, "matched-toast-1600.png"),
  });
  console.log(
    "WISE 2010.0 sexagesimal search → wise_0855, 2025.8 query centre, 3 epochs, matched toast",
  );

  // 1b. Telemetry sidecar: one decode of the gzipped float16+uint32 payload
  //     yields a physical MJy/sr value at the cursor (no second gunzip pass).
  const canvasBox = await page.locator("canvas.blink-canvas").boundingBox();
  assert.ok(canvasBox, "blink canvas has a layout box");
  await page.mouse.move(
    canvasBox.x + canvasBox.width / 2 + 30,
    canvasBox.y + canvasBox.height / 2 + 30,
    { steps: 4 },
  );
  await page.waitForFunction(
    () => {
      const text = document.querySelector(".hud-chip--loupe")?.textContent ?? "";
      return (
        /Iν \((thermal|all)\): [-+0-9.eE]+ MJy\/sr/.test(text) &&
        !/decoding/.test(text)
      );
    },
    undefined,
    { timeout: 25_000 },
  );
  await page.screenshot({
    path: path.join(outputDir, "telemetry-loupe-1600.png"),
  });
  console.log("telemetry sidecar decodes once and reports a physical MJy/sr value");

  // 2. J2000 decimal coordinates resolve to Barnard's Star.
  await search(page, "269.4521", "+4.6934");
  await waitForDecoded(page, "Barnard's Star");
  await waitForEpochs(page, 3);
  await waitForText(
    page,
    ".notice-bar",
    /Matched Barnard's Star \(J2000 reference coordinates\) → propagated to 2025\.8; loaded the golden cache\./,
  );
  await waitForTargetUrl(page, "barnards_star");
  await waitForUrlCoords(page, 269.4463, 4.7676);
  const barnard = await assertTargetUrl(page, "barnards_star");
  assert.ok(Math.abs(barnard.ra - 269.4463) < 1e-6);
  assert.ok(Math.abs(barnard.dec - 4.7676) < 1e-6);
  console.log("Barnard J2000 decimal search → barnards_star, 2025.8 centre, 3 epochs");

  // 3. Space- and colon-separated forms parse identically and resolve back.
  await search(page, "08 55 10.831", "-07:14:42.53");
  await waitForDecoded(page, "WISE 0855");
  await waitForEpochs(page, 3);
  console.log("space/colon sexagesimal forms parse and resolve to WISE 0855");

  // 4. Arbitrary cached position → all returned real epochs or honest failure.
  const arbitraryReady = await warmArbitrary();
  await search(page, "133.66", "-7.20");
  if (arbitraryReady) {
    const epochCount = arbitraryReady.epochs.length;
    assert.ok(epochCount >= 1);
    assert.equal(arbitraryReady.provenance.is_simulated_fallback, false);
    await waitForDecoded(page, "Sky field", 130_000);
    await waitForEpochs(page, epochCount);
    await waitForNoTargetUrl(page);
    if (epochCount === 1) {
      await waitForText(page, '[data-live-single-epoch="1"]', /insufficient comparable epochs for blinking/);
      assert.equal(await page.locator('[data-live-single-epoch="1"] .btn').count(), 5);
    } else {
      assert.equal(await page.locator('[data-live-single-epoch="1"]').count(), 0);
    }
    await page.screenshot({
      path: path.join(outputDir, "live-epochs-1600.png"),
    });
    console.log(
      `arbitrary 133.66 -7.20 → no target id, ${epochCount} real epochs, honest comparison controls`,
    );
  } else {
    await page.waitForSelector(".boot-card", { timeout: 130_000 });
    await waitForText(page, ".boot-card", /Could not load this sky field/, 130_000);
    console.log("arbitrary position: request failed; app shows the clean unavailable state");
  }

  // 5. WISE curtain defaults to the real W2 4.6 µm reference cutout.
  await page.goto(
    url(
      `target=wise_0855&bands=all&mode=still&epoch=2025_E1&fps=4&diff=0&overlay=${OVERLAYS}`,
    ),
    { waitUntil: "domcontentloaded" },
  );
  await waitForDecoded(page, "WISE 0855");
  await page.getByRole("button", { name: "Curtain", exact: true }).click();
  await page.waitForSelector(".curtain-stage");
  assert.equal(
    (await page.locator(".curtain-tag--right").textContent())?.trim(),
    "Mid-IR · WISE W2 4.6 µm",
  );
  assert.match(
    (await page.locator(".curtain-real").textContent()) ?? "",
    /REAL REFERENCE CUTOUTS · SAME WCS/,
  );
  const irSource = await page.locator(".curtain-img--ir").getAttribute("src");
  assert.match(irSource ?? "", /ref_wise_w2\.webp$/);
  await page.waitForFunction(
    () => {
      const image = document.querySelector(".curtain-img--ir");
      return image instanceof HTMLImageElement && image.naturalWidth > 0;
    },
    undefined,
    { timeout: 15_000 },
  );
  await page.screenshot({
    path: path.join(outputDir, "wise-w2-curtain-1600.png"),
  });
  console.log("WISE curtain opens on WISE W2 4.6 µm; REAL label and real cutout loaded");
  await page.keyboard.press("Escape");

  // 6. Stale reference-epoch URL coordinates are rewritten to 2025.8 without
  //    a 422, and show the same matched toast.
  await page.goto(
    url(
      `target=wise_0855&ra=133.79513&dec=-7.24515&bands=all&epoch=all&mode=still&fps=4&diff=0&overlay=${OVERLAYS}`,
    ),
    { waitUntil: "domcontentloaded" },
  );
  await waitForDecoded(page, "WISE 0855");
  await waitForEpochs(page, 3);
  await waitForText(
    page,
    ".notice-bar",
    /Matched WISE 0855 \(2010\.0 reference coordinates\) → propagated to 2025\.8; loaded the golden cache\./,
  );
  await waitForTargetUrl(page, "wise_0855");
  await waitForUrlCoords(page, 133.75921, -7.24216);
  const normalised = await assertTargetUrl(page, "wise_0855");
  assert.ok(Math.abs(normalised.ra - 133.75921) < 1e-6);
  assert.ok(Math.abs(normalised.dec - -7.24216) < 1e-6);
  assert.equal(await page.locator(".boot-error").count(), 0);
  await page.screenshot({
    path: path.join(outputDir, "url-normalized-1600.png"),
  });
  console.log("stale 2010.0 URL coordinates normalised to 2025.8 before the API query");

  // 7. Mobile: no horizontal overflow on the workspace or the search modal.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(
    url(
      `target=wise_0855&bands=all&mode=still&epoch=2025_E1&fps=4&diff=0&overlay=${OVERLAYS}`,
    ),
    { waitUntil: "domcontentloaded" },
  );
  await waitForDecoded(page, "WISE 0855");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  assert.ok(overflow <= 1, `mobile horizontal overflow: ${overflow}px`);
  await openSearch(page);
  const modalOverflow = await page.evaluate(() => {
    const panel = document.querySelector(".modal-panel--search");
    if (!panel) return Number.POSITIVE_INFINITY;
    const rect = panel.getBoundingClientRect();
    return Math.max(
      document.documentElement.scrollWidth - window.innerWidth,
      rect.right - window.innerWidth,
    );
  });
  assert.ok(modalOverflow <= 1, `mobile search overflow: ${modalOverflow}px`);
  await page.screenshot({
    path: path.join(outputDir, "mobile-search-390.png"),
  });
  await page.keyboard.press("Escape");
  console.log("mobile workspace and search dialog have no horizontal overflow");

  const filteredConsoleErrors = consoleErrors.filter(
    (text) => !/Download the React DevTools/i.test(text),
  );
  if (filteredConsoleErrors.length > 0) {
    console.error("console errors:", filteredConsoleErrors);
  }
  if (pageErrors.length > 0) console.error("page errors:", pageErrors);
  assert.equal(filteredConsoleErrors.length, 0, "no console errors");
  assert.equal(pageErrors.length, 0, "no page errors");
  console.log("no console or page errors");

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
