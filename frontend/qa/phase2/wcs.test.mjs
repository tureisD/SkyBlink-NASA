/** Compare the actual TypeScript helpers with independent Astropy/WCSLIB output. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const repo = path.resolve(root, "..");
const pythonCandidates = process.platform === "win32"
  ? [path.join(repo, ".venv311/Scripts/python.exe"), path.join(repo, ".venv/Scripts/python.exe")]
  : [path.join(repo, ".venv311/bin/python"), path.join(repo, ".venv/bin/python")];
const python = process.env.SKYBLINK_PYTHON ?? pythonCandidates.find((p) => fs.existsSync(p)) ?? "python";
const reference = spawnSync(python, [path.join(here, "wcs-reference.py")], {
  encoding: "utf8", maxBuffer: 2 * 1024 * 1024,
});
assert.equal(reference.status, 0, `Astropy reference failed (${python}): ${reference.stderr || reference.error}`);
const vectors = JSON.parse(reference.stdout);
const source = fs.readFileSync(path.join(root, "src/lib/wcs.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
});
const { worldToPixel, pixelToWorld, angularSeparationArcsec } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);
let maximumPixelError = 0;
let maximumAngularError = 0;
let count = 0;
for (const { wcs, points } of vectors) {
  for (const expected of points) {
    const world = pixelToWorld(wcs, expected.x, expected.y);
    assert.ok(world.ra >= 0 && world.ra < 360 && world.dec >= -90 && world.dec <= 90);
    // RA at an exact celestial pole is undefined; spherical separation is
    // the meaningful comparison there, as elsewhere on the sphere.
    const angularError = angularSeparationArcsec(world, expected);
    maximumAngularError = Math.max(maximumAngularError, angularError);
    assert.ok(angularError < 0.0001, `Inverse TAN error ${angularError} arcsec at ${JSON.stringify({ wcs, expected, world })}`);
    const pixel = worldToPixel(wcs, expected.ra, expected.dec);
    const pixelError = Math.hypot(pixel.x - expected.x, pixel.y - expected.y);
    maximumPixelError = Math.max(maximumPixelError, pixelError);
    assert.ok(pixelError < 0.0001, `Forward TAN error ${pixelError} pixels at ${JSON.stringify({ wcs, expected, pixel })}`);
    const roundtrip = worldToPixel(wcs, world.ra, world.dec);
    assert.ok(Math.hypot(roundtrip.x - expected.x, roundtrip.y - expected.y) < 0.0001);
    count++;
  }
}
const equator = vectors[0].wcs;
for (const [ra, dec] of [[90, 0], [180, 0], [270, 0], [0, 91], [NaN, 0]]) {
  const pixel = worldToPixel(equator, ra, dec);
  assert.ok(Number.isNaN(pixel.x) && Number.isNaN(pixel.y), "Unprojectable world coordinates must be skipped");
}
for (const [x, y] of [[NaN, 120], [120, Infinity]]) {
  const world = pixelToWorld(equator, x, y);
  assert.ok(Number.isNaN(world.ra) && Number.isNaN(world.dec));
}
assert.ok(Number.isNaN(pixelToWorld({ ...equator, cdelt1: 0 }, 120, 120).ra));
assert.ok(worldToPixel(equator, 0.01, 0).x < 120, "East lies left");
assert.ok(worldToPixel(equator, 0, 0.01).y < 120, "North lies up");
console.log(`TAN matches Astropy for ${count} points across ${vectors.length} fields, including both poles and RA zero. Maximum errors: ${maximumPixelError} px / ${maximumAngularError} arcsec.`);
