/** Retired: this historical runner depended on removed synthetic observations.
 * Run npm run test:real-data for policy checks, or node qa/f7/run.mjs
 * against the actual application for real-observation browser smoke tests.
 */
console.error("This historical synthetic-data QA runner is retired. Use npm run test:real-data and node qa/f7/run.mjs.");
process.exitCode = 1;
