from __future__ import annotations

from datetime import datetime, date
import re
import os
import tempfile
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
    trailing_newline: bool = False,
) -> None:
    """Write JSON to a file."""
    path = _normalize_path(path)

    if binary:
        _write_bytes_atomic(path, pickle.dumps(data, protocol=protocol))
        return

    write_text(
        path,
        json.dumps(data, indent=indentValue, ensure_ascii=False, default=json_default),
        trailing_newline=trailing_newline,
    )


def _normalize_path(path: Path | str) -> Path:
    """Map Windows drive paths to WSL mounts only when running inside WSL."""
    if isinstance(path, Path):
        path_str = str(path)
    else:
        path_str = path

    if _is_wsl():
        match = re.match(r"^([A-Za-z]):[\\/](.*)$", path_str)
        if match:
            drive = match.group(1).lower()
            rest = match.group(2).replace("\\", "/")
            return Path(f"/mnt/{drive}/{rest}")

    return Path(path)


def write_text(
    path: Path | str,
    content: str,
    *,
    encoding: str = "utf-8",
    trailing_newline: bool = False,
) -> None:
    """Write text content atomically."""
    path = _normalize_path(path)

    if trailing_newline and not content.endswith("\n"):
        content += "\n"

    _write_bytes_atomic(path, content.encode(encoding))


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _is_wsl() -> bool:
    if os.name != "posix":
        return False

    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True

    try:
        kernel_release = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8")
    except OSError:
        return False

    return "microsoft" in kernel_release.lower()
