"""Copy the router's files into a Claude Code configuration directory.

Run as `python scripts/install.py [--target DIR] [--dry-run]`. The target
defaults to `~/.claude`. The installer owns `agents/router-*.md` and the
`.md` and `.py` files in `skills/model-router/`: it writes those, removes
any it no longer ships, and leaves everything else in the target alone.

It also registers the router's hooks in the target's `settings.json`. It
owns every hook whose command points into `skills/model-router/`, replaces
those on each run, and keeps every other setting and hook. Refuses to
install, before writing anything, if validation fails or `settings.json`
cannot be read. If `settings.json` cannot be written once the files are
copied, it says so and exits with status 1; running again finishes the job.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from validate import SKILL_DIR, validate

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = Path.home() / ".claude"
AGENT_PATTERN = "router-*.md"
SKILL_SUFFIXES = frozenset({".md", ".py"})
SETTINGS_NAME = "settings.json"
PYTHON_PATH = Path(sys.executable).as_posix()
ROUTER_HOOK_MARKER = f"/{SKILL_DIR.as_posix()}/"
HOOK_TIMEOUT_SECONDS = 10
# (event, matcher or None for every tool, script in the skill directory)
ROUTER_HOOKS: tuple[tuple[str, str | None, str], ...] = (
    ("PreToolUse", "Agent", "spawn_hook.py"),
    ("PreToolUse", "Bash", "test_output_hook.py"),
    ("SubagentStop", None, "result_hook.py"),
)

HookGroup = dict[str, object]
HookEvents = dict[str, list[HookGroup]]


@dataclass(frozen=True, slots=True)
class InstallReport:
    copied: list[Path]
    removed: list[Path]


@dataclass(frozen=True, slots=True)
class Settings:
    document: dict[str, object]
    hooks: HookEvents


def owned_files(root: Path) -> set[Path]:
    """Owned paths under root, relative to it."""
    agents = (root / "agents").glob(AGENT_PATTERN)
    skill_dir = root / SKILL_DIR
    skill = skill_dir.iterdir() if skill_dir.is_dir() else iter(())
    skill_files = (p for p in skill if p.is_file() and p.suffix in SKILL_SUFFIXES)
    return {path.relative_to(root) for path in [*agents, *skill_files]}


def install(source_root: Path, target_root: Path, *, dry_run: bool) -> InstallReport:
    """Copy owned files to target_root and remove owned files no longer shipped."""
    shipped = owned_files(source_root)
    stale = owned_files(target_root) - shipped
    copied = [target_root / relative for relative in sorted(shipped)]
    removed = [target_root / relative for relative in sorted(stale)]
    if not dry_run:
        for relative, target in zip(sorted(shipped), copied, strict=True):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((source_root / relative).read_bytes())
        for target in removed:
            target.unlink()
    return InstallReport(copied=copied, removed=removed)


def parse_hook_events(value: object) -> HookEvents:
    if not isinstance(value, dict):
        raise ValueError(
            f'expected "hooks" to be an object, got {type(value).__name__}'
        )
    for event, groups in value.items():
        if not (isinstance(groups, list) and all(isinstance(g, dict) for g in groups)):
            raise ValueError(f'expected "hooks.{event}" to be a list of objects')
    return value


def read_settings(path: Path) -> Settings:
    """Parse settings.json; a missing or blank file is empty settings.

    Raises ValueError naming the file if it cannot be read as UTF-8 or is
    not a JSON object with a readable "hooks" object.
    """
    try:
        # utf-8-sig: Windows PowerShell writes a byte order mark JSON rejects.
        text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    except UnicodeDecodeError as error:
        raise ValueError(f"{path} is not UTF-8: {error}") from error
    except OSError as error:
        raise ValueError(f"{path} cannot be read: {error}") from error
    if not text.strip():
        return Settings(document={}, hooks={})
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise ValueError(
            f"{path}: expected a JSON object, got {type(document).__name__}"
        )
    try:
        hooks = parse_hook_events(document.get("hooks", {}))
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error
    return Settings(document=document, hooks=hooks)


def is_router_hook(hook: object) -> bool:
    command = hook.get("command") if isinstance(hook, dict) else None
    return isinstance(command, str) and ROUTER_HOOK_MARKER in command


def without_router_hooks(groups: list[HookGroup]) -> list[HookGroup]:
    """Groups with router hooks removed; a group left with no hooks is dropped."""
    kept_groups = []
    for group in groups:
        hooks = group.get("hooks")
        if not isinstance(hooks, list):
            kept_groups.append(group)
            continue
        kept = [hook for hook in hooks if not is_router_hook(hook)]
        if len(kept) == len(hooks):
            kept_groups.append(group)
        elif kept:
            kept_groups.append({**group, "hooks": kept})
    return kept_groups


def router_hook_groups(target_root: Path) -> list[tuple[str, HookGroup]]:
    groups: list[tuple[str, HookGroup]] = []
    for event, matcher, script in ROUTER_HOOKS:
        script_path = (target_root.resolve() / SKILL_DIR / script).as_posix()
        hook = {
            "type": "command",
            "command": f'"{PYTHON_PATH}" "{script_path}"',
            "timeout": HOOK_TIMEOUT_SECONDS,
        }
        matcher_field = {} if matcher is None else {"matcher": matcher}
        groups.append((event, {**matcher_field, "hooks": [hook]}))
    return groups


def with_router_hooks(hooks: HookEvents, target_root: Path) -> HookEvents:
    """hooks with every router hook replaced by the current set."""
    merged: HookEvents = {}
    for event, groups in hooks.items():
        kept = without_router_hooks(groups)
        # An event the user left empty stays, so an untouched file compares
        # equal and is not rewritten.
        held_only_router_hooks = bool(groups) and not kept
        if not held_only_router_hooks:
            merged[event] = kept
    for event, group in router_hook_groups(target_root):
        merged.setdefault(event, []).append(group)
    return merged


def write_settings(path: Path, document: dict[str, object]) -> None:
    """Write through a temporary file, so a failed write leaves the old file."""
    temporary = path.with_name(f"{path.name}.tmp")
    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def register_hooks(target_root: Path, settings: Settings, *, dry_run: bool) -> str:
    """Merge the router hooks into settings.json and say what happened to it."""
    path = target_root / SETTINGS_NAME
    hooks = with_router_hooks(settings.hooks, target_root)
    if hooks == settings.hooks:
        return f"Unchanged {path}"
    if dry_run:
        return f"Would update {path}"
    write_settings(path, {**settings.document, "hooks": hooks})
    return f"Updated {path}"


def run(source_root: Path, target_root: Path, *, dry_run: bool) -> int:
    errors = validate(source_root)
    if errors:
        print("Not installed. Validation failed:")
        for error in errors:
            print(f"  {error}")
        return 1
    try:
        settings = read_settings(target_root / SETTINGS_NAME)
    except ValueError as error:
        print(f"Not installed. {error}")
        return 1
    report = install(source_root, target_root, dry_run=dry_run)
    copy_verb, remove_verb = (
        ("Would copy", "Would remove") if dry_run else ("Copied", "Removed")
    )
    for target in report.copied:
        print(f"{copy_verb} {target}")
    for target in report.removed:
        print(f"{remove_verb} {target}")
    try:
        print(register_hooks(target_root, settings, dry_run=dry_run))
    except OSError as error:
        path = target_root / SETTINGS_NAME
        print(f"Hooks not registered. {path} cannot be written: {error}")
        return 1
    return 0


def main() -> int:  # pragma: no cover: argument parsing over tested run()
    parser = argparse.ArgumentParser(description="Install the model router.")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    return run(REPO_ROOT, arguments.target, dry_run=arguments.dry_run)


if __name__ == "__main__":  # pragma: no cover: argument parsing over tested run()
    sys.exit(main())
