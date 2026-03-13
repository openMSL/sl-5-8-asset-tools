from __future__ import annotations

import hashlib
import os
import uuid

SL58_NAMESPACE = uuid.UUID("a3f2b8c1-7d4e-4f9a-b6e5-1c8d9a0e3f7b")


def create_uuid() -> str:
    """Create a UUID for asset identifiers.

    In deterministic mode (SL58_DETERMINISTIC=1), SL58_INPUT_HASH is set by
    the pipeline orchestrator.  When present, returns a UUID5 seeded by the
    input content hash with an incrementing counter for intra-process
    uniqueness.

    By default (no env var) returns a random UUID4.
    """
    input_hash = os.environ.get("SL58_INPUT_HASH")
    if input_hash:
        counter = getattr(create_uuid, "_counter", 0)
        create_uuid._counter = counter + 1
        name = f"{input_hash}:{counter}"
        return str(uuid.uuid5(SL58_NAMESPACE, name))
    return str(uuid.uuid4())
