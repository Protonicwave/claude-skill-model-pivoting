"""Report where Claude Code spend went, from the session transcripts.

Run as:  python usage_report.py [--since YYYY-MM-DD]

Reads the main chat's transcripts at ~/.claude/projects/<project>/<session>.jsonl
and each subagent's at <project>/<session>/subagents/**/agent-<id>.jsonl, whose
sibling .meta.json names the agent type. Figures are list-price equivalents
from PRICES: a subscription is not billed per token, so they compare choices
rather than predict a bill.
"""

import argparse
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from pathlib import Path

from result_hook import ROUTER_AGENT_PREFIX
from router_log import DEFAULT_LOG_PATH, format_summary, summarise

PROJECTS_DIR = Path.home() / ".claude" / "projects"
MAIN_SOURCE = "main"
UNKNOWN_AGENT_TYPE = "unknown"
# Claude Code records turns it made up locally, such as an interrupted reply,
# under this model name with zero usage.
SYNTHETIC_MODEL = "<synthetic>"
# Transcripts are mostly tool results and attachments; a line without this
# text cannot be an assistant turn, so it is not worth parsing.
ASSISTANT_MARKER = '"assistant"'
TOKENS_PER_MILLION = 1_000_000

type MessageKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class Rates:
    """List prices in USD per million tokens."""

    base: float
    write_5m: float
    write_1h: float
    read: float
    output: float


@dataclass(frozen=True, slots=True)
class Price:
    rates: Rates
    # (prompt tokens, rates): a prompt longer than the threshold is priced
    # at these rates instead, for models priced in two tiers.
    long_prompt: tuple[int, Rates] | None = None


PRICES_AS_OF = "2026-11-11"
PRICES: dict[str, Price] = {
    "claude-fable-5-2": Price(Rates(8, 10, 16, 0.20, 40)),
    "claude-opus-5-5": Price(Rates(4, 5, 8, 0.20, 20)),
    "claude-sonnet-5-5": Price(Rates(2, 2.5, 4, 0.10, 10)),
    "claude-haiku-5-5": Price(
        Rates(0.10, 0.125, 0.20, 0.01, 0.50),
        long_prompt=(100_000, Rates(0.50, 0.625, 1, 0.05, 2.50)),
    ),
}


@dataclass(frozen=True, slots=True)
class Usage:
    input: int
    write_5m: int
    write_1h: int
    read: int
    output: int

    @property
    def prompt_tokens(self) -> int:
        return self.input + self.write_5m + self.write_1h + self.read


@dataclass(frozen=True, slots=True)
class Turn:
    time: datetime
    # MAIN_SOURCE for the main chat, otherwise the subagent's agent type.
    source: str
    # The transcript file's stem: the session ID, or agent-<id> for a subagent.
    transcript: str
    model: str
    usage: Usage


@dataclass(slots=True)
class Spend:
    turns: int = 0
    transcripts: set[str] = field(default_factory=set)
    cost_usd: float = 0.0
    unpriced_tokens: int = 0


def cost_usd(model: str, usage: Usage) -> float | None:
    """List-price cost of one turn, or None for a model PRICES does not list."""
    price = PRICES.get(model)
    if price is None:
        return None
    rates = price.rates
    if price.long_prompt is not None and usage.prompt_tokens > price.long_prompt[0]:
        rates = price.long_prompt[1]
    return (
        usage.input * rates.base
        + usage.write_5m * rates.write_5m
        + usage.write_1h * rates.write_1h
        + usage.read * rates.read
        + usage.output * rates.output
    ) / TOKENS_PER_MILLION


def token_count(fields: dict[str, object], key: str) -> int | None:
    value = fields.get(key, 0)
    # bool is a subclass of int, and JSON true is not a count.
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def parse_usage(value: object) -> Usage | None:
    if not isinstance(value, dict):
        return None
    split = value.get("cache_creation")
    if isinstance(split, dict):
        writes = (
            token_count(split, "ephemeral_5m_input_tokens"),
            token_count(split, "ephemeral_1h_input_tokens"),
        )
    else:
        writes = (token_count(value, "cache_creation_input_tokens"), 0)
    counts = (
        token_count(value, "input_tokens"),
        *writes,
        token_count(value, "cache_read_input_tokens"),
        token_count(value, "output_tokens"),
    )
    valid = [count for count in counts if count is not None]
    return Usage(*valid) if len(valid) == len(counts) else None


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_turn(
    line: str, source: str, transcript: str
) -> tuple[MessageKey, Turn] | None:
    """The turn on an assistant line with usage, keyed for deduplication."""
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None
    message = entry.get("message") if isinstance(entry, dict) else None
    if not isinstance(message, dict) or entry.get("type") != "assistant":
        return None
    model, message_id = message.get("model"), message.get("id")
    if not isinstance(model, str) or model == SYNTHETIC_MODEL:
        return None
    usage, when = parse_usage(message.get("usage")), parse_time(entry.get("timestamp"))
    if not isinstance(message_id, str) or usage is None or when is None:
        return None
    request_id = entry.get("requestId")
    key = (message_id, request_id if isinstance(request_id, str) else "")
    return key, Turn(when, source, transcript, model, usage)


def agent_type(transcript: Path) -> str:
    try:
        meta = json.loads(
            transcript.with_suffix(".meta.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return UNKNOWN_AGENT_TYPE
    value = meta.get("agentType") if isinstance(meta, dict) else None
    return value if isinstance(value, str) else UNKNOWN_AGENT_TYPE


def transcripts(projects_dir: Path) -> Iterator[tuple[Path, str]]:
    """Each transcript with its source; the directory depth is fixed by Claude Code."""
    for path in sorted(projects_dir.glob("*/*.jsonl")):
        yield path, MAIN_SOURCE
    for path in sorted(projects_dir.glob("*/*/subagents/**/agent-*.jsonl")):
        yield path, agent_type(path)


def read_turns(projects_dir: Path, since: datetime | None = None) -> list[Turn]:
    """Every assistant turn under projects_dir once, oldest first.

    Claude Code writes one line per content block, each repeating the
    message's usage, and a resumed session copies earlier lines, so a turn
    is counted once per (message ID, request ID) across all files.
    """
    seen: set[MessageKey] = set()
    turns: list[Turn] = []
    for path, source in transcripts(projects_dir):
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                parsed = (
                    parse_turn(line, source, path.stem)
                    if ASSISTANT_MARKER in line
                    else None
                )
                if parsed is None or parsed[0] in seen:
                    continue
                seen.add(parsed[0])
                if since is None or parsed[1].time >= since:
                    turns.append(parsed[1])
    return sorted(turns, key=lambda turn: turn.time)


def spend_by_source(turns: list[Turn]) -> dict[tuple[str, str], Spend]:
    spend: dict[tuple[str, str], Spend] = {}
    for turn in turns:
        row = spend.setdefault((turn.source, turn.model), Spend())
        row.turns += 1
        row.transcripts.add(turn.transcript)
        cost = cost_usd(turn.model, turn.usage)
        if cost is None:
            row.unpriced_tokens += turn.usage.prompt_tokens + turn.usage.output
        else:
            row.cost_usd += cost
    return spend


def is_unrouted(source: str) -> bool:
    return source != MAIN_SOURCE and not source.startswith(ROUTER_AGENT_PREFIX)


def unrouted_totals(spend: dict[tuple[str, str], Spend]) -> tuple[int, float]:
    """(spawns, cost) of subagents that are not router tiers."""
    rows = [row for (source, _), row in spend.items() if is_unrouted(source)]
    return (
        sum(len(row.transcripts) for row in rows),
        sum(row.cost_usd for row in rows),
    )


def format_tokens(count: int) -> str:
    return f"{count / 1000:.1f}k"


def format_spend(turns: list[Turn]) -> list[str]:
    spend = spend_by_source(turns)
    total = sum(row.cost_usd for row in spend.values())
    lines = [
        "Spend by source and model",
        f"{'Source':<20} {'Model':<20} {'Runs':>5} {'Turns':>6} "
        f"{'USD':>9} {'Share':>6}",
    ]
    for (source, model), row in sorted(
        spend.items(), key=lambda item: -item[1].cost_usd
    ):
        share = row.cost_usd / total if total else 0.0
        lines.append(
            f"{source:<20} {model:<20} {len(row.transcripts):>5} {row.turns:>6} "
            f"{row.cost_usd:>9.2f} {share:>6.0%}"
        )
        if row.unpriced_tokens:
            lines.append(f"  unpriced: {format_tokens(row.unpriced_tokens)} tokens")
    spawns, unrouted_cost = unrouted_totals(spend)
    lines.append(f"Total: {total:.2f} USD")
    lines.append(f"Unrouted spawns: {spawns}, {unrouted_cost:.2f} USD")
    return lines


def format_report(turns: list[Turn]) -> str:
    if not turns:
        return "No assistant turns found."
    header = (
        f"{len(turns)} turns, {turns[0].time:%Y-%m-%d %H:%M} to "
        f"{turns[-1].time:%Y-%m-%d %H:%M} UTC. List-price equivalent USD, "
        f"prices as of {PRICES_AS_OF}; runs are sessions for main, spawns otherwise."
    )
    return "\n".join([header, "", *format_spend(turns)])


def main() -> int:  # pragma: no cover: argument parsing over tested functions
    parser = argparse.ArgumentParser(description="Report spend from transcripts.")
    parser.add_argument(
        "--since", type=date.fromisoformat, help="first day to include, YYYY-MM-DD"
    )
    arguments = parser.parse_args()
    since = (
        datetime.combine(arguments.since, time(), tzinfo=UTC)
        if arguments.since
        else None
    )
    print(format_report(read_turns(PROJECTS_DIR, since)))
    print()
    print(format_summary(summarise(DEFAULT_LOG_PATH)))
    return 0


if __name__ == "__main__":  # pragma: no cover: wiring
    sys.exit(main())
