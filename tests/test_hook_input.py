import io
import json

import pytest
from hook_input import MAX_PAYLOAD_BYTES, read_payload


@pytest.mark.parametrize("raw", [b"", b"not json", b"[1, 2]", b"\xff\xfe"])
def test_unreadable_payload_reads_as_empty(raw: bytes) -> None:
    assert read_payload(io.BytesIO(raw)) == {}


def test_oversized_payload_reads_as_empty() -> None:
    raw = b"{" + b" " * MAX_PAYLOAD_BYTES + b"}"
    assert read_payload(io.BytesIO(raw)) == {}


def test_payload_object_is_parsed_from_utf8() -> None:
    raw = json.dumps({"tool_input": {"prompt": "café"}}, ensure_ascii=False)
    assert read_payload(io.BytesIO(raw.encode("utf-8"))) == {
        "tool_input": {"prompt": "café"}
    }
