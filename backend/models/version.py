"""The frozen API contract version.

Canonical import path (run the app from ``backend/``):

    from models.version import API_CONTRACT_VERSION

``backend.models.version`` is not canonical; the FastAPI app runs with
``backend/`` as the working directory (or ``PYTHONPATH=backend``).

1.0.0 was the O1 freeze. 1.1.0 is the additive Phase 2 contract:
telemetry sidecars, LVF geometry, optional candidates, and per-channel
photometry/aperture provenance. No existing field changed type or meaning.
1.2.0 is a data-value addition for DR1/QR3: ``release``/``collection``
accept ``DR1``, ``QR3``, and ``DR1+QR3`` (schema unchanged).
1.3.0 tightens measurement eligibility: unsupported local backgrounds produce
null flux/error and false is_used_in_photometry even for flag-clean pixels.
No fields are renamed, removed, or retyped; historical saved products remain
readable and are identified as pre-audit visualizations.
"""

# 1.4.0 adds explicit lineage/ranges/telemetry meaning and preserves creation time.
# 1.6.0 adds explicit known-exposure discovery with fresh upstream downloads.
# 1.7.0 adds explicit bounded spatial-index acquisition with fresh downloads.
API_CONTRACT_VERSION = "1.7.0"
