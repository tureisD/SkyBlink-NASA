# Event compliance — Berlin Local Event exception

**Date recorded:** 2026-11-09
**Source:** Written confirmation from the Berlin Local Event organizing team, dated Berlin, 09.11.2026.

## Confirmation

The Berlin Local Event organizing team explicitly permits registered participants to begin project work before 14 November 2026. The permission covers team formation, challenge selection, research, data analysis, concept and architecture, repository/tooling setup, design, programming, and presentation preparation. There is no requirement that work be created only during the event weekend, and early work does not create a disadvantage.

## Conditions

- In-person attendance on both event days (14–15 November 2026).
- Timely submission through the official NASA Space Apps platform.
- The Code of Conduct applies.
- A signed copy can be requested from the Berlin organizing team; keep the confirmation with the submission materials.

## Project decision

The team is registered with the Berlin Local Event and is relying on this written confirmation to start O1/B1/F1/S1 before the global event weekend. The public NASA FAQ's general "no pre-work" statement still exists; the local written confirmation is the basis for this exception. Do not publish personal data from the letter; this page is a summary, not the letter itself.

## Final status (2026-11-09; counts updated 2026-11-14; submission rules rechecked 2026-11-13)

The exception was relied upon and the project is code/data complete: contract **1.2.0**, golden **revision 3 (DR1+QR3)**, **83 tests**, five-target card 5/5, and `skyblink:final` smoke-tested. Normal operation uses real data only. Attendance on both event days and timely submission remain the outstanding conditions. See `README.md`, `STATUS.md`, and `TASKS.md`.

## Submission rules confirmed by the 2026 FAQ (2026-11-13)

- Project pages open **2026-11-14 09:00 local time**; submission closes **2026-11-15 23:59 local time**.
- Submit through the team's project page on `spaceappschallenge.org`.
- Teams may have **1–6 members**, all registered for the same Local Event (or the Universal Event).
- Each submission must describe how **SI (Super Intelligence)** tools were used.
- The **Project Submission Guide** and **Judging & Awards Guide** were announced for November 13; the guide files were not publicly retrievable at the time of this check. Recheck the Resources page before filling the form.
- An open-source license, public repository, public demo URL, and demo video are expected in the submission; confirm the exact 2026 requirements in the guide. The repository currently exists at <https://github.com/tureisD/SkyBlink> but is **private**; make it public or grant judge access before judging if required.

The project still has **no public URL**. That remains the P0 submission risk; see `docs/guides/deployment.md`.

## What may start now

- O1: Pydantic contract models, `backend/models/version.py`, `backend/openapi.json`, explicit development-fixture manifests/frames.
- B1/F1/S1: implementation work, tests, golden cache, Docker/README.
- The H+12/H+24/H+32/H+38 checkpoints and H+42 freeze still apply to the event weekend.
