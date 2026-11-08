"""Check the router's agent definitions before they are installed.

Run as `python scripts/validate.py`. Exits 1 and prints one line per
problem if any file is invalid.
"""

import re
import sys
from pathlib import Path

MODEL_ALIASES = frozenset({"haiku", "sonnet", "opus", "fable", "inherit"})
MODEL_ID_PATTERN = re.compile(r"claude-[a-z0-9-]+")
EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})
REQUIRED_AGENT_FIELDS = ("name", "description", "model", "effort")
FRONTMATTER_DELIMITER = "---"
MAX_FRONTMATTER_LINES = 50


def read_frontmatter(text: str) -> dict[str, str] | None:
    """Return the flat `key: value` pairs between the opening `---` lines.

    Returns None when the text does not open with a closed frontmatter
    block within MAX_FRONTMATTER_LINES lines.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        return None
    fields: dict[str, str] = {}
    for line in lines[1 : MAX_FRONTMATTER_LINES + 1]:
        if line.strip() == FRONTMATTER_DELIMITER:
            return fields
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    return None


def is_known_model(model: str) -> bool:
    return model in MODEL_ALIASES or MODEL_ID_PATTERN.fullmatch(model) is not None


def check_agent(path: Path) -> list[str]:
    fields = read_frontmatter(path.read_text(encoding="utf-8"))
    if fields is None:
        return [f"{path}: no frontmatter block"]
    errors = [
        f"{path}: missing field '{field}'"
        for field in REQUIRED_AGENT_FIELDS
        if not fields.get(field)
    ]
    name = fields.get("name")
    if name and name != path.stem:
        errors.append(f"{path}: name '{name}' does not match file name '{path.stem}'")
    model = fields.get("model")
    if model and not is_known_model(model):
        errors.append(
            f"{path}: unknown model '{model}', expected an alias or a claude- model ID"
        )
    effort = fields.get("effort")
    if effort and effort not in EFFORT_LEVELS:
        expected = ", ".join(sorted(EFFORT_LEVELS))
        errors.append(f"{path}: unknown effort '{effort}', expected one of {expected}")
    return errors


def validate(repo_root: Path) -> list[str]:
    agent_paths = sorted((repo_root / "agents").glob("*.md"))
    if not agent_paths:
        return [f"{repo_root / 'agents'}: no agent files"]
    return [error for path in agent_paths for error in check_agent(path)]


def main() -> int:
    errors = validate(Path(__file__).resolve().parent.parent)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
