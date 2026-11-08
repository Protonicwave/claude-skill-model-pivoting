"""Copy the router's files into a Claude Code configuration directory.

Run as `python scripts/install.py [--target DIR] [--dry-run]`. The target
defaults to `~/.claude`. Only files this repository owns are written;
anything else in the target is left alone. Refuses to install if
validation fails.
"""

import argparse
import shutil
import sys
from pathlib import Path

from validate import SKILL_DIR, validate

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = Path.home() / ".claude"


def owned_files(source_root: Path) -> list[Path]:
    """Paths, relative to the repository root, that the installer copies."""
    agents = (source_root / "agents").glob("*.md")
    skill = (path for path in (source_root / SKILL_DIR).iterdir() if path.is_file())
    return sorted(path.relative_to(source_root) for path in [*agents, *skill])


def install(source_root: Path, target_root: Path, *, dry_run: bool) -> list[Path]:
    """Copy every owned file into target_root and return the target paths."""
    targets = []
    for relative in owned_files(source_root):
        target = target_root / relative
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_root / relative, target)
        targets.append(target)
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()

    errors = validate(REPO_ROOT)
    if errors:
        print("Not installed. Validation failed:")
        for error in errors:
            print(f"  {error}")
        return 1

    prefix = "Would copy" if arguments.dry_run else "Copied"
    for target in install(REPO_ROOT, arguments.target, dry_run=arguments.dry_run):
        print(f"{prefix} {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
