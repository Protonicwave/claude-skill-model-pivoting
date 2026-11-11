"""Check the router's agents, skill and routing table before installing."""

import re
from pathlib import Path

MODEL_ALIASES = frozenset({"haiku", "sonnet", "opus", "fable", "inherit"})
MODEL_ID_PATTERN = re.compile(r"claude-[a-z0-9-]+")
EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})
# Without `tools` an agent receives every tool the session has, and the tool
# definitions alone more than double its first prompt.
REQUIRED_AGENT_FIELDS = ("name", "description", "model", "effort", "tools")
TOOL_LIST_SEPARATOR = ","
# Claude Code ignores a tool name it does not recognise, so a lower-case or
# space-separated entry silently removes the tool rather than failing.
TOOL_NAME_PATTERN = re.compile(r"[A-Z][A-Za-z]*|mcp__[A-Za-z0-9_-]+")
FRONTMATTER_DELIMITER = "---"
MAX_FRONTMATTER_LINES = 50
# YAML block scalar markers: the value continues on later lines, which the
# flat reader below does not follow.
MULTI_LINE_MARKERS = frozenset({">", "|", ">-", "|-"})
SKILL_DIR = Path("skills") / "model-router"
INLINE_TIER = "main"
# The result hook logs a routed step only when the brief carries this label.
TASK_TYPE_LABEL = "Task type:"
TIER_HEADERS = frozenset({"Tier", "Lean tier"})
TASK_TYPE_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
# Claude Code truncates the description at this length in the skill listing,
# which can cut off the text that triggers the skill.
MAX_LISTING_CHARACTERS = 1536


def read_frontmatter(text: str) -> dict[str, str] | None:
    """Return the `key: value` pairs between the opening `---` lines.

    Values are single-line; surrounding quotes are removed. Returns None
    when the text does not open with a frontmatter block closed within
    MAX_FRONTMATTER_LINES lines.
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
            fields[key.strip()] = value.strip().strip("\"'")
    return None


def check_frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    fields = read_frontmatter(path.read_text(encoding="utf-8"))
    if fields is None:
        return {}, [f"{path}: no frontmatter block"]
    errors = [
        f"{path}: multi-line value for '{key}' is not supported, use one line"
        for key, value in fields.items()
        if value in MULTI_LINE_MARKERS
    ]
    return fields, errors


def is_known_model(model: str) -> bool:
    return model in MODEL_ALIASES or MODEL_ID_PATTERN.fullmatch(model) is not None


def check_agent(path: Path) -> list[str]:
    fields, errors = check_frontmatter(path)
    if not fields:
        return errors
    errors.extend(
        f"{path}: missing field '{field}'"
        for field in REQUIRED_AGENT_FIELDS
        if not fields.get(field)
    )
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
    errors.extend(check_tools(path, fields.get("tools", "")))
    return errors


def check_tools(path: Path, tools: str) -> list[str]:
    if not tools:
        return []  # reported as a missing field
    return [
        f"{path}: tool '{tool}' is not a tool name such as Read or mcp__server__tool"
        for tool in (entry.strip() for entry in tools.split(TOOL_LIST_SEPARATOR))
        if TOOL_NAME_PATTERN.fullmatch(tool) is None
    ]


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_separator(cells: list[str]) -> bool:
    return set("".join(cells)) <= set("-: ")


def check_routing_row(
    cells: list[str], header: list[str], known: set[str]
) -> list[str]:
    if len(cells) != len(header):
        row = " | ".join(cells)
        return [f"row '{row}' has {len(cells)} cells, expected {len(header)}"]
    errors = []
    if TASK_TYPE_PATTERN.fullmatch(cells[0]) is None:
        errors.append(
            f"task type '{cells[0]}' is not lower-case words joined by hyphens"
        )
    errors.extend(
        f"unknown tier '{cell}' in row '{cells[0]}', expected one of {sorted(known)}"
        for column, cell in zip(header, cells, strict=True)
        if column in TIER_HEADERS and cell not in known
    )
    return errors


def check_routing(text: str, known: set[str]) -> tuple[int, list[str]]:
    """Check every row of every table with a tier column; return (rows, errors)."""
    rows = 0
    errors: list[str] = []
    header: list[str] | None = None
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            header = None
            continue
        cells = table_cells(line)
        if header is None:
            header = cells
        elif TIER_HEADERS & set(header) and not is_separator(cells):
            rows += 1
            errors.extend(check_routing_row(cells, header, known))
    return rows, errors


def check_skill(skill_dir: Path, agent_names: set[str]) -> list[str]:
    skill_path = skill_dir / "SKILL.md"
    routing_path = skill_dir / "routing.md"
    missing = [path for path in (skill_path, routing_path) if not path.is_file()]
    if missing:
        return [f"{path}: missing" for path in missing]
    fields, errors = check_frontmatter(skill_path)
    skill_lines = skill_path.read_text(encoding="utf-8").splitlines()
    if not any(line.lstrip().startswith(TASK_TYPE_LABEL) for line in skill_lines):
        errors.append(
            f"{skill_path}: brief template has no '{TASK_TYPE_LABEL}' line, "
            "so the result hook cannot log routed steps"
        )
    description = fields.get("description", "")
    if len(description) > MAX_LISTING_CHARACTERS:
        errors.append(
            f"{skill_path}: description is {len(description)} characters, "
            f"over the {MAX_LISTING_CHARACTERS} shown in the skill listing"
        )
    rows, routing_errors = check_routing(
        routing_path.read_text(encoding="utf-8"), agent_names | {INLINE_TIER}
    )
    if rows == 0:
        errors.append(f"{routing_path}: no routing rows with a tier column")
    errors.extend(f"{routing_path}: {error}" for error in routing_errors)
    return errors


def validate(repo_root: Path) -> list[str]:
    agent_paths = sorted((repo_root / "agents").glob("*.md"))
    errors = [error for path in agent_paths for error in check_agent(path)]
    if not agent_paths:
        errors.append(f"{repo_root / 'agents'}: no agent files")
    agent_names = {path.stem for path in agent_paths}
    errors.extend(check_skill(repo_root / SKILL_DIR, agent_names))
    return errors
