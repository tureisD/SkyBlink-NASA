# IRSA support incident — prepared, not sent

Subject: SPHEREx SIA and TAP discovery return 502 Proxy Error; static pages and AWS files accessible

**Latest controls (22:48-22:54 UTC):** availability returned 200/true, but
minimal plane and WISE SIA calls timed out. POST /TAP/async returned the same
341-byte 502 before creating a job. Direct plane/artifact lookups by MOST's
exact plane ID `01A0D2DE-63D3-7A96-868D-ACBFF3652C21` each timed out after about
60 seconds, with no spatial predicate or join. MOST again returned 66 rows in
1.891 seconds. New receipts are under
[`archive-continuation-20261115`](../evidence/phase6/archive-continuation-20261115/).
No new async job ID was issued. These controls strengthen the distinction
between TAP/SIA failure and working MOST/storage paths.

**Follow-up finding:** the documented MOST service returned 66 SPHEREx rows
for Neptune (NAIF ID 899), 2025-06-01 through 2025-06-30, in 3.031 seconds.
The response includes DR1 file paths, times and footprints, and a returned file
served a FITS header range. Please investigate whether this successful route
helps isolate the failing TAP/SIA service path. Exact query and response:
[`most-neptune-june.json`](../evidence/phase6/challenge-sources-20261115/most-neptune-june.json).
The earlier support ZIP predates this finding; include this updated draft and
the new MOST receipt when reporting the issue.

We are investigating failed SPHEREx discovery from a Windows client in the
Europe/Berlin timezone. Requests on 2026-11-15 at 22:04–22:14 UTC returned HTTP
502 or timed out. The problem reproduces outside our application using Python
httpx, Python urllib and native Windows curl 8.13.0/Schannel. No environment or
system proxy was configured. DNS resolved irsa.ipac.caltech.edu to 134.4.54.42.
We have not yet verified the same requests from a second independent network.

Minimal reproduction:

```text
curl --max-time 20 "https://irsa.ipac.caltech.edu/TAP/availability"
curl --max-time 20 "https://irsa.ipac.caltech.edu/TAP/sync?QUERY=SELECT+TOP+1+planeid+FROM+spherex.plane&FORMAT=votable&MAXREC=1"
curl --max-time 20 "https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_dr1&POS=circle+127.69444+-39.17760+0.01&RESPONSEFORMAT=HTML"
```

The 341-byte 502 body reports an invalid upstream response and an error reading
from the remote server. SHA-256:
`6c5cbf315d1e65021bda341d39f2f9126b1e63d3099d07c315894bd11add085b`.
The same error also occurred for TAP_SCHEMA.tables, fp_psc and a minimal
spherex.obscore query without geometry. Availability intermittently returned
200 to our application, but science discovery did not recover.

Static `/cloud_access/` returned 200. Anonymous range reads of DR1/QR3 spectral
images from nasa-irsa-spherex returned 206. We distinguish storage access from
discovery. The official Explorer earlier reported TAP inaccessible; its
server-side spatial query also returned a 502 cause inside an HTTP 200 error
payload. A prior async job, ID 28362490, remained queued during observation;
later reads failed and cleanup could not be confirmed. We have not created
additional async jobs during this investigation.

Could you confirm:

1. Whether TAP/SIA discovery is experiencing a service incident, and whether
   a supported alternative discovery endpoint is available?
2. Whether the minimal queries above are expected to work currently, and any
   additional diagnostic fields you need from us?
3. Whether job 28362490 remains active and can be cleaned up?
4. Whether a public bulk metadata manifest exists for DR1/QR3 spectral images,
   including footprints, detector, observation bounds, object URL and release?
   We found directory listings but no manifest at the root/release/level2 levels
   inspected. We have not exhaustively scanned all objects.

Attach selected diagnostics from
[`archive-execution-20261115`](../evidence/phase6/archive-execution-20261115/),
including `portable-local/`, `environment.json`, `curl.headers`, `curl.body`
and the previous [baseline](../evidence/phase6/archive-recovery-20261115/).
These contain public queries and no authentication credentials. The larger
header feasibility samples are unnecessary for the initial support request.
