import json
import subprocess
import sys
from pathlib import Path

import pytest
from spawn_hook import POLICY_MODEL, hook_output

HOOK_PATH = Path(__file__).resolve().parent.parent / "skills/model-router/spawn_hook.py"


def agent_payload(tool_input: dict[str, object]) -> dict[str, object]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": tool_input,
    }


@pytest.mark.parametrize(
    "tool_input",
    [
        {
            "prompt": "Goal: x",
            "description": "find x",
            "subagent_type": "general-purpose",
        },
        {"prompt": "Goal: x", "description": "find x"},
        {"prompt": "Goal: x", "subagent_type": "general-purpose", "model": None},
        {"prompt": "Goal: x", "subagent_type": "general-purpose", "model": ""},
    ],
)
def test_general_purpose_spawn_without_model_gets_policy_model(
    tool_input: dict[str, object],
) -> None:
    output = hook_output(agent_payload(tool_input))
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["updatedInput"] == {**tool_input, "model": POLICY_MODEL}
    assert POLICY_MODEL in specific["additionalContext"]
    assert "model" in specific["additionalContext"]


@pytest.mark.parametrize(
    "tool_input",
    [
        {"prompt": "Goal: x", "subagent_type": "general-purpose", "model": "opus"},
        {"prompt": "Goal: x", "subagent_type": "router-scout"},
        {"prompt": "Goal: x", "subagent_type": "Explore"},
        {"prompt": "Goal: x", "subagent_type": "fork"},
    ],
)
def test_explicit_model_named_agent_and_fork_pass_through(
    tool_input: dict[str, object],
) -> None:
    assert hook_output(agent_payload(tool_input)) == {}


@pytest.mark.parametrize(
    "payload",
    [{}, {"tool_name": "Agent"}, {"tool_name": "Agent", "tool_input": "prompt"}],
)
def test_payload_without_tool_input_object_passes_through(
    payload: dict[str, object],
) -> None:
    assert hook_output(payload) == {}


def run_hook(stdin: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603  # fixed interpreter and script path
        [sys.executable, str(HOOK_PATH)], input=stdin, capture_output=True, check=False
    )


def test_hook_process_prints_updated_input() -> None:
    payload = agent_payload(
        {"prompt": "Goal: café", "subagent_type": "general-purpose"}
    )
    completed = run_hook(json.dumps(payload).encode("utf-8"))
    assert completed.returncode == 0
    output = json.loads(completed.stdout)
    assert output["hookSpecificOutput"]["updatedInput"]["model"] == POLICY_MODEL
    assert output["hookSpecificOutput"]["updatedInput"]["prompt"] == "Goal: café"


def test_hook_process_prints_empty_object_for_malformed_input() -> None:
    completed = run_hook(b"not json")
    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {}
