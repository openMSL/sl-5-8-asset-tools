from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
from typing import Any

import json
import pickle


def json_default(obj: Any) -> Any:
    """Default serializer for json.dumps/json.dump."""
    
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def read_json(path: Path, binary : bool = False) -> Any:
    """Read JSON from a file."""

    if binary:
        with open(path, 'rb') as f:
            return pickle.load(f)

    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any, *, indentValue:int = 4, binary: bool = False, protocol: int = pickle.HIGHEST_PROTOCOL)  -> None:
    """Write JSON to a file."""
    
    path.parent.mkdir(parents=True, exist_ok=True)

    if binary:
        # Write pickle in binary mode
        with path.open("wb") as f:
            pickle.dump(data, f, protocol=protocol)
        return    

    path.write_text(json.dumps(data, indent=indentValue, ensure_ascii=False, default=json_default), encoding="utf-8")
    