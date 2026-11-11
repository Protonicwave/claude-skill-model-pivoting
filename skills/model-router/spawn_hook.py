"""PreToolUse hook for Agent: give an unrouted general-purpose spawn a model.

A general-purpose subagent with no model inherits the main chat's, which is
usually the most expensive one. This hook sets POLICY_MODEL on such a spawn
and tells the main chat it did. Named agents carry their own model, a fork
must share the main chat's cache, and an explicit model is a deliberate
choice, so all of those pass through untouched.
"""

import json
import sys

from hook_input import read_payload

POLICY_MODEL = "sonnet"
GENERAL_PURPOSE = "general-purpose"


def chosen_model(tool_input: dict[str, object]) -> str | None:
    """The model to set on this spawn, or None to leave it alone."""
    if tool_input.get("model"):
        return None
    if (tool_input.get("subagent_type") or GENERAL_PURPOSE) != GENERAL_PURPOSE:
        return None
    return POLICY_MODEL


def hook_output(payload: dict[str, object]) -> dict[str, object]:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return {}
    model = chosen_model(tool_input)
    if model is None:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {**tool_input, "model": model},
            "additionalContext": (
                f"model-router ran this general-purpose subagent on {model}. "
                "Pass model explicitly, or use a router-* agent, to choose another."
            ),
        }
    }


def main() -> int:  # pragma: no cover: wiring, proved by the subprocess tests
    print(json.dumps(hook_output(read_payload(sys.stdin.buffer))))
    return 0


if __name__ == "__main__":  # pragma: no cover: wiring
    sys.exit(main())
