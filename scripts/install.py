"""Copy the router's files into a Claude Code configuration directory.

Run as `python scripts/install.py [--target DIR] [--dry-run]`. The target
defaults to `~/.claude`. The installer owns `agents/router-*.md` and the
`.md` and `.py` files in `skills/model-router/`: it writes those, removes
any it no longer ships, and leaves everything else in the target alone.
Refuses to install if validation fails.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from validate import SKILL_DIR, validate

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = Path.home() / ".claude"
AGENT_PATTERN = "router-*.md"
SKILL_SUFFIXES = frozenset({".md", ".py"})


@dataclass(frozen=True, slots=True)
class InstallReport:
    copied: list[Path]
    removed: list[Path]


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


def run(source_root: Path, target_root: Path, *, dry_run: bool) -> int:
    errors = validate(source_root)
    if errors:
        print("Not installed. Validation failed:")
        for error in errors:
            print(f"  {error}")
        return 1
    report = install(source_root, target_root, dry_run=dry_run)
    copy_verb, remove_verb = (
        ("Would copy", "Would remove") if dry_run else ("Copied", "Removed")
    )
    for target in report.copied:
        print(f"{copy_verb} {target}")
    for target in report.removed:
        print(f"{remove_verb} {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the model router.")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    return run(REPO_ROOT, arguments.target, dry_run=arguments.dry_run)


if __name__ == "__main__":  # pragma: no cover: argument parsing over tested run()
    sys.exit(main())
