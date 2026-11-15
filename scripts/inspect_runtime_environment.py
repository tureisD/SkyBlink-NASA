"""Read-only Windows process configuration receipt, emitting allowlisted values only.

No process is paused or modified. Raw environment blocks are never saved or printed.
The x64 PEB offsets used here are Windows implementation details; failures are explicit.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import re
import struct
from urllib.parse import urlsplit


def inspect(pid: int, allowed: set[str]) -> dict:
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("This diagnostic requires 64-bit Python on Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())

    def read(address: int, size: int) -> bytes:
        data = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        ok = kernel.ReadProcessMemory(handle, address, data, size, ctypes.byref(got))
        if not ok or got.value != size:
            raise ctypes.WinError(ctypes.get_last_error())
        return data.raw

    def pointer(address: int) -> int:
        return struct.unpack("<Q", read(address, 8))[0]

    def unicode_string(address: int) -> str:
        length = struct.unpack("<H", read(address, 2))[0]
        return read(pointer(address + 8), length).decode("utf-16-le")

    try:
        info = ctypes.create_string_buffer(48)
        ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.c_void_p]
        status = ntdll.NtQueryInformationProcess(handle, 0, info, 48, None)
        if status:
            raise RuntimeError(f"NtQueryInformationProcess status {status}")
        peb = struct.unpack_from("<Q", info.raw, 8)[0]
        parameters = pointer(peb + 0x20)
        cwd = unicode_string(parameters + 0x38)
        address = pointer(parameters + 0x80)
        block = bytearray()
        # Environment memory can end at a region boundary: read one UTF-16 unit
        # at a time until its explicit double-NUL terminator, with a fixed cap.
        while len(block) < 262144:
            block.extend(read(address + len(block), 2))
            if len(block) >= 4 and block[-4:] == b"\x00\x00\x00\x00":
                break
        else:
            raise RuntimeError("Environment block exceeded diagnostic limit")
        values = {}
        proxies = {}
        for item in block.decode("utf-16-le").split("\x00"):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            if key in allowed:
                if key.startswith("IRSA_") and "://" in value:
                    url = urlsplit(value)
                    value = f"{url.scheme}://{url.hostname}{url.path}"  # never credentials/query
                values[key] = value
            if key.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}:
                url = urlsplit(value)
                proxies[key] = {"configured": bool(value), "hostname": url.hostname, "port": url.port}
        return {"pid": pid, "cwd": cwd, "explicit_backend_settings": values,
                "proxy_endpoints_without_credentials": proxies,
                "missing_allowlisted_settings_use_source_defaults": sorted(allowed - values.keys())}
    finally:
        kernel.CloseHandle(handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pids", nargs="+", type=int)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "backend/core/config.py"
    allowed = set(re.findall(r'_env_\w+\(\s*"([A-Z0-9_]+)"', source.read_text()))
    receipt = {"scope": "Read-only x64 Windows PEB; allowlisted config only; no raw environment retained",
               "source_config_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "processes": []}
    for pid in args.pids:
        try:
            receipt["processes"].append(inspect(pid, allowed))
        except Exception as error:
            receipt["processes"].append({"pid": pid, "error": str(error)})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
