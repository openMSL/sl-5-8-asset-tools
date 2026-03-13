from __future__ import annotations

from pathlib import Path

from multiformats import CID
from multiformats.multihash import digest


def compute_file_cid(path: Path) -> str:
    with path.open("rb") as file_handle:
        data = file_handle.read()

    multihash = digest(data, "sha2-256")
    cid = CID("base32", 1, "raw", bytes(multihash))
    return cid.encode("base32")
