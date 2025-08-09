# ===============================
# backend/app/utils.py
# ===============================
from __future__ import annotations

import base64
import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from fastapi import HTTPException

HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def validate_hex_list(hex_list: List[str]) -> List[str]:
    """Validate and normalize a list of HEX colors (#RRGGBB).

    Ensures length between 3 and 10 inclusive.
    Returns normalized list with leading '#', uppercase.
    Raises HTTPException on invalid input.
    """
    if not (3 <= len(hex_list) <= 10):
        raise HTTPException(status_code=400, detail="Palette must have 3–10 HEX colors.")
    normalized: List[str] = []
    for h in hex_list:
        if not isinstance(h, str):
            raise HTTPException(status_code=400, detail=f"Palette item {h!r} is not a string.")
        h2 = h.strip()
        if not HEX_RE.match(h2):
            raise HTTPException(status_code=400, detail=f"Invalid HEX color: {h}")
        if not h2.startswith('#'):
            h2 = '#' + h2
        normalized.append(h2.upper())
    return normalized


def norm_hex(hex_str: str) -> str:
    if not HEX_RE.match(hex_str):
        raise HTTPException(status_code=400, detail=f"Invalid HEX color: {hex_str}")
    return hex_str.upper() if hex_str.startswith('#') else '#' + hex_str.upper()


def json_pretty(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)


def b64_png(buf: bytes) -> str:
    return base64.b64encode(buf).decode('ascii')


@dataclass
class TempSession:
    root: Path

    def __enter__(self) -> "TempSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Clean up on exit
        try:
            for p in self.root.rglob('*'):
                try:
                    p.unlink()
                except IsADirectoryError:
                    pass
            for p in sorted(self.root.glob('**/*'), reverse=True):
                try:
                    p.rmdir()
                except Exception:
                    pass
        except Exception:
            pass


class ZipBuilder:
    """Builds an in-memory zip from a directory or file map."""

    def __init__(self) -> None:
        self._buf = io.BytesIO()
        self._zip = zipfile.ZipFile(self._buf, mode='w', compression=zipfile.ZIP_DEFLATED)

    def write_bytes(self, arcname: str, data: bytes) -> None:
        zinfo = zipfile.ZipInfo(arcname)
        self._zip.writestr(zinfo, data)

    def write_text(self, arcname: str, text: str) -> None:
        self.write_bytes(arcname, text.encode('utf-8'))

    def write_file(self, arcname: str, file_path: Path) -> None:
        self._zip.write(file_path, arcname)

    def close(self) -> bytes:
        self._zip.close()
        self._buf.seek(0)
        return self._buf.read()

