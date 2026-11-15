"""Telemetry sidecar codec (contract 1.1.0 ``epochs[].telemetry``).

Layout (frozen, additive 1.1.0)
-------------------------------
A gzip stream containing, in order and little-endian:

1. one ``float16`` 240 x 240 plane of surface brightness in MJy/sr;
2. one ``uint32`` 240 x 240 plane of the Table 16 bitwise-OR union of the
   flags of every band that contributed to the displayed coadd.

The decoded payload is exactly ``240*240*2 + 240*240*4 = 345600`` bytes.  The
default gzip level gives the measured 80-105 KiB size; the sidecar is served
as ``application/gzip`` and is *not* wrapped in ``Content-Encoding``.

This module is deliberately dependency-light (numpy + stdlib) so the science
builder, the API loader, and the frontend-facing smoke tests can share it.
The sidecar is display/telemetry data: it never changes the science arrays and
``BIT_SOURCE`` is preserved in the flag plane.
"""

from __future__ import annotations

import gzip
import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

TELEMETRY_FORMAT = "float16_uint32_le_gzip"
TELEMETRY_WIDTH = 240
TELEMETRY_HEIGHT = 240
TELEMETRY_IMAGE_DTYPE = np.dtype("<f2")
TELEMETRY_FLAGS_DTYPE = np.dtype("<u4")
TELEMETRY_IMAGE_BYTES = TELEMETRY_WIDTH * TELEMETRY_HEIGHT * 2
TELEMETRY_FLAGS_BYTES = TELEMETRY_WIDTH * TELEMETRY_HEIGHT * 4
TELEMETRY_DECODED_BYTES = TELEMETRY_IMAGE_BYTES + TELEMETRY_FLAGS_BYTES
TELEMETRY_GZIP_LEVEL = 6
GZIP_MAGIC = b"\x1f\x8b"
#: float16 cannot represent larger surface brightness values; clamp instead of
#: emitting ``inf``.  65504 MJy/sr is far beyond any unsaturated SPHEREx pixel.
FLOAT16_MAX = float(np.finfo(np.float16).max)


class TelemetryError(ValueError):
    """The sidecar is malformed or does not match the declared asset."""


@dataclass(frozen=True)
class TelemetryPlanes:
    """Decoded telemetry sidecar."""

    image_mjy_sr: np.ndarray  # float32, NaN for hard-masked/absent pixels
    flags: np.ndarray  # uint32 Table 16 bitmask
    width: int
    height: int

    @property
    def byte_size(self) -> int:
        return self.width * self.height * 6


def telemetry_filename(epoch_id: str) -> str:
    """Canonical catalog/live sidecar filename for one epoch."""
    safe = str(epoch_id).strip()
    if not safe or "/" in safe or "\\" in safe or ".." in safe:
        raise TelemetryError(f"invalid epoch id for a telemetry sidecar: {epoch_id!r}")
    return f"telemetry_{safe}.bin.gz"


def _prepare_planes(
    image_mjy_sr: np.ndarray,
    flags: np.ndarray,
    *,
    width: int,
    height: int,
) -> tuple[np.ndarray, np.ndarray]:
    image = np.asarray(image_mjy_sr, dtype=np.float64)
    flag_plane = np.asarray(flags, dtype=np.uint32)
    expected = (int(height), int(width))
    if image.shape != expected:
        raise TelemetryError(
            f"image shape {image.shape} does not match {width}x{height}"
        )
    if flag_plane.shape != expected:
        raise TelemetryError(
            f"flags shape {flag_plane.shape} does not match {width}x{height}"
        )

    finite = np.isfinite(image)
    with np.errstate(over="ignore", invalid="ignore"):
        quantized = image.astype(np.float16)
    overflow = finite & ~np.isfinite(quantized)
    if np.any(overflow):
        quantized = np.array(quantized, dtype=np.float16, copy=True)
        quantized[overflow] = np.copysign(
            np.float16(FLOAT16_MAX), image[overflow]
        ).astype(np.float16)
    return quantized, flag_plane


def encode_telemetry(
    image_mjy_sr: np.ndarray,
    flags: np.ndarray,
    *,
    width: int = TELEMETRY_WIDTH,
    height: int = TELEMETRY_HEIGHT,
) -> bytes:
    """Encode one float16 MJy/sr plane + one uint32 flag plane, gzipped."""
    image, flag_plane = _prepare_planes(
        image_mjy_sr, flags, width=width, height=height
    )
    raw = (
        image.astype(TELEMETRY_IMAGE_DTYPE, copy=False).tobytes(order="C")
        + flag_plane.astype(TELEMETRY_FLAGS_DTYPE, copy=False).tobytes(order="C")
    )
    if len(raw) != width * height * 6:
        raise TelemetryError("internal telemetry layout error")
    return gzip.compress(raw, compresslevel=TELEMETRY_GZIP_LEVEL, mtime=0)


def write_telemetry_sidecar(
    path: Path,
    image_mjy_sr: np.ndarray,
    flags: np.ndarray,
    *,
    width: int = TELEMETRY_WIDTH,
    height: int = TELEMETRY_HEIGHT,
) -> int:
    """Write the sidecar atomically and return its gzipped byte size."""
    content = encode_telemetry(
        image_mjy_sr, flags, width=width, height=height
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)
    return len(content)


def decode_telemetry(
    content: bytes,
    *,
    width: int = TELEMETRY_WIDTH,
    height: int = TELEMETRY_HEIGHT,
) -> TelemetryPlanes:
    """Decode and validate a sidecar payload."""
    content = bytes(content)
    if not content.startswith(GZIP_MAGIC):
        raise TelemetryError("telemetry sidecar is not gzip-compressed")
    try:
        raw = gzip.decompress(content)
    except OSError as exc:  # includes BadGzipFile / EOFError
        raise TelemetryError(f"telemetry sidecar could not be decompressed: {exc}") from exc

    expected = int(width) * int(height) * 6
    if len(raw) != expected:
        raise TelemetryError(
            f"telemetry payload is {len(raw)} bytes; expected {expected} "
            f"for {width}x{height} (float16 + uint32)"
        )
    image_bytes = int(width) * int(height) * 2
    image = np.frombuffer(raw[:image_bytes], dtype=TELEMETRY_IMAGE_DTYPE)
    flag_plane = np.frombuffer(raw[image_bytes:], dtype=TELEMETRY_FLAGS_DTYPE)
    image = np.array(image, dtype=np.float32).reshape(int(height), int(width))
    flag_plane = np.array(flag_plane, dtype=np.uint32).reshape(
        int(height), int(width)
    )
    return TelemetryPlanes(
        image_mjy_sr=image,
        flags=flag_plane,
        width=int(width),
        height=int(height),
    )


def read_telemetry_sidecar(
    path: Path,
    *,
    width: int = TELEMETRY_WIDTH,
    height: int = TELEMETRY_HEIGHT,
) -> TelemetryPlanes:
    """Read and decode a sidecar from disk."""
    content = Path(path).read_bytes()
    return decode_telemetry(content, width=width, height=height)


def validate_telemetry_asset(
    path: Path,
    *,
    byte_size: int | None = None,
    width: int = TELEMETRY_WIDTH,
    height: int = TELEMETRY_HEIGHT,
) -> TelemetryPlanes:
    """Validate a sidecar on disk against an optional declared byte size."""
    path = Path(path)
    actual = path.stat().st_size
    if byte_size is not None and int(byte_size) != actual:
        raise TelemetryError(
            f"telemetry byte_size {byte_size} does not match {actual} on disk"
        )
    planes = read_telemetry_sidecar(path, width=width, height=height)
    if int(width) * int(height) * 6 != planes.byte_size:
        raise TelemetryError("decoded telemetry plane size mismatch")
    return planes


def is_telemetry_filename(filename: str) -> bool:
    value = str(filename)
    return value.startswith("telemetry_") and value.endswith(".bin.gz")


def is_finite_geometry(pa_deg: float, grad_um_per_arcsec: float) -> bool:
    """Shared finite-value gate for ``lvf_geometry`` payloads."""
    try:
        pa = float(pa_deg)
        grad = float(grad_um_per_arcsec)
    except (TypeError, ValueError):
        return False
    return (
        math.isfinite(pa)
        and math.isfinite(grad)
        and grad > 0.0
    )


__all__ = [
    "FLOAT16_MAX",
    "GZIP_MAGIC",
    "TELEMETRY_DECODED_BYTES",
    "TELEMETRY_FLAGS_BYTES",
    "TELEMETRY_FLAGS_DTYPE",
    "TELEMETRY_FORMAT",
    "TELEMETRY_HEIGHT",
    "TELEMETRY_IMAGE_BYTES",
    "TELEMETRY_IMAGE_DTYPE",
    "TELEMETRY_WIDTH",
    "TelemetryError",
    "TelemetryPlanes",
    "decode_telemetry",
    "encode_telemetry",
    "is_finite_geometry",
    "is_telemetry_filename",
    "read_telemetry_sidecar",
    "telemetry_filename",
    "validate_telemetry_asset",
    "write_telemetry_sidecar",
]
