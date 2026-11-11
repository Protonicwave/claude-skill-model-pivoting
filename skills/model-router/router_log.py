"""Record routed steps and summarise how each tier performs.

The log is one JSON object per line at ~/.claude/model-router/log.jsonl,
outside every project so no repository gains a stray file. Each line keeps
its time so the log can be read for a given week. Two steps logged at the
same instant can interleave on Windows, where appends are not atomic; the
summary then skips the damaged line and reports it as malformed.
"""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, get_args

Result = Literal["done", "failed", "blocked"]
RESULTS: tuple[str, ...] = get_args(Result)
DEFAULT_LOG_PATH = Path.home() / ".claude" / "model-router" / "log.jsonl"


@dataclass(frozen=True, slots=True)
class Summary:
    counts: dict[tuple[str, str], Counter[str]] = field(default_factory=dict)
    skipped_lines: int = 0


def append_step(log_path: Path, task_type: str, tier: str, result: Result) -> None:
    entry = {
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
        "task_type": task_type,
        "tier": tier,
        "result": result,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry) + "\n")


def parse_time(value: object) -> datetime | None:
    """An ISO 8601 time, read as UTC when it names no zone."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_entry(line: str) -> tuple[datetime, str, str, str] | None:
    """Return (time, task_type, tier, result) for a well-formed line, else None."""
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(entry, dict):
        return None
    logged_at = parse_time(entry.get("time"))
    task_type, tier, result = (
        entry.get(key) for key in ("task_type", "tier", "result")
    )
    if (
        logged_at is not None
        and isinstance(task_type, str)
        and isinstance(tier, str)
        and result in RESULTS
    ):
        return logged_at, task_type, tier, str(result)
    return None


def summarise(log_path: Path, since: datetime | None = None) -> Summary:
    """Count results per (task type, tier) from since onwards.

    A missing log is an empty summary.
    """
    counts: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    skipped_lines = 0
    if not log_path.exists():
        return Summary()
    with log_path.open(encoding="utf-8") as stream:
        for line in stream:
            parsed = parse_entry(line)
            if parsed is None:
                skipped_lines += 1
                continue
            logged_at, task_type, tier, result = parsed
            if since is None or logged_at >= since:
                counts[(task_type, tier)][result] += 1
    return Summary(counts=dict(counts), skipped_lines=skipped_lines)


def format_summary(summary: Summary) -> str:
    if not summary.counts:
        return "No routed steps logged yet."
    lines = [f"{'Task type':<24} {'Tier':<16} {'done':>5} {'failed':>7} {'blocked':>8}"]
    for (task_type, tier), results in sorted(summary.counts.items()):
        lines.append(
            f"{task_type:<24} {tier:<16} {results['done']:>5} "
            f"{results['failed']:>7} {results['blocked']:>8}"
        )
    if summary.skipped_lines:
        lines.append(f"Skipped {summary.skipped_lines} malformed line(s).")
    return "\n".join(lines)
