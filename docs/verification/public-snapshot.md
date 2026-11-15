# Public source snapshot — 15 November 2026

## Current synchronization

The public repository now includes the observatory styling, illustrated Help,
rewritten README and video guide, annotated screenshots and their verification.
`SkyBlink-NASA` is the default Git remote for publication. The branch retains
one snapshot commit, with no imported development history.

The original public-release settings below are preserved: exact-byte Git
attributes, corrected environment defaults, the redacted personal path and
exclusion of the research PDF whose redistribution provenance is unresolved.
The current application build and real-only packaging checks pass. The latest
local checks include 321 backend tests and the illustrated Help browser checks;
the separate-export results below retain their original scope.

## Original export record

This repository is the public **SkyBlink NASA** source snapshot at
<https://github.com/tureisD/SkyBlink-NASA>. It starts with one initial commit;
the development repository and its Git history were not imported or modified.
Historical reports and their recorded commit identifiers remain as evidence of
prior work, not as commits in this repository.

The export includes the current application, tests, scripts, documentation,
MIT software license, bounded known-exposure index and five explicit saved
real-data examples. The 288 approved observation files retain their exact bytes.
The license does not replace upstream astronomical-data and imagery terms;
retain the source attribution in the manifests and documentation.

Local environments, dependencies, build output, private environment settings,
IDE files, ignored acquisition caches and Git metadata were excluded. The root
research PDF was excluded because its redistribution provenance was unresolved.
Historical screenshots retain their original evidence limitations; use the
[verified presentation examples](../video.md) for the current demonstration.

The export preserves recorded evidence rather than rewriting past results.
References to the former private repository, historical local paths and hashes
in dated reports are historical. A private personal Desktop path in the old
verification narrative was redacted; raw scientific records were not changed.
Source files and data are preserved without Git line-ending conversion so
recorded byte hashes remain portable.

A source checkout does not contain ignored original FITS files or the local
live-analysis cache. Reproduction that needs those inputs requires the
recorded upstream files or an independently retained analysis bundle. Consult
[reproducibility](../guides/reproducibility.md) before clearing live storage.
Publishing the source does not deploy a website, establish archive availability,
validate an astrophysical discovery, or complete the event submission.

## Checks on the separate export

- Backend regression: 302 passed, 19 skipped (retained research inputs absent).
  Used the existing Python 3.11 dependency environment; this was not a fresh
  Python installation or a Linux/container run.
- Frontend: fresh `npm ci`, production build and all four regression commands
  passed. The WCS test used `SKYBLINK_PYTHON` to select the installed Astropy
  environment. Two optional share/export checks reported unavailable retained
  archive receipts; the other assertions passed.
- All five saved datasets passed `build_golden_cache.py --target all --verify-only`.
- The real-data packaging gate, including built frontend, and local Markdown
  destination check passed. Approved runtime observation hashes are unchanged.
- Credential-pattern review found no credentials; the test-only
  `user:password` URL is an intentional rejection case.

The public-source checks do not establish current archive availability,
container operation, hosted-app availability or scientific detection validity.
