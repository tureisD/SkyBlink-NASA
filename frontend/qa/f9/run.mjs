/**
 * F9 Playwright QA — beginner Help dialog.
 *
 * Runs against the local final container (APP_URL, default
 * http://127.0.0.1:8000) with the F9 frontend dist mounted into the unchanged
 * `skyblink:final` image: real `/api/v1`, golden cache and reference overlays.
 * No routes are stubbed. Screenshots are written next to this file.
 *
 * Run:
 *   npx playwright install chromium   # once
 *   node qa/f9/run.mjs
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

async function waitForDecoded(page, name, timeout = 45_000) {
  await page.waitForSelector(".hud-name", { timeout });
  await page.waitForFunction(
    (expected) =>
      document.querySelector(".hud-name")?.textContent?.trim() === expected,
    name,
    { timeout },
  );
  await page.waitForSelector(".canvas-status", { timeout: 5_000 }).catch(() => undefined);
  await page.waitForFunction(
    () => !document.querySelector(".canvas-status"),
    undefined,
    { timeout },
  );
}

async function openHelp(page) {
  const button = page.locator(".topbar").getByRole("button", { name: "Help", exact: true });
  assert.equal(await button.count(), 1, "TopBar has exactly one ? Help button");
  assert.equal((await button.textContent())?.trim(), "?", "Help trigger is the ? glyph");
  await button.click();
  await page.waitForSelector("#help-title", { timeout: 5_000 });
}

async function main() {
  const browser = await chromium.launch();
  const consoleErrors = [];
  const pageErrors = [];

  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto(
    url(
      `target=wise_0855&bands=all&epoch=all&mode=still&fps=4&diff=0&overlay=${OVERLAYS}`,
    ),
    { waitUntil: "domcontentloaded" },
  );
  await waitForDecoded(page, "WISE 0855");
  await page.waitForFunction(
    () => document.querySelectorAll(".epoch-node").length > 1,
    undefined,
    { timeout: 45_000 },
  );
  console.log("WISE 0855 golden manifest loaded at 1600 × 1000");

  // ---------------------------------------------------------------------
  // 1. Help opens from ? and carries the beginner structure.
  // ---------------------------------------------------------------------
  await openHelp(page);

  assert.equal(
    (await page.locator("#help-title").textContent())?.trim(),
    "How to use SkyBlink",
    "plain-language title",
  );
  assert.equal(
    (await page.locator(".help-head .drawer-kicker").textContent())?.trim(),
    "Guide",
    "plain-language kicker",
  );

  for (const selector of [
    "#help-tour",
    "#help-screen",
    "#help-choose",
    "#help-viewer",
    "#help-display",
    "#help-spectrum",
    "#help-tools",
    "#help-watch",
    "#help-words",
    "#help-keys",
    "#help-data",
  ]) {
    await page.locator(selector).waitFor({ state: "visible", timeout: 5_000 });
  }

  const tourCards = page.locator(".help-tour .help-card");
  assert.equal(await tourCards.count(), 3, "quick tour has three numbered cards");
  assert.equal(await page.locator(".help-card-step").count(), 3, "cards are numbered");
  assert.match(await tourCards.nth(0).textContent(), /Pick a target/);
  assert.match(await tourCards.nth(1).textContent(), /Press play/);
  assert.match(await tourCards.nth(2).textContent(), /warnings[\s\S]*spectrum/);

  const figures = page.locator(".help-dialog .help-figure");
  assert.equal(await figures.count(), 1, "workflow diagram");
  const imageState = await page.locator(".help-dialog .help-figure img").evaluateAll((nodes) =>
    nodes.map((node) => ({
      src: node.getAttribute("src"),
      alt: node.getAttribute("alt"),
      complete: node.complete,
      naturalWidth: node.naturalWidth,
    })),
  );
  assert.deepEqual(
    imageState.map((entry) => entry.src),
    ["/help/how-it-works.svg"],
    "workflow diagram is embedded from /help",
  );
  for (const entry of imageState) {
    assert.ok(entry.alt && entry.alt.length > 40, `${entry.src} has useful alt text`);
    assert.ok(entry.complete && entry.naturalWidth > 0, `${entry.src} loads`);
  }
  const captions = (await page.locator(".help-figure figcaption").allTextContents()).join(" ");
  assert.match(captions, /Pick[\s\S]*blink[\s\S]*check[\s\S]*read/i);

  const icons = await page.locator(".help-dialog svg").count();
  assert.ok(icons >= 8, `expected inline SVG icons, found ${icons}`);
  assert.equal(
    await page.locator('.help-dialog svg:not([aria-hidden="true"])').count(),
    0,
    "all decorative icons are aria-hidden",
  );

  const glossaryTerms = page.locator(".help-glossary .help-term");
  assert.equal(await glossaryTerms.count(), 13, "glossary has the 13 requested terms");
  const glossaryText = (await page.locator(".help-glossary").textContent()) ?? "";
  for (const term of [
    "Target",
    "Epoch / survey pass",
    "Band",
    "Blink",
    "Difference",
    "Artifact / flag",
    "Spectrum",
    "Golden / saved data",
    "Telemetry / pixel data",
    "MJy/sr",
    "LVF",
    "RA / Dec",
    "FOV",
  ]) {
    assert.ok(glossaryText.includes(term), `glossary is missing ${term}`);
  }

  assert.equal(
    await page.locator(".help-shortcuts tr").count(),
    11,
    "compact shortcut table keeps all 11 rows",
  );

  const text = (await page.locator(".help-dialog").textContent()) ?? "";
  const lower = text.toLowerCase();
  for (const forbidden of [
    "operator manual",
    "discovery pipeline",
    "confidence score",
    "discovery probability",
    "publication-grade",
    "provenance",
    "telemetry sidecar",
    "no invented inference",
  ]) {
    assert.ok(!lower.includes(forbidden), `jargon phrase still present: ${forbidden}`);
  }
  assert.equal(
    (lower.match(/discovery tool/g) ?? []).length,
    1,
    "the 'not a discovery tool' idea is stated once",
  );
  assert.equal(
    (lower.match(/golden cache/g) ?? []).length,
    1,
    "the internal 'golden cache' name is mentioned once",
  );
  assert.match(text, /not an automatic discovery tool/);
  assert.match(text, /WISE 0855/);
  assert.match(text, /QR2/);
  assert.match(text, /2024_E1/);
  assert.match(text, /6\.15″/);
  assert.match(text, /Real observations only/);
  assert.match(text, /follow-up observations/);
  assert.match(text, /NASA\/IPAC IRSA/);
  assert.match(text, /SkyView DSS2/);
  assert.match(text, /Gaia DR3/);

  const shortcutRows = await page.locator(".help-shortcuts tr").evaluateAll((rows) =>
    rows.map((row) => row.textContent?.replace(/\s+/g, " ").trim() ?? ""),
  );
  for (const expected of ["Space", "Esc", "Double-click", "Thermal"]) {
    assert.ok(
      shortcutRows.some((row) => row.includes(expected)),
      `shortcut table is missing ${expected}`,
    );
  }

  const design = await page.evaluate(() => {
    const panel = document.querySelector(".modal-panel--help");
    const heading = document.querySelector(".help-heading");
    const card = document.querySelector(".help-card");
    return {
      viewportOverflow: document.documentElement.scrollWidth - window.innerWidth,
      dialogOverflow:
        (document.querySelector(".help-dialog")?.scrollWidth ?? 0) -
        (document.querySelector(".help-dialog")?.clientWidth ?? 0),
      panelScrollable: Boolean(panel && panel.scrollHeight > panel.clientHeight + 1),
      headingFamily: heading ? getComputedStyle(heading).fontFamily : "",
      cardBorder: card ? getComputedStyle(card).borderTopColor : "",
      defaultCheckboxes: document.querySelectorAll('.help-dialog input[type="checkbox"]').length,
    };
  });
  assert.ok(design.viewportOverflow <= 1, `desktop viewport overflow ${design.viewportOverflow}px`);
  assert.equal(design.dialogOverflow, 0, "desktop help has no horizontal overflow");
  assert.ok(design.panelScrollable, "desktop help modal scrolls");
  assert.match(design.headingFamily, /mono|Consolas|Menlo/i, "section headers use mono");
  assert.match(design.cardBorder, /0\.07/, "cards use the 7% hairline");
  assert.equal(design.defaultCheckboxes, 0, "no default browser checkboxes");

  await page.screenshot({ path: path.join(outputDir, "desktop-help-top.png") });
  console.log(`Help opens from ?: 3 tour cards, ${icons} icons, 13 glossary terms, 11 shortcuts`);

  // ---------------------------------------------------------------------
  // 2. The wide figures and glossary stay inside the modal.
  // ---------------------------------------------------------------------
  await page.evaluate(() => {
    const panel = document.querySelector(".modal-panel--help");
    const section = document.querySelector("#help-screen");
    if (!(panel instanceof HTMLElement) || !(section instanceof HTMLElement)) return;
    panel.scrollTop +=
      section.getBoundingClientRect().top - panel.getBoundingClientRect().top - 44;
  });
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(outputDir, "desktop-help-figure.png") });

  const figureBoxes = await page.locator(".help-figure img").evaluateAll((nodes) =>
    nodes.map((node) => {
      const rect = node.getBoundingClientRect();
      return { left: rect.left, right: rect.right, width: rect.width };
    }),
  );
  for (const box of figureBoxes) {
    assert.ok(box.width > 300, "figures span the body width");
    assert.ok(box.left >= 0, "figure starts inside the viewport");
    assert.ok(box.right <= 1600 + 1, "figure ends inside the viewport");
  }

  await page.locator("#help-words").scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(outputDir, "desktop-help-glossary.png") });
  console.log("Flow diagram, screen map and glossary fit the desktop modal");

  // Escape closes and restores focus to the ? trigger.
  await page.keyboard.press("Escape");
  await page.waitForSelector("#help-title", { state: "detached", timeout: 5_000 });
  await page.waitForFunction(
    () =>
      document.activeElement?.getAttribute("aria-label") === "Help" &&
      document.activeElement?.getAttribute("aria-haspopup") === "dialog",
    undefined,
    { timeout: 5_000 },
  );
  assert.equal(await page.getByRole("dialog").count(), 0, "no dialog remains after Escape");
  console.log("Escape closes Help and restores focus to the ? trigger");

  // ---------------------------------------------------------------------
  // 3. Mobile 390 × 844: single column, images scale, modal scrolls.
  // ---------------------------------------------------------------------
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForDecoded(page, "WISE 0855");
  const workspaceOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  assert.ok(workspaceOverflow <= 1, `mobile workspace overflow: ${workspaceOverflow}px`);

  await openHelp(page);
  await page.waitForFunction(
    () =>
      Array.from(document.querySelectorAll(".help-figure img")).every(
        (node) => node.complete && node.naturalWidth > 0,
      ),
    undefined,
    { timeout: 10_000 },
  );
  const mobile = await page.evaluate(() => {
    const panel = document.querySelector(".modal-panel--help");
    const dialog = document.querySelector(".help-dialog");
    if (!panel || !dialog) return null;
    const panelRect = panel.getBoundingClientRect();
    const cards = Array.from(document.querySelectorAll(".help-tour .help-card")).map((node) => {
      const rect = node.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom, width: rect.width };
    });
    const terms = Array.from(document.querySelectorAll(".help-glossary .help-term")).map(
      (node) => {
        const rect = node.getBoundingClientRect();
        return { top: rect.top, bottom: rect.bottom };
      },
    );
    const images = Array.from(document.querySelectorAll(".help-figure img")).map((node) => {
      const rect = node.getBoundingClientRect();
      return { left: rect.left, right: rect.right, width: rect.width, naturalWidth: node.naturalWidth };
    });
    return {
      viewportOverflow: document.documentElement.scrollWidth - window.innerWidth,
      panelOverflow: panelRect.right - window.innerWidth,
      panelScrollable: panel.scrollHeight > panel.clientHeight + 1,
      dialogOverflow: dialog.scrollWidth - dialog.clientWidth,
      columns: Array.from(document.querySelectorAll(".help-col")).map((element) => {
        const rect = element.getBoundingClientRect();
        return { top: rect.top, bottom: rect.bottom, width: rect.width };
      }),
      cards,
      terms,
      images,
    };
  });
  assert.ok(mobile, "mobile help panel is present");
  assert.ok(mobile.viewportOverflow <= 1, `mobile help viewport overflow: ${mobile.viewportOverflow}px`);
  assert.ok(mobile.panelOverflow <= 1, `mobile help panel overflow: ${mobile.panelOverflow}px`);
  assert.equal(mobile.dialogOverflow, 0, "help content has no horizontal overflow");
  assert.ok(mobile.panelScrollable, "help modal is vertically scrollable on mobile");
  assert.equal(mobile.columns.length, 2, "help has two body columns before stacking");
  assert.ok(
    mobile.columns[1].top >= mobile.columns[0].bottom - 1,
    "help body columns stack vertically on mobile",
  );
  assert.ok(
    mobile.cards[1].top >= mobile.cards[0].bottom - 1 &&
      mobile.cards[2].top >= mobile.cards[1].bottom - 1,
    "quick-tour cards stack to one column on mobile",
  );
  assert.ok(
    mobile.terms[1].top >= mobile.terms[0].bottom - 1,
    "glossary stacks to one column on mobile",
  );
  for (const image of mobile.images) {
    assert.ok(image.width > 0 && image.width <= 370 + 1, "mobile figure scales to the panel");
    assert.ok(image.left >= 0 && image.right <= 390 + 1, "mobile figure stays inside the viewport");
    assert.ok(image.naturalWidth > 0, "mobile figure image loads");
  }
  await page.screenshot({ path: path.join(outputDir, "mobile-help.png") });

  const scrolled = await page.evaluate(() => {
    const panel = document.querySelector(".modal-panel--help");
    if (!(panel instanceof HTMLElement)) return -1;
    panel.scrollTop = panel.scrollHeight;
    return panel.scrollTop;
  });
  assert.ok(scrolled > 0, "help modal scrolls to the bottom on mobile");
  await page.waitForTimeout(100);
  await page.screenshot({ path: path.join(outputDir, "mobile-help-scrolled.png") });
  console.log("mobile 390 × 844: Help stacks, figures scale, modal scrolls, no overflow");

  // ---------------------------------------------------------------------
  // 4. Clean console.
  // ---------------------------------------------------------------------
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
