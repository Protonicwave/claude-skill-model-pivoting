"""Read the JSON payload Claude Code passes to a hook on standard input."""

import json
from typing import BinaryIO

# Agent briefs can carry pasted files, so the bound is generous; a payload
# past it is treated like a malformed one rather than parsed partially.
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024


def read_payload(stream: BinaryIO) -> dict[str, object]:
    """Parse the payload, or return {} if it is oversized, not JSON or not an object.

    A routing hook must never block work, so a payload it cannot read means
    the hook does nothing.
    """
    raw = stream.read(MAX_PAYLOAD_BYTES + 1)
    if len(raw) > MAX_PAYLOAD_BYTES:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
