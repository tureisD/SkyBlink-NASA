/**
 * F8 Playwright QA — rail relocation and the single `?` help surface.
 *
 * Runs against the local final container (APP_URL, default
 * http://127.0.0.1:8000) with the F8 frontend dist mounted into the unchanged
 * F7 backend image: real `/api/v1`, golden cache and reference overlays. No
 * routes are stubbed. Screenshots are written next to this file.
 *
 * Run:
 *   npx playwright install chromium   # once
 *   node qa/f8/run.mjs
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

async function waitForHelpHeading(page, name) {
  await page
    .locator(".help-dialog")
    .getByRole("heading", { name, exact: true })
    .waitFor({ state: "visible", timeout: 10_000 });
}

async function main() {
  const browser = await chromium.launch();
  const consoleErrors = [];
  const pageErrors = [];

  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1,
    permissions: ["clipboard-read", "clipboard-write"],
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
  // 1. Search lives in the left target header; the TopBar stays uncluttered.
  // ---------------------------------------------------------------------
  const topbarActions = await page
    .locator(".topbar")
    .getByRole("button", { name: /search|triage|copy/i })
    .count();
  assert.equal(topbarActions, 0, "TopBar must not contain Search/Triage/Copy");

  const topbarHelp = page.locator(".topbar").getByRole("button", { name: "Help", exact: true });
  assert.equal(await topbarHelp.count(), 1, "TopBar has exactly one Help button");

  const leftSearch = page
    .locator(".rail--left .rail-head")
    .getByRole("button", { name: "Search coordinates" });
  assert.equal(await leftSearch.count(), 1, "left rail target header has Search coordinates");
  await leftSearch.click();
  await page.waitForSelector("#search-ra");
  assert.equal(
    (await page.locator("#search-title").textContent())?.trim(),
    "Search coordinates",
  );
  console.log("Search coordinates is in the left target header and opens the resolver");
  await page.keyboard.press("Escape");
  await page.waitForSelector(".modal-panel--search", { state: "detached" });

  // ---------------------------------------------------------------------
  // 2. Triage card and Copy link live at the bottom of the right rail.
  // ---------------------------------------------------------------------
  const rightActions = page.locator(".rail--right .display-actions");
  assert.equal(await rightActions.count(), 1, "right rail has one action block");
  assert.match(
    (await rightActions.textContent()) ?? "",
    /Share & export[\s\S]*Triage card[\s\S]*Copy link/,
  );
  assert.equal(
    await rightActions.getByRole("button", { name: "Triage card", exact: true }).count(),
    1,
  );
  assert.equal(
    await rightActions.getByRole("button", { name: "Copy link", exact: true }).count(),
    1,
  );
  const lastRailHeading = await page
    .locator(".rail--right .control-section")
    .last()
    .locator(".control-name")
    .textContent();
  assert.equal(
    lastRailHeading?.trim(),
    "Share & export",
    "the action block is the last right-rail section",
  );
  console.log("Triage card and Copy link are in the right-rail bottom action block");
  await page.screenshot({ path: path.join(outputDir, "layout-1600.png") });

  // Triage export still builds the dynamic-channel card.
  await rightActions.getByRole("button", { name: "Triage card", exact: true }).click();
  await page.waitForSelector("#triage-title", { timeout: 10_000 });
  await page.waitForFunction(
    () => {
      const card = document.querySelector(".triage[data-channel-count]");
      const count = Number(card?.getAttribute("data-channel-count") ?? "");
      return Number.isFinite(count) && count > 0 && Boolean(document.querySelector(".triage-preview img"));
    },
    undefined,
    { timeout: 45_000 },
  );
  const channelCount = await page
    .locator(".triage[data-channel-count]")
    .getAttribute("data-channel-count");
  assert.ok(Number(channelCount) > 0, "triage card reports a positive channel count");
  console.log(`Triage card opens and reports ${channelCount} channels`);
  await page.keyboard.press("Escape");
  await page.waitForSelector(".modal-panel--triage", { state: "detached" });

  // Copy link still writes a reproducible URL and flips to COPIED.
  const copyButton = page
    .locator(".rail--right .display-actions")
    .getByRole("button", { name: "Copy link", exact: true });
  await copyButton.click();
  await page.waitForFunction(
    () =>
      document
        .querySelector(".rail--right .display-actions")
        ?.textContent?.includes("COPIED"),
    undefined,
    { timeout: 5_000 },
  );
  const copiedUrl = await page.evaluate(() => navigator.clipboard.readText());
  const copied = new URL(copiedUrl);
  assert.equal(copied.searchParams.get("target"), "wise_0855");
  assert.equal(copied.searchParams.get("bands"), "all");
  assert.equal(copied.searchParams.get("mode"), "still");
  console.log("Copy link writes the reproducible view URL and shows COPIED");

  // ---------------------------------------------------------------------
  // 3. One `?` help surface: content, Escape and focus restoration.
  // ---------------------------------------------------------------------
  await topbarHelp.click();
  await page.waitForSelector("#help-title", { timeout: 5_000 });

  const expectedSections = [
    "What this is",
    "Quick start",
    "Coordinate search",
    "Left rail",
    "Canvas & overlays",
    "Bottom deck",
    "Right rail & display",
    "Panels & actions",
    "What to look out for",
    "Keyboard shortcuts",
    "Data & credits",
  ];
  for (const section of expectedSections) {
    await waitForHelpHeading(page, section);
  }

  const helpText = (await page.locator(".help-dialog").textContent()) ?? "";
  const requiredFragments = [
    "LIVE QUICK-LOOK",
    "5′",
    "6.15″",
    "MJy/sr",
    "Table 16",
    "B1",
    "Thermal",
    "difference pair",
    "dense per-detector channels",
    "W2 4.6 µm",
    "dynamic",
    "QR2-only",
    "2024_E1",
    "Real observations only",
    "No invented inference",
    "Double-click",
  ];
  for (const fragment of requiredFragments) {
    assert.ok(
      helpText.includes(fragment),
      `help dialog is missing required fragment: ${fragment}`,
    );
  }
  const shortcutRows = await page.locator(".help-shortcuts tr").count();
  assert.ok(shortcutRows >= 10, `expected a full shortcut table, got ${shortcutRows} rows`);
  console.log(
    `Help dialog covers ${expectedSections.length} sections, ${shortcutRows} shortcut rows and the required limitations`,
  );
  await page.screenshot({ path: path.join(outputDir, "help-1600.png") });

  // Escape closes and restores focus to the `?` trigger.
  await page.keyboard.press("Escape");
  await page.waitForSelector("#help-title", { state: "detached", timeout: 5_000 });
  await page.waitForFunction(
    () =>
      document.activeElement?.getAttribute("aria-label") === "Help" &&
      document.activeElement?.getAttribute("aria-haspopup") === "dialog",
    undefined,
    { timeout: 5_000 },
  );
  assert.equal(
    await page.getByRole("dialog").count(),
    0,
    "no dialog remains after Escape",
  );
  console.log("Escape closes Help and restores focus to the ? trigger");

  // ---------------------------------------------------------------------
  // 4. Mobile 390 × 844: the Help modal scrolls, no horizontal overflow.
  // ---------------------------------------------------------------------
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForDecoded(page, "WISE 0855");
  const mobileOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  assert.ok(mobileOverflow <= 1, `mobile workspace overflow: ${mobileOverflow}px`);

  await page.locator(".topbar").getByRole("button", { name: "Help" }).click();
  await page.waitForSelector("#help-title");
  const mobileHelp = await page.evaluate(() => {
    const panel = document.querySelector(".modal-panel--help");
    const dialog = document.querySelector(".help-dialog");
    if (!panel || !dialog) return null;
    const panelRect = panel.getBoundingClientRect();
    const columns = Array.from(document.querySelectorAll(".help-col")).map((element) => {
      const rect = element.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom, width: rect.width };
    });
    return {
      viewportOverflow: document.documentElement.scrollWidth - window.innerWidth,
      panelOverflow: panelRect.right - window.innerWidth,
      panelScrollable: panel.scrollHeight > panel.clientHeight + 1,
      dialogOverflow: dialog.scrollWidth - dialog.clientWidth,
      columns,
    };
  });
  assert.ok(mobileHelp, "mobile help panel is present");
  assert.ok(
    mobileHelp.viewportOverflow <= 1,
    `mobile help viewport overflow: ${mobileHelp.viewportOverflow}px`,
  );
  assert.ok(
    mobileHelp.panelOverflow <= 1,
    `mobile help panel overflow: ${mobileHelp.panelOverflow}px`,
  );
  assert.equal(mobileHelp.dialogOverflow, 0, "help content has no horizontal overflow");
  assert.ok(mobileHelp.panelScrollable, "help modal is vertically scrollable on mobile");
  assert.equal(mobileHelp.columns.length, 2, "help has two content columns before stacking");
  assert.ok(
    mobileHelp.columns[1].top >= mobileHelp.columns[0].bottom - 1,
    "help columns stack vertically on mobile",
  );
  await page.screenshot({ path: path.join(outputDir, "mobile-help-390.png") });

  const scrolled = await page.evaluate(() => {
    const panel = document.querySelector(".modal-panel--help");
    if (!(panel instanceof HTMLElement)) return -1;
    panel.scrollTop = panel.scrollHeight;
    return panel.scrollTop;
  });
  assert.ok(scrolled > 0, "help modal scrolls to the data footnote");
  await page.waitForTimeout(100);
  await page.screenshot({
    path: path.join(outputDir, "mobile-help-scrolled-390.png"),
  });
  console.log("mobile 390 × 844: Help stacks to one column, scrolls, no horizontal overflow");

  // ---------------------------------------------------------------------
  // 5. Clean console.
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
