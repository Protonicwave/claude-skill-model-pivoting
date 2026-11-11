import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_output_hook import hook_output, quiet_command

HOOK_PATH = (
    Path(__file__).resolve().parent.parent / "skills/model-router/test_output_hook.py"
)


def bash_payload(tool_input: object) -> dict[str, object]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": tool_input,
    }


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("pytest", "pytest -q"),
        ("pytest tests/test_x.py -x", "pytest -q tests/test_x.py -x"),
        ("python -m pytest", "python -m pytest -q"),
        ("python3 -m pytest -k 'a and b'", "python3 -m pytest -q -k 'a and b'"),
        ("  pytest", "  pytest -q"),
        ("cargo test", "cargo test -q"),
        ("cargo test parser -- --nocapture", "cargo test -q parser -- --nocapture"),
        ("npm test", "npm test --silent"),
        ("npm test -- --watch=false", "npm test --silent -- --watch=false"),
    ],
)
def test_bare_test_command_gets_quiet_flag(command: str, expected: str) -> None:
    assert quiet_command(command) == expected


@pytest.mark.parametrize(
    "command",
    [
        "pytest | tail -5",
        "pytest && git commit",
        "pytest || true",
        "pytest; echo done",
        "pytest > out.txt",
        "pytest 2>&1",
        "pytest &",
        "pytest $TEST_ARGS",
        "pytest $(git diff --name-only)",
        "pytest `cat targets`",
        "pytest\nrm out.txt",
        "(pytest)",
        "cd tests && npm test",
    ],
)
def test_compound_command_is_untouched(command: str) -> None:
    assert quiet_command(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q",
        "pytest -qq",
        "pytest -xq",
        "pytest --quiet",
        "pytest -v tests",
        "python -m pytest -vv",
        "pytest --verbose",
        "pytest --verbosity=2",
        "cargo test -q",
        "cargo test --quiet",
        "cargo test -vv",
        "cargo test -- --quiet",
        "npm test -s",
        "npm test --silent",
        "npm test --loglevel=warn",
        "npm test --loglevel warn",
        "npm test -d",
        "npm test --verbose",
    ],
)
def test_command_with_verbosity_flag_is_untouched(command: str) -> None:
    assert quiet_command(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "",
        "git status",
        "pytestx",
        "pytest-watch",
        "python -m pytest_cov",
        "cargo testing",
        "npm run test",
        "echo pytest",
        "'pytest'",
        "pytest -k 'unterminated",
    ],
)
def test_other_command_is_untouched(command: str) -> None:
    assert quiet_command(command) is None


def test_hook_output_replaces_command_and_keeps_other_fields() -> None:
    tool_input = {"command": "pytest", "description": "Run tests", "timeout": 60000}
    output = hook_output(bash_payload(tool_input))
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["updatedInput"] == {**tool_input, "command": "pytest -q"}
    assert "-q" in specific["additionalContext"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"tool_name": "Bash"},
        bash_payload("pytest"),
        bash_payload({"description": "Run tests"}),
        bash_payload({"command": ["pytest"]}),
        bash_payload({"command": "git status"}),
    ],
)
def test_payload_without_bare_test_command_passes_through(
    payload: dict[str, object],
) -> None:
    assert hook_output(payload) == {}


def run_hook(stdin: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603  # fixed interpreter and script path
        [sys.executable, str(HOOK_PATH)], input=stdin, capture_output=True, check=False
    )


def test_hook_process_prints_updated_command() -> None:
    payload = bash_payload({"command": "python -m pytest", "description": "café"})
    completed = run_hook(json.dumps(payload).encode("utf-8"))
    assert completed.returncode == 0
    updated = json.loads(completed.stdout)["hookSpecificOutput"]["updatedInput"]
    assert updated == {"command": "python -m pytest -q", "description": "café"}


def test_hook_process_prints_empty_object_for_malformed_input() -> None:
    completed = run_hook(b"not json")
    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {}
