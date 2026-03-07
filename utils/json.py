from __future__ import annotations

from datetime import datetime, date
import re
import os
from pathlib import Path
from typing import Any

import json
import pickle


def json_default(obj: Any) -> Any:
    """Default serializer for json.dumps/json.dump."""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def read_json(path: Path | str, binary: bool = False) -> Any:
    """Read JSON from a file."""
    path = _normalize_path(path)

    if binary:
        with open(path, "rb") as f:
            return pickle.load(f)

    return json.loads(path.read_text(encoding="utf-8"))


def write_json(
    path: Path | str,
    data: Any,
    *,
    indentValue: int = 4,
    binary: bool = False,
    protocol: int = pickle.HIGHEST_PROTOCOL,
) -> None:
    """Write JSON to a file."""
    path = _normalize_path(path)

    path.parent.mkdir(parents=True, exist_ok=True)

    if binary:
        # Write pickle in binary mode
        with path.open("wb") as f:
            pickle.dump(data, f, protocol=protocol)
        return

    path.write_text(
        json.dumps(data, indent=indentValue, ensure_ascii=False, default=json_default),
        encoding="utf-8",
    )


def _normalize_path(path: Path | str) -> Path:
    """Map Windows drive paths to WSL mounts when running on POSIX."""
    if isinstance(path, Path):
        path_str = str(path)
    else:
        path_str = path

    if os.name == "posix":
        match = re.match(r"^([A-Za-z]):[\\/](.*)$", path_str)
        if match:
            drive = match.group(1).lower()
            rest = match.group(2).replace("\\", "/")
            return Path(f"/mnt/{drive}/{rest}")

    return Path(path)
