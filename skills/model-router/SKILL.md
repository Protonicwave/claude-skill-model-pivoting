---
name: model-router
description: Decides which model and effort level runs each step of a task, by keeping the step in the main chat or handing it to the router-scout, router-worker or router-expert subagent. Use whenever a task has a step worth delegating (searching, reading logs, running checks, routine edits with tests, review, hard debugging), when another skill's process reaches such a step, and when the user mentions lean mode, token use or routing.
---

# Model router

The aim is to spend fewer tokens with no loss of quality. Two facts drive every rule here:

- The main chat re-reads its whole history every turn, and the prompt cache makes that cheap. Each model has its own cache, so a model switch makes the next turn pay full price for the whole history. An effort change keeps the cache.
- A subagent starts with an empty context and its own cache. A short brief to it costs little and never disturbs the main chat's cache.

So the main chat keeps one model for the whole session, and work moves between models by delegation, never by `/model`. If the user wants to change the main model anyway, tell them to run `/compact` first so the new model reads a summary instead of the history.

## Decide

Delegate a step only when all three hold:

1. `routing.md` assigns its task type to a subagent tier, or the active skill's split in `routing.md` does.
2. A check can confirm the result without trusting the subagent: a test, build, linter, checker, exact file and line, or, for a review, findings the main chat will verify.
3. The work is much larger than the brief. As a rule of thumb, a step the main chat would finish in under five tool calls stays in the main chat.

Otherwise do the step in the main chat. When unsure between two tiers, pick the higher one: overpaying costs the price difference, while a failed cheap attempt costs both runs.

Never run two subagents that edit the same files at once. Commits, pushes, branch changes and plan updates stay in the main chat.

## Brief

Every brief uses this template, with no section left out:

```
Goal: one sentence on what is true when the step is done.
Skill: the skill to load first, or "none".
Read: the files and line ranges to read. Point at files rather than summarising them.
Change: what may be edited, or "nothing".
Done when: the exact check command, or the exact thing to find.
Constraints: rules that apply beyond the skill, such as files not to touch.
Ruled out: what has already been tried or excluded, with the evidence.
```

Leave out the main chat's reasoning about why the code is the way it is, especially for a review. A reviewer who knows the reasons accepts the code.

## Accept or escalate

Each subagent replies with `Result`, `Evidence` and `Notes`.

- Accept `done` only when Evidence shows the check passing. When the check is one cheap command, rerun it in the main chat before accepting.
- On `failed`, `blocked`, or `done` without evidence, escalate once: router-scout to router-worker, router-worker to router-expert. The new brief includes the previous Evidence under "Ruled out".
- When router-expert fails, stop routing. Take the step into the main chat and tell the user what was tried.

Never escalate twice for the same step.

## Log

After every routed step, including each escalation, record it:

```
python ~/.claude/skills/model-router/router_log.py add <task-type> <tier> <done|failed|blocked>
```

`<task-type>` is the first column of the matching row in `routing.md`. Do not log steps kept in the main chat.

When the user asks how routing is going, run `python ~/.claude/skills/model-router/router_log.py summary` and point out any task type that fails on its tier more than about one time in four. That row should move up a tier in `routing.md`.

## Other skills

A domain skill (engineer, writing, latex, web-ui-craft or any other) decides how the work is done. This skill decides only which model does each step. Name the domain skill in the brief's Skill line so the subagent loads and follows it. `routing.md` lists each skill's split.

## Lean mode

When the user asks for lean mode, tell them to run `/effort medium`. The model cannot change its own effort, and an effort change keeps the cache. While lean mode is on, the steps in `routing.md` marked "expert in lean mode" go to router-expert instead of staying in the main chat. When the user ends lean mode, tell them to run `/effort` with their usual level.
