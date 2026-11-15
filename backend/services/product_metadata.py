"""Shared factual metadata; never infer a successful scientific validation."""
from datetime import datetime, timezone
import math

from astropy.time import Time


def creation_time(product: dict) -> datetime:
    """Use recorded product time, not a file mtime or the current request."""
    value = product.get("generated_at") or product.get("provenance", {}).get("generated_at")
    if not isinstance(value, str):
        raise ValueError("Product has no recorded creation time")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Product creation time has no timezone")
    return result.astimezone(timezone.utc)


def observation_range(records) -> dict | None:
    """Archive exposure bounds in UTC (the observed Level 2 TIMESYS)."""
    if not records:
        return None
    lower = min(float(record.mjd_lower) for record in records)
    upper = max(float(record.mjd_upper if record.mjd_upper is not None else record.mjd_lower) for record in records)
    return {
        "mjd_min": lower, "mjd_max": upper,
        "date_start_iso": Time(lower, format="mjd", scale="utc").isot[:10],
        "date_end_iso": Time(upper, format="mjd", scale="utc").isot[:10],
        "time_scale": "utc",
    }


def observation_label(bounds: dict | None, fallback: str) -> str:
    if bounds is None:
        return fallback
    return f"Observed {bounds['date_start_iso']} to {bounds['date_end_iso']} (samples not necessarily simultaneous)"


def measurement_availability(channels: list[dict]) -> dict:
    def finite(channel):
        value = channel.get("flux_ujy")
        return isinstance(value, (int, float)) and math.isfinite(value)
    reasons = sorted({reason for channel in channels for reason in channel.get("measurement_reasons", [])})
    if channels and not any(finite(channel) for channel in channels):
        reasons.append("NO_FINITE_FLUX")
    return {
        "total_channels": len(channels),
        "finite_channels": sum(finite(channel) for channel in channels),
        "usable_channels": sum(finite(channel) and channel.get("is_used_in_photometry") is True for channel in channels),
        "reasons": sorted(set(reasons)),
    }
