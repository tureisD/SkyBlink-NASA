/** Build gate: only reviewed UI artwork can be bundled as static data. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const approvedPublicFiles = new Set([
  "favicon.svg",
  "help/how-it-works.svg",
  // Reviewed annotated screenshots: help illustrations, never observation inputs.
  "help/guide-workspace.png",
  "help/guide-compare.png",
  "help/guide-spectrum.png",
]);

function files(directory) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(directory, entry.name);
    assert.ok(!entry.isSymbolicLink(), `Static data must not be a symlink: ${full}`);
    return entry.isDirectory() ? files(full) : [full];
  });
}

for (const filename of files(path.join(root, "public"))) {
  const relative = path.relative(path.join(root, "public"), filename).replaceAll("\\", "/");
  assert.ok(approvedPublicFiles.has(relative), `Unreviewed public asset: ${relative}`);
}
for (const filename of files(path.join(root, "src"))) {
  assert.ok(!/\.(json|fits|webp|png|bin|gz)$/i.test(filename), `Bundled observation/model data is forbidden: ${filename}`);
}
if (process.argv.includes("--dist")) {
  const dist = path.join(root, "dist");
  assert.ok(fs.existsSync(path.join(dist, "index.html")), "Build output is missing");
  for (const filename of files(dist)) {
    const relative = path.relative(dist, filename).replaceAll("\\", "/");
    assert.ok(
      relative === "index.html" || approvedPublicFiles.has(relative) || /^assets\/[^/]+\.(js|css)$/.test(relative),
      `Unreviewed built asset: ${relative}`,
    );
    if (filename.endsWith(".js")) {
      const text = fs.readFileSync(filename, "utf8");
      assert.ok(!/Planck blackbody|T1_like|T6_like|forward_sum|\/mock\/manifest\.json/.test(text), `Removed data found in bundle: ${relative}`);
    }
  }
}
console.log("Frontend real-data packaging gate passed.");
