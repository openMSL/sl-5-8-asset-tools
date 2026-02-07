from __future__ import annotations

import uuid


def create_uuid() -> str:
    """Create a random UUID string.""" # e.g. 'f47ac10b-58cc-4372-a567-0e02b2c3d479'
    return str(uuid.uuid4())
