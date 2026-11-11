import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from result_hook import MAX_BRIEF_SCAN_LINES, log_result
from router_log import summarise

HOOK_PATH = (
    Path(__file__).resolve().parent.parent / "skills/model-router/result_hook.py"
)
BRIEF = "Goal: find the parser.\nTask type: search\nSkill: none.\nChange: nothing."
REPLY = "Result: done\nEvidence: found at parser.py:12\nNotes: none"


def write_transcript(path: Path, lines: list[object]) -> Path:
    path.write_text(
        "".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8"
    )
    return path


def user_line(content: object) -> dict[str, object]:
    return {"type": "user", "message": {"role": "user", "content": content}}


def stop_payload(transcript: Path, reply: str = REPLY) -> dict[str, object]:
    return {
        "hook_event_name": "SubagentStop",
        "agent_type": "router-scout",
        "agent_transcript_path": str(transcript),
        "last_assistant_message": reply,
    }


def logged(log: Path) -> dict[tuple[str, str], dict[str, int]]:
    return {key: dict(counts) for key, counts in summarise(log).counts.items()}


def test_logs_task_type_tier_and_result(tmp_path: Path) -> None:
    transcript = write_transcript(tmp_path / "agent.jsonl", [user_line(BRIEF)])
    log = tmp_path / "log.jsonl"
    assert log_result(stop_payload(transcript), log)
    assert logged(log) == {("search", "router-scout"): {"done": 1}}


@pytest.mark.parametrize(
    ("reply", "result"),
    [
        ("**Result:** failed\nEvidence: exit 1", "failed"),
        ("Checked.\n  Result: Blocked.\nNotes: brief lacked a path", "blocked"),
    ],
)
def test_reads_result_through_emphasis_and_case(
    tmp_path: Path, reply: str, result: str
) -> None:
    transcript = write_transcript(tmp_path / "agent.jsonl", [user_line(BRIEF)])
    log = tmp_path / "log.jsonl"
    assert log_result(stop_payload(transcript, reply), log)
    assert logged(log) == {("search", "router-scout"): {result: 1}}


def test_brief_is_the_first_user_line(tmp_path: Path) -> None:
    lines: list[object] = [
        {"type": "system", "content": "start"},
        user_line(BRIEF),
        user_line("Task type: later"),
    ]
    transcript = write_transcript(tmp_path / "agent.jsonl", lines)
    log = tmp_path / "log.jsonl"
    assert log_result(stop_payload(transcript), log)
    assert logged(log) == {("search", "router-scout"): {"done": 1}}


@pytest.mark.parametrize(
    "reply",
    ["Evidence: none", "Result: maybe", "Result:", "Result: \nEvidence: x", ""],
)
def test_skips_reply_without_a_known_result(tmp_path: Path, reply: str) -> None:
    transcript = write_transcript(tmp_path / "agent.jsonl", [user_line(BRIEF)])
    log = tmp_path / "log.jsonl"
    assert not log_result(stop_payload(transcript, reply), log)
    assert not log.exists()


@pytest.mark.parametrize(
    "lines",
    [
        [user_line("Goal: x\nSkill: none.")],
        [user_line("Goal: x\nTask type:  \nSkill: none.")],
        [user_line([{"type": "text", "text": BRIEF}])],
        [{"type": "user"}],
        [{"type": "user", "message": "flat"}],
        [],
    ],
)
def test_skips_brief_without_a_task_type(tmp_path: Path, lines: list[object]) -> None:
    transcript = write_transcript(tmp_path / "agent.jsonl", lines)
    log = tmp_path / "log.jsonl"
    assert not log_result(stop_payload(transcript), log)
    assert not log.exists()


def test_skips_malformed_lines_before_the_brief(tmp_path: Path) -> None:
    transcript = tmp_path / "agent.jsonl"
    transcript.write_text(
        "not json\n[1]\n" + json.dumps(user_line(BRIEF)) + "\n", encoding="utf-8"
    )
    log = tmp_path / "log.jsonl"
    assert log_result(stop_payload(transcript), log)


def test_brief_past_the_scan_limit_is_not_read(tmp_path: Path) -> None:
    filler: list[object] = [{"type": "system"}] * MAX_BRIEF_SCAN_LINES
    transcript = write_transcript(tmp_path / "agent.jsonl", [*filler, user_line(BRIEF)])
    log = tmp_path / "log.jsonl"
    assert not log_result(stop_payload(transcript), log)


@pytest.mark.parametrize(
    "agent_type", ["general-purpose", "Explore", "", None, "my-router-scout"]
)
def test_skips_agents_outside_the_router(tmp_path: Path, agent_type: object) -> None:
    transcript = write_transcript(tmp_path / "agent.jsonl", [user_line(BRIEF)])
    log = tmp_path / "log.jsonl"
    payload = {**stop_payload(transcript), "agent_type": agent_type}
    assert not log_result(payload, log)
    assert not log.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"agent_transcript_path": None},
        {"agent_transcript_path": "missing.jsonl"},
        {"last_assistant_message": None},
    ],
)
def test_skips_payload_with_missing_fields(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    write_transcript(tmp_path / "agent.jsonl", [user_line(BRIEF)])
    log = tmp_path / "log.jsonl"
    payload = {**stop_payload(tmp_path / "agent.jsonl"), **changes}
    assert not log_result(payload, log)
    assert not log.exists()


def test_skips_transcript_that_is_a_directory(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    assert not log_result(stop_payload(tmp_path), log)


def test_skips_transcript_that_is_not_utf8(tmp_path: Path) -> None:
    transcript = tmp_path / "agent.jsonl"
    transcript.write_bytes(b"\xff\xfe not text\n")
    log = tmp_path / "log.jsonl"
    assert not log_result(stop_payload(transcript), log)


def run_hook(stdin: bytes, home: Path) -> subprocess.CompletedProcess[bytes]:
    environment = {**os.environ, "USERPROFILE": str(home), "HOME": str(home)}
    return subprocess.run(  # noqa: S603  # fixed interpreter and script path
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        check=False,
        env=environment,
    )


def test_hook_process_logs_to_the_home_log(tmp_path: Path) -> None:
    transcript = write_transcript(tmp_path / "agent.jsonl", [user_line(BRIEF)])
    completed = run_hook(json.dumps(stop_payload(transcript)).encode("utf-8"), tmp_path)
    assert completed.returncode == 0
    log = tmp_path / ".claude" / "model-router" / "log.jsonl"
    assert logged(log) == {("search", "router-scout"): {"done": 1}}


def test_hook_process_exits_cleanly_on_malformed_input(tmp_path: Path) -> None:
    completed = run_hook(b"not json", tmp_path)
    assert completed.returncode == 0
    assert completed.stdout == b""
    assert not (tmp_path / ".claude").exists()
