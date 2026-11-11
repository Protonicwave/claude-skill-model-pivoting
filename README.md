# model-router

A Claude Code skill that sends delegable work to subagents on fixed models and effort levels, so the main chat keeps one model and its prompt cache stays warm.

- `agents/`: the three tiers. `router-scout` (haiku, low effort), `router-worker` (sonnet, medium), `router-expert` (opus, high). Each lists its tools, because an agent without a `tools` line receives every tool in the session and starts with a far larger prompt; the validator rejects an agent without one. The scout is told never to edit, but it has Bash, so that rule rests on its instructions rather than its tools.
- `skills/model-router/SKILL.md`: when to delegate, the brief template, how to accept or escalate a result, and lean mode.
- `skills/model-router/routing.md`: which tier handles each task type normally and in lean mode, with tables for the engineer, writing, latex and web-ui-craft skills.
- `skills/model-router/router_log.py`: the routed-step log the result hook writes and the report summarises.
- `skills/model-router/spawn_hook.py`: a PreToolUse hook that runs a general-purpose subagent spawned without a model on sonnet, instead of the main chat's model. Named agents, forks and explicit models are left alone.
- `skills/model-router/test_output_hook.py`: a PreToolUse hook that adds the quiet flag to a bare `pytest`, `python -m pytest`, `cargo test` or `npm test` command, so passing tests do not fill the main chat's context. A command with a pipe, `&&`, redirection, an expansion or its own verbosity flag is left alone.
- `skills/model-router/result_hook.py`: a SubagentStop hook that logs each router subagent's step from the brief's `Task type:` line and the reply's `Result:` line.
- `skills/model-router/usage_report.py`: reads the transcripts under `~/.claude/projects` and reports where the spend went.

## Install

Requires Python 3.12 or later and no third-party packages.

```
python scripts/install.py --dry-run
python scripts/install.py
```

The installer validates every file first, then copies the agents to `~/.claude/agents` and the skill to `~/.claude/skills/model-router`. Pass `--target DIR` to install elsewhere. It owns `agents/router-*.md` and the `.md` and `.py` files in `skills/model-router/`, and removes any of those the repository no longer ships. Everything else in the target is left alone.

It also registers the three hooks in `~/.claude/settings.json`, running them with the Python that ran the installer. It owns every hook whose command points into `skills/model-router/` and replaces those on each run; other settings and hooks are kept. If `settings.json` cannot be read as UTF-8 JSON, nothing is installed and the reason is printed. If it cannot be written after the files are copied, the installer says so and exits with status 1, and running it again finishes the job. The file is rewritten with two-space indentation when the hooks change.

Install with no Claude Code session open: a session that changes its settings while the installer writes `settings.json` can lose one of the two changes. To uninstall, remove the three hook entries from `settings.json` before deleting the files. A hook whose script is missing makes Python exit with status 2, which Claude Code treats as a block, so every `Agent` and `Bash` call would be refused.

## Use

- Lean mode: ask for it, then run `/effort medium`. Run `/effort` with your usual level to end it.
- Spend and routing results: `python ~/.claude/skills/model-router/usage_report.py [--since YYYY-MM-DD]`. It prints spend per source (the main chat or an agent type) and model, unrouted spawns, main-chat prompt size deciles, cache misses over 50k tokens, five-hour blocks, the median first-turn context per agent type, and the routed results. Figures are list-price equivalents from the dated `PRICES` table in the script, not a bill; models it does not list are shown as unpriced tokens. A task type that fails on its tier more than about one time in four should move up a tier in `routing.md`; reinstall afterwards.
- To change a tier's model or effort, edit the `model` or `effort` line in its file under `agents/` and reinstall.

## Test

```
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
```
