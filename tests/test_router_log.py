import json
from pathlib import Path

from router_log import append_step, format_summary, summarise


def test_appends_one_json_line_per_step(tmp_path: Path) -> None:
    log = tmp_path / "nested" / "log.jsonl"
    append_step(log, "search", "router-scout", "done")
    append_step(log, "edit", "router-worker", "failed")
    text = log.read_text(encoding="utf-8")
    entries = [json.loads(line) for line in text.splitlines()]
    assert [entry["result"] for entry in entries] == ["done", "failed"]
    assert all(entry["time"].endswith("+00:00") for entry in entries)


def test_summary_counts_results_per_task_type_and_tier(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    append_step(log, "edit", "router-worker", "done")
    append_step(log, "edit", "router-worker", "failed")
    append_step(log, "edit", "router-expert", "done")
    summary = summarise(log)
    assert summary.counts[("edit", "router-worker")] == {"done": 1, "failed": 1}
    assert summary.counts[("edit", "router-expert")] == {"done": 1}
    assert summary.skipped_lines == 0


def test_summary_skips_malformed_lines(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    append_step(log, "search", "router-scout", "done")
    malformed = [
        "not json",
        '{"task_type": "search"}',
        "[1, 2]",
        '{"task_type": "a", "tier": "b", "result": "maybe"}',
    ]
    with log.open("a", encoding="utf-8") as stream:
        stream.writelines(line + "\n" for line in malformed)
    summary = summarise(log)
    assert summary.counts == {("search", "router-scout"): {"done": 1}}
    assert summary.skipped_lines == 4


def test_summary_of_missing_log_is_empty(tmp_path: Path) -> None:
    summary = summarise(tmp_path / "absent.jsonl")
    assert summary.counts == {}
    assert summary.skipped_lines == 0


def test_format_shows_counts_and_skipped_lines(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    append_step(log, "search", "router-scout", "failed")
    with log.open("a", encoding="utf-8") as stream:
        stream.write("not json\n")
    lines = format_summary(summarise(log)).splitlines()
    assert lines[1].split() == ["search", "router-scout", "0", "1", "0"]
    assert lines[2] == "Skipped 1 malformed line(s)."


def test_format_of_empty_summary(tmp_path: Path) -> None:
    summary = summarise(tmp_path / "absent.jsonl")
    assert format_summary(summary) == "No routed steps logged yet."
