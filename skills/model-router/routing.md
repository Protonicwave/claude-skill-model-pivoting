# Routing table

`Tier` applies normally and `Lean tier` while lean mode is on. `main` means the step stays in the main chat. The first column is the task type to log.

When a skill's table below covers the step, it takes precedence over the general table.

## General

| Task type | Tier | Lean tier | Check that confirms it |
|---|---|---|---|
| search | router-scout | router-scout | every reported path and line exists |
| read-logs | router-scout | router-scout | the quoted lines appear in the log |
| run-checks | router-scout | router-scout | the command's exit code and output |
| routine-edit | router-worker | router-worker | the named test, build or checker passes |
| mechanical-fix | router-worker | router-worker | the linter, type-checker or build is clean |
| web-research | router-worker | router-worker | each quoted passage appears at its cited URL |
| review | router-expert | router-expert | each finding settled in the main chat with a test or a rerun |
| design | main | router-expert | the main chat reviews the proposal before acting on it |
| hard-debug | main | router-expert | a reproducing test that now passes |
| prose | main | main | the writing skill's own checks |

## engineer

| Task type | Tier | Lean tier | Check that confirms it |
|---|---|---|---|
| engineer-orient | router-scout | router-scout | every reported path and line exists |
| engineer-plan | main | main | the user approves the plan |
| engineer-phase-specified | router-worker | router-worker | the phase's tests and the full suite pass |
| engineer-phase-design | main | router-expert | the phase's tests and the full suite pass |
| engineer-commit | main | main | the pre-commit hook passes |
| engineer-review | router-expert | router-expert | each finding settled with evidence, as engineer specifies |

`engineer-phase-specified` is phase work the plan's test list fully specifies. Phase work that needs a design decision is `engineer-phase-design`.

## writing

| Task type | Tier | Lean tier | Check that confirms it |
|---|---|---|---|
| writing-draft | main | main | the reader test in the writing skill |
| writing-check | router-scout | router-scout | the output of check.py |
| writing-find-sources | router-worker | router-worker | verify.py confirms each source |
| writing-verify | router-scout | router-scout | the output of verify.py |
| writing-claim-support | router-worker | router-worker | each verdict other than supported quotes the claim's words, settled in the main chat against the quote |
| writing-cold-read | router-worker | router-worker | each reported passage is quoted word for word from the draft, settled in the main chat |
| writing-examiner | router-expert | router-expert | each band quotes the rubric and the draft word for word, settled in the main chat |

`writing-find-sources` searches the web, which router-scout cannot. The three review passes start the subagent without the writing skill, so it reads the draft as its reader or examiner would.

## latex

| Task type | Tier | Lean tier | Check that confirms it |
|---|---|---|---|
| latex-fix-build | router-worker | router-worker | a clean build and source lint |
| latex-locate | router-scout | router-scout | the file and line exist |
| latex-structure | main | router-expert | the main chat reviews the proposal before acting on it |
| latex-final-look | main | main | the main chat views the rendered pages |

## web-ui-craft

| Task type | Tier | Lean tier | Check that confirms it |
|---|---|---|---|
| ui-design | main | router-expert | the main chat reviews the brief or critique before acting on it |
| ui-build | router-worker | router-worker | build, type-check and tests pass |
| ui-audit | router-scout | router-scout | the audit tool's report |
