"""Minimal PNG encoder (stdlib only) for atlas display exports."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


def write_png_rgb(path: Path, rgb: NDArray[np.uint8]) -> None:
    """Write ``rgb[H,W,3]`` uint8 as an RGB PNG."""
    arr = np.asarray(rgb, dtype=np.uint8)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError("rgb must have shape [H,W,3]")
    height, width, _ = arr.shape
    raw = bytearray()
    for j in range(height):
        raw.append(0)  # filter: None
        raw.extend(arr[j].tobytes())
    compressed = zlib.compress(bytes(raw), level=6)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def write_png_rgba(path: Path, rgba: NDArray[np.uint8]) -> None:
    """Write ``rgba[H,W,4]`` uint8 as an RGBA PNG."""
    arr = np.asarray(rgba, dtype=np.uint8)
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("rgba must have shape [H,W,4]")
    height, width, _ = arr.shape
    raw = bytearray()
    for j in range(height):
        raw.append(0)
        raw.extend(arr[j].tobytes())
    compressed = zlib.compress(bytes(raw), level=6)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
