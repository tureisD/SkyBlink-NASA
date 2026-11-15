# Renewed archive-search investigation

2026-11-15, approximately 17:42–17:45 UTC. **Live discovery has not been restored.** This follow-up tested whether the official SPHEREx Data Explorer had a working science-metadata route independent of the failing direct SIA/TAP calls. It found no usable replacement. No runtime acquisition source, scientific gate or default mode was changed during these probes; no known-exposure build was made or counted as live-search acceptance.

## Official interface and observed network

The [IRSA SPHEREx mission page](https://irsa.ipac.caltech.edu/Missions/spherex.html) links to the public [SPHEREx Data Explorer](https://irsa.ipac.caltech.edu/applications/spherex/). A fresh anonymous Chromium session loaded this application successfully. Opening its **Spectral Image Search** tab first displayed a spatial-search capability warning, then:

> TAP service does not appear to exist or is not accessible: https://irsa.ipac.caltech.edu/TAP

The browser's observed public endpoint `applications/spherex/CmdSrv/sync?cmd=getCapabilities` returned HTTP 200 with `{"success":false}` for the canonical TAP capabilities URL. This is an application-level failure despite the HTTP status.

Other interface resources worked: HiPS/MOC coverage assets and a server-side query of `TAP_SCHEMA.columns` for `spherex.obscore` returned data. The schema includes real discovery fields such as `obs_id`, `access_url`, `t_min`, `t_max`, `energy_bandpassname` and `s_region`. These successful configuration/coverage responses do not contain a selected field's observation inventory and do not establish science-query availability.

Evidence is retained under `backend/.cache/phase6/explorer-diagnosis/`: `network.json` records request URLs, public request payloads, status, body hashes and timestamps; `response-013.bin` contains the capability failure, `response-016.bin` the returned schema, and `gui-spatial-warning.png` the interface state. The browser used a fresh anonymous context; no credentials, nonpublic host or access bypass was used.

## One distinct public server-side spatial query

Because the interface could not expose a usable coordinate-search form, one explicitly authorized diagnostic reused its **observed public** `CmdSrv/sync?cmd=tableSearch` endpoint and `IpacTableFromSource` processor. The source remained the canonical public TAP service. This was a manually supplied standard ADQL query through an observed processor, not a successful click-through GUI search:

```sql
SELECT TOP 1 obs_id, access_url, t_min, t_max, energy_bandpassname, s_region
FROM spherex.obscore
WHERE 1 = INTERSECTS(
  CIRCLE('ICRS', 192.85948, 27.12825, 0.01), s_region
)
```

The arbitrary north Galactic pole position was independent of the five catalog targets and known-exposure index. The request had a 30-second caller limit and no retry. It completed in **1.089 seconds**, returning HTTP 200 with a **107-byte error payload**, `success="false"`, whose cause was an upstream **502 Bad Gateway**. It returned **no science rows**. HTTP 200 here must not be interpreted as discovery success.

Exact query, endpoint, response body and SHA-256 are retained in `obscore-spatial-proxy.json` and `obscore-spatial-proxy.body`; body hash is `80f2c0e8ec10faf952636e505162c294e63664f89ed657632d26ebd3ef8abcb0`.

## Independent direct-query comparison

The backend agent's distinct direct `SELECT TOP 1 * FROM spherex.obscore` query returned HTTP **502** in **1.016 seconds**, with a 341-byte error body. Its renewed asynchronous transport, multipart synchronous transport and prior-job checks also failed rather than yielding observation rows. Receipts are retained under `backend/.cache/phase6/discovery-renewed/`; `obscore-minimal.json` records the direct ObsCore comparison.

These observations narrow the problem beyond SkyBlink's artifact/plane join: even a minimal ObsCore query and the public Explorer's server-side metadata path fail. They do not prove permanent or globally universal downtime, identify the internal failing service, or imply that all IRSA endpoints are unavailable. The earlier successful schema query, current coverage resources and fresh file-download controls remain distinct evidence.

## Outcome and boundary

The [official cloud-access guide](https://irsa.ipac.caltech.edu/cloud_access/)
identifies the public `nasa-irsa-spherex` bucket. Anonymous root and DR1-prefix
listings returned HTTP 200; the DR1 listing took 0.797 seconds. The inspected
levels exposed release, image, cube and calibration directories, with no
independent coordinate-search index. This was not a recursive scan of every
object and does not prove an index could never be provided. Download storage
availability alone does not supply current observation footprints and times.
Receipts are `discovery-renewed/cloud-root.json`, `cloud-prefixes.json` and
`cloud-prefixes.xml` under the local Phase 6 cache.

No route tested in this renewal produced current spatial science metadata, so there is no evidenced live-discovery implementation to adopt. A metadata schema, cached coverage map, historical exposure list, or downloaded FITS file is not a current arbitrary-coordinate observation inventory. Explicit known mode remains a bounded catalog workaround; saved mode remains historical. Neither is relabeled as restored default archive search.

The diagnostic browser was closed and network probes stopped after the distinct public route failed. User application servers and the method-13 acquisition implementation were untouched. See [the preceding diagnosis](phase6-live-discovery-diagnosis.md) for independent SIA transports, bounded TAP timing, the scheduling repair, and its separately verified known-mode result.
