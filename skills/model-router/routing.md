# Routing table

`main` means the step stays in the main chat. A row marked "expert in lean mode" goes to router-expert while lean mode is on.

## Task types

| Task type | Tier | Check that confirms it |
|---|---|---|
| search | router-scout | every reported path and line exists |
| read-logs | router-scout | the quoted lines appear in the log |
| run-checks | router-scout | the command's exit code and output |
| routine-edit | router-worker | the named test, build or checker passes |
| mechanical-fix | router-worker | the linter, type-checker or build is clean |
| review | router-expert | each finding settled in the main chat with a test or a rerun |
| escalation | router-expert | the check from the original brief |
| design | main | none; judgement, expert in lean mode |
| hard-debug | main | the reproducing test passes; expert in lean mode |
| small-task | main | under five tool calls, not worth a brief |
| prose | main | voice and judgement do not survive a brief |

## engineer

| Step | Tier | Check that confirms it |
|---|---|---|
| Orient across many directories | router-scout | paths and lines exist |
| Plan and settle ambiguities | main | user approval |
| Phase work fully specified by the plan's test list | router-worker | the phase's tests and the full suite pass |
| Phase work needing a design decision | main | expert in lean mode |
| Commit, push, plan update | main | the pre-commit hook |
| Finish: independent review | router-expert | each finding settled with evidence, as engineer specifies |

## writing

| Step | Tier | Check that confirms it |
|---|---|---|
| Register, outline, draft and revise | main | the reader test in the writing skill |
| Run check.py on a draft and list its findings | router-scout | the checker's output |
| Find candidate sources | router-scout | verify.py confirms each one |
| Verify references and quotations | router-scout | verify.py output |

## latex

| Step | Tier | Check that confirms it |
|---|---|---|
| Fix build errors, warnings and overfull boxes | router-worker | a clean build and source lint |
| Locate an undefined reference or citation | router-scout | the file and line exist |
| Structure and house-style decisions | main | expert in lean mode |
| Final look at the rendered pages | main | visual judgement |

## web-ui-craft

| Step | Tier | Check that confirms it |
|---|---|---|
| Design brief and critique pass | main | expert in lean mode |
| Build components from the agreed brief | router-worker | build, type-check and tests pass |
| Accessibility or performance audit with tools | router-scout | the tool's report |
