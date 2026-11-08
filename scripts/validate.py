"""Check the router's agents, skill and routing table before installing.

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
SKILL_DIR = Path("skills") / "model-router"
INLINE_TIER = "main"
TIER_HEADER = "Tier"
# Claude Code truncates description plus when_to_use at this length in the
# skill listing, which can cut off the text that triggers the skill.
MAX_LISTING_CHARACTERS = 1536


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


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def routing_tiers(text: str) -> list[str]:
    """Return the Tier cell of every row in every table with a Tier column."""
    tiers: list[str] = []
    tier_column: int | None = None
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            tier_column = None
            continue
        cells = table_cells(line)
        if tier_column is None:
            tier_column = cells.index(TIER_HEADER) if TIER_HEADER in cells else -1
        elif tier_column >= 0 and not set("".join(cells)) <= set("-: "):
            tiers.append(cells[tier_column])
    return tiers


def check_skill(skill_dir: Path, agent_names: set[str]) -> list[str]:
    errors = []
    skill_path = skill_dir / "SKILL.md"
    fields = read_frontmatter(skill_path.read_text(encoding="utf-8"))
    if fields is None:
        errors.append(f"{skill_path}: no frontmatter block")
    else:
        listing = fields.get("description", "") + fields.get("when_to_use", "")
        if len(listing) > MAX_LISTING_CHARACTERS:
            errors.append(
                f"{skill_path}: description is {len(listing)} characters, "
                f"over the {MAX_LISTING_CHARACTERS} shown in the skill listing"
            )
    routing_path = skill_dir / "routing.md"
    tiers = routing_tiers(routing_path.read_text(encoding="utf-8"))
    if not tiers:
        errors.append(f"{routing_path}: no routing rows with a {TIER_HEADER} column")
    known = agent_names | {INLINE_TIER}
    errors.extend(
        f"{routing_path}: unknown tier '{tier}', expected one of {sorted(known)}"
        for tier in tiers
        if tier not in known
    )
    return errors


def validate(repo_root: Path) -> list[str]:
    agent_paths = sorted((repo_root / "agents").glob("*.md"))
    if not agent_paths:
        return [f"{repo_root / 'agents'}: no agent files"]
    errors = [error for path in agent_paths for error in check_agent(path)]
    skill_dir = repo_root / SKILL_DIR
    if skill_dir.is_dir():
        errors.extend(check_skill(skill_dir, {path.stem for path in agent_paths}))
    return errors


def main() -> int:
    errors = validate(Path(__file__).resolve().parent.parent)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
