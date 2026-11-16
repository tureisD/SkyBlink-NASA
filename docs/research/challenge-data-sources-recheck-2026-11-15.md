# Challenge-provided data sources: renewed check

Reviewed 2026-11-15 after the archive recovery investigation. **There are other
usable data routes, but no verified drop-in replacement for current arbitrary-
coordinate SPHEREx temporal discovery.** MOST did return current SPHEREx
metadata for a solar-system trajectory, revising the earlier broad failure
assessment. Two further options deserve more attention
than the earlier source review gave them: directly addressed all-sky cube tiles
and the static 3I/ATLAS observation list. WISE also provides an independently
working image service suitable for separately labeled context.

## What was rechecked

The [November 13 resource inventory](../reference/resource-release-2026-11-13.md)
records eight challenge links: IRSA SPHEREx, its tutorial notebooks, WiseView,
Gaia at MAST, the CSA NEOSSat mission, CADC, the CSA NEOSSat tutorial and the
NEOSSat dataset. I revisited those providers and followed their relevant data
links. The live challenge page could not be independently retrieved: the web
tool reported a failure and local Python/curl failed certificate verification.
Certificate checking was retained. Therefore this report does not certify that
the challenge has added no resources since the recorded November 13 inventory.

The [IRSA mission page](https://irsa.ipac.caltech.edu/Missions/spherex.html)
currently exposes DR1/quick releases, AWS access, SPLICES, Comet 3I/ATLAS, MOST
and several processing tools. These are reached through the challenge's IRSA
resource; they are not eight separate challenge-listed data archives.

## Same-mission routes

| Source | What the new check established | Suitability |
|---|---|---|
| Official AWS DR1/QR3 spectral images | Earlier execution in this session retrieved real IMAGE headers and completed a sample-period listing independently of TAP/SIA. | Best route to preserve the current image method; arbitrary coordinates still need a complete maintained exposure index. |
| DR1 all-sky cube | The tutorial computes a HEALPix tile URL directly from coordinates. The exact sample tile served a 5,760-byte FITS range with HTTP 206 in 1.500 s; full object length is 320,909,760 bytes. | Enables a distinct spectral-map/context feature without discovery. A header range is not full-cube or photometric validation. The spectral axis is not a temporal sequence. |
| Static 3I/ATLAS products | Downloaded the official table: 259 rows with predicted comet positions, observation times and detector IDs. All rows identify QR2. Download script was accessible; one direct image URL served a FITS range with 206 in 3.015 s. | A target-specific historical SPHEREx example is possible. Not current DR1/QR3 discovery, a catalog-target fix, or complete arbitrary-sky coverage. |
| MOST | The 3I/ATLAS name lookup failed, but a numeric Neptune query for June 2025 returned **66 SPHEREx rows in 3.031 s**, including DR1 paths, exposure times and footprints. An August one-day query returned a valid empty table. | **Working alternate metadata route for solar-system trajectories.** Not a generic fixed-coordinate replacement for the five catalog targets. |
| Source Discovery Tool | Its notebook explicitly calls `Irsa.query_sia` before downloading the selected images from S3. | Cloud download does not make its initial discovery independent. |
| Mosaic, spectrophotometry and cutout tools | Official processing tools are present. No successful independent inventory route was demonstrated through them. | Do not infer service independence from a separate interface; cutouts require an identified image. |
| SPLICES | A downloadable source catalog, including a bulk FITS link, is documented. | Target positions/properties, not an exposure-footprint/time inventory or a blink-image source. |

Sources: [cloud access](https://irsa.ipac.caltech.edu/cloud_access/),
[cube tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-hipscube/),
[cube product semantics](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/),
[3I/ATLAS resource](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/index.html),
[MOST API](https://irsa.ipac.caltech.edu/applications/MOST/MOSTProgramInterface.html),
[source-discovery notebook](https://caltech-ipac.github.io/irsa-tutorials/spherex-source-discovery-tool-demo/),
[SPLICES](https://irsa.ipac.caltech.edu/data/SPHEREx/SPLICES/).

### Important details in the two overlooked SPHEREx options

**Cube:** its 102 layers are wavelength channels, with 12.9-arcsecond pixels;
channels 51/52 are blank according to the product guide. The cube is already
ZODI-subtracted, unlike native Level 2 images. It must have a separate reader
and source label: sending it through the existing subtraction/epoch pipeline
would change its meaning. The documented tile lookup avoids the missing
exposure index, which is why it can help with coordinate-based exploration now.

**Comet:** the static table's `access_url` values are DataLink URLs, not direct
FITS URLs. The first tested DataLink returned HTTP 200 and `QUERY_STATUS=OK`,
but an empty TABLEDATA: it did not resolve an image. The separate official curl
script contains direct QR2 FITS URLs; the first such URL was reachable. The
script was inspected, not executed as a bulk download. Thus the static table
and direct script together are more useful than relying on DataLink alone.
The comet is extended and the provider discourages its point-source photometry
tool for this object. No comparison or comet measurement was produced here.

These findings narrow an earlier overly broad assumption: useful static
SPHEREx inventories do exist for at least this special target. That does not
establish a published full-archive metadata index.

## Other missions explicitly represented by challenge resources

| Resource family | Recheck and actual availability | How SkyBlink could use it |
|---|---|---|
| WiseView → unWISE | WiseView itself failed to load from this environment. Its maintainer repository links unWISE; that site's documented cutout endpoint returned a complete 77,197-byte archive in 2.156 s. Both included W1/W2 FITS files opened with 100×100 dimensions. | Strongest measured independent image alternative for WISE context. This test used the documented `neo1` cumulative coadd example; it does **not** validate time-resolved blink retrieval. A WISE temporal mode would need its own epoch adapter and tests. |
| Gaia / MAST → ESA archive | MAST mission/documentation page was accessible and describes positions, parallaxes, motions and photometry. No new Gaia catalog query or download was verified. | Independent astrometric reference/cross-match source, not a replacement SPHEREx image series. |
| NEOSSat / CADC / CSA dataset / tutorial | CADC's NEOSSat page and CSA's tutorial were accessible and document real FITS downloads and processing levels. The CSA dataset portal timed out in the web tool and failed local certificate verification. No NEOSSat image download or target coverage was verified. | Real independent mission imagery, potentially a separate moving-object example. Requires its own calibration, coverage and provenance handling. |

Sources: [WiseView maintainer repository](https://github.com/backyardworlds/wiseview),
[unWISE data access](https://unwise.me/imgsearch/),
[Gaia at MAST](https://archive.stsci.edu/missions-and-data/gaia),
[NEOSSat at CADC](https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/neossat/),
[CSA tutorial](https://github.com/asc-csa/NEOSSAT_Tutorial),
[CSA mission](https://www.asc-csa.gc.ca/eng/satellites/neossat/).
The four CSA links are entry points/documentation for a related archive family,
not four independent SPHEREx mirrors.

## Recommended scope

1. To retain current catalog/arbitrary-coordinate SPHEREx temporal comparisons:
   continue the AWS metadata-index track and IRSA recovery. **Add MOST to the
   support diagnosis:** current science metadata can execute through this
   documented service, so a blanket claim that all metadata backends are down
   is no longer justified. Its observed successful query does not prove the
   architecture or root cause of the failing TAP/SIA path.
2. To provide useful coordinate-based SPHEREx viewing during the outage:
   investigate a separately labeled all-sky spectral-cube view. Direct tile
   addressing is demonstrated; full-cube extraction, uncertainty/flag handling
   and delivery size remain to be tested.
3. For independent comparison imagery: prioritize unWISE, whose real cutout
   route was measured working. Preserve WISE identity and coadd date scope;
   never pass those frames off as another SPHEREx epoch.
4. For a curated moving-object story: assess the official 3I/ATLAS list, with
   explicit legacy QR2 provenance and moving/extended-source handling. Do not
   silently reintroduce QR2 into the current default acquisition policy.
   A MOST-driven solar-system mode could instead discover current-release
   exposures; retain actual trajectories, partial search scope and the existing
   image-quality gates. Do not invent orbital elements to impersonate a fixed
   target or equate 66 inventory rows with a validated temporal pair.

No runtime source or scientific threshold changed. These are candidate routes,
not newly integrated features or end-to-end acceptance. Direct file/header
availability is reported separately from complete downloads and interpretation.

## Receipts

New bodies, exact URLs and hashes are retained in
[`challenge-sources-20261115`](../evidence/phase6/challenge-sources-20261115/).
`comet-table.json` records the static inventory and columns; `comet-datalink.body`
retains the empty resolution result; `comet-file-header.json`, `cube-header.json`
and `unwise-cutout.json` record the actual file probes. Downloaded examples are
research evidence only and are not runtime observation inputs or fallback assets.
`most-neptune-june.json` and its body retain the working discovery query and
66 rows; earlier name-lookup failure and zero-row controls remain alongside it.
The first returned DR1 file served a 5,760-byte FITS range with HTTP 206 in
1.735 s (`most-dr1-file.json`). This confirms one returned path is reachable;
it does not validate a full image, matching pair or planetary measurement.
