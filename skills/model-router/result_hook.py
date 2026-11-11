"""SubagentStop hook: log each router subagent's result.

The task type comes from the brief's `Task type:` line, which is the first
user line of the subagent's transcript, and the result from the `Result:`
line of its reply. A step missing either is not logged, so the log holds
only steps that were briefed and answered as the skill describes.
"""

import itertools
import json
import sys
from pathlib import Path
from typing import cast

from hook_input import read_payload
from router_log import DEFAULT_LOG_PATH, RESULTS, Result, append_step

ROUTER_AGENT_PREFIX = "router-"
TASK_TYPE_LABEL = "Task type:"
RESULT_LABEL = "Result:"
# The brief opens the transcript, so a long scan only reads the subagent's
# own work, which can run to thousands of lines.
MAX_BRIEF_SCAN_LINES = 50


def labelled_value(text: str, label: str) -> str | None:
    """The text after the first line starting with label, ignoring emphasis."""
    for line in text.splitlines():
        plain = line.replace("*", "").strip()
        if plain.startswith(label):
            return plain.removeprefix(label).strip() or None
    return None


def parse_result(reply: str) -> Result | None:
    value = labelled_value(reply, RESULT_LABEL)
    if value is None:
        return None
    word = value.split()[0].strip(".").lower()
    # Membership in RESULTS is exactly the Literal's set of values.
    return cast(Result, word) if word in RESULTS else None


def read_brief(transcript: Path) -> str | None:
    """The first user message's text, if it is plain text within the scan limit."""
    with transcript.open(encoding="utf-8") as stream:
        for line in itertools.islice(stream, MAX_BRIEF_SCAN_LINES):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict) or entry.get("type") != "user":
                continue
            message = entry.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            return content if isinstance(content, str) else None
    return None


def log_result(payload: dict[str, object], log_path: Path) -> None:
    """Append the payload's routed step to log_path, if it is one."""
    agent_type = payload.get("agent_type")
    transcript = payload.get("agent_transcript_path")
    reply = payload.get("last_assistant_message")
    if not (isinstance(agent_type, str) and agent_type.startswith(ROUTER_AGENT_PREFIX)):
        return
    if not (isinstance(transcript, str) and isinstance(reply, str)):
        return
    result = parse_result(reply)
    try:
        brief = read_brief(Path(transcript))
    except (OSError, UnicodeDecodeError):
        return
    task_type = labelled_value(brief, TASK_TYPE_LABEL) if brief else None
    if result is None or task_type is None:
        return
    append_step(log_path, task_type, agent_type, result)


def main() -> int:  # pragma: no cover: wiring, proved by the subprocess tests
    log_result(read_payload(sys.stdin.buffer), DEFAULT_LOG_PATH)
    return 0


if __name__ == "__main__":  # pragma: no cover: wiring
    sys.exit(main())
