"""PreToolUse hook for Bash: run a bare test command quietly.

Passing tests print a line each, and that output stays in the main chat's
context for the rest of the session. This hook adds the runner's quiet flag
to a bare pytest, cargo test or npm test command, so mostly failures print.

It adds a flag and never pipes the output: a pipe through tail would replace
the test's exit code with tail's, and results are accepted on exit codes. A
command the hook cannot read with certainty is left alone, as is one that
already chooses its own verbosity.
"""

import json
import re
import shlex
import sys
from dataclasses import dataclass

from hook_input import read_payload

# Operators make the command compound, and expansions can add flags the hook
# cannot see, so a command containing any of these is left alone.
SHELL_CONTROL_CHARACTERS = frozenset("|&;<>()`$\n\r")


@dataclass(frozen=True, slots=True)
class QuietRule:
    prefix: re.Pattern[str]
    flag: str
    verbosity_letters: str
    verbosity_options: tuple[str, ...]

    def has_verbosity_flag(self, arguments: list[str]) -> bool:
        return any(
            argument.startswith(self.verbosity_options)
            or (
                re.fullmatch(r"-[A-Za-z]+", argument) is not None
                and any(letter in argument for letter in self.verbosity_letters)
            )
            for argument in arguments
        )


QUIET_RULES = (
    QuietRule(
        re.compile(r"\s*(?:pytest|python3? -m pytest)(?=\s|$)"),
        "-q",
        "qv",
        ("--quiet", "--verbose", "--verbosity"),
    ),
    QuietRule(
        re.compile(r"\s*cargo test(?=\s|$)"), "-q", "qv", ("--quiet", "--verbose")
    ),
    QuietRule(
        re.compile(r"\s*npm test(?=\s|$)"),
        "--silent",
        "sqd",
        ("--silent", "--quiet", "--verbose", "--loglevel"),
    ),
)


def quiet_command(command: str) -> str | None:
    """command with its runner's quiet flag added, or None to leave it alone."""
    if not SHELL_CONTROL_CHARACTERS.isdisjoint(command):
        return None
    for rule in QUIET_RULES:
        match = rule.prefix.match(command)
        if match is None:
            continue
        rest = command[match.end() :]
        try:
            arguments = shlex.split(rest)
        except ValueError:
            return None
        if rule.has_verbosity_flag(arguments):
            return None
        return f"{command[: match.end()]} {rule.flag}{rest}"
    return None


def hook_output(payload: dict[str, object]) -> dict[str, object]:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return {}
    command = tool_input.get("command")
    if not isinstance(command, str):
        return {}
    quietened = quiet_command(command)
    if quietened is None:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {**tool_input, "command": quietened},
            "additionalContext": (
                f"model-router ran this as `{quietened}` to shorten passing "
                "output. Pass a verbosity flag to choose another."
            ),
        }
    }


def main() -> int:  # pragma: no cover: wiring, proved by the subprocess tests
    print(json.dumps(hook_output(read_payload(sys.stdin.buffer))))
    return 0


if __name__ == "__main__":  # pragma: no cover: wiring
    sys.exit(main())
