# Machine-readable evidence

[Documentation home](../README.md) · [Readable verification reports](../verification/README.md)

- [phase1/](phase1/): real-data inventory and approval metadata.
- [phase2/](phase2/): discovery and spectral-signature checks.
- [phase3/](phase3/): astrometry, calibration and scientific checks.
- [phase4/](phase4/): protocols, control locks, discovery/replay results and [record snapshots](phase4/records/).
- [phase5/](phase5/): live-comparison results.

Scientific JSON and screenshot bytes were preserved during the documentation
reorganization. The real-data inventory is mutable policy metadata; its approved
observation hashes are unchanged. Old file paths inside sealed evidence remain
historical identifiers, with current locations recorded in
[the relocation map](../reference/file-locations.json).

Large FITS inputs and recent diagnostic receipts live in ignored local cache
directories named by the reports. Their presence in a report does not mean those
bytes ship with the repository. Follow the [replay guide](../guides/reproducibility.md)
for acquisition, integrity checks and input-retention requirements.
