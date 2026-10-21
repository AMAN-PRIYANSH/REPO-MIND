# Claude Code - Round 1 prompt (Milestone 1)

Copy everything below the line into Claude Code, opened in a local clone of `AMAN-PRIYANSH/REPO-MIND`.

---

You are implementing **Milestone 1** of VulnTrace AI in this repository. Milestone 1 only. Stop when it is done.

## 1. Read before changing anything

1. Run `git status`, `git branch -a` and `git log --oneline -10`. Report what you see.
2. Read these files fully before writing code:
   - `README.md`
   - `docs/PROJECT_DEFINITION.md`
   - `docs/research/FEASIBILITY_FINDINGS.md`
   - `docs/architecture/SYSTEM_ARCHITECTURE.md`
   - `docs/design/DATA_MODEL.md`
   - `docs/design/INTERFACES_AND_CONTRACTS.md` (sections 1 and 3)
   - `docs/design/PROJECT_STRUCTURE.md`
   - `docs/testing/TESTING_STRATEGY.md`
   - `docs/implementation/MILESTONE_1.md` (this is your specification)
   - `docs/decisions/ARCHITECTURE_DECISIONS.md`
   - `docs/decisions/RISKS_AND_OPEN_QUESTIONS.md`
3. If the repository contents differ from what these documents describe (for example, files already exist that the design does not mention), stop and ask before continuing.

## 2. Check the environment and report it honestly

Before writing code, run and report the output of:

- the Python version
- `go version`
- `go env GOOS GOARCH GOVERSION`
- `git --version`
- the operating system

Do not assume any tool, package, network resource, API or credential is available. If something needed is missing:

- Python packages `pytest` and `jsonschema` may be installed into a project virtual environment. Report the commands you used.
- Do **not** install Go, change system settings, or install anything system-wide. If Go is missing, continue with the parts that do not need it, and report Go as a blocker for the integration criteria.
- Do not use any network access during tests or scoring. Fixture builds must run with `GOPROXY=off`.

## 3. Git safety rules

- Create a new branch for this work: `milestone-1/ground-truth-linker`, based on the branch that contains the design documents. Never commit directly to `main`.
- Commit in small, logically separate commits with clear messages.
- Never force-push, rebase shared branches, rewrite history, delete branches, or run `git reset --hard` / `git clean -fd` on files you did not create.
- Never commit secrets, API keys, `.env` files, virtual environments, caches, or built binaries. Add them to `.gitignore` first.
- Do not modify, move or delete the design documents, except to add `docs/results/M1_LINKER_RESULTS.md` and to fix a clear factual error, which you must list in your report.
- Push the branch only if push access is configured and works. If pushing fails, report it; do not try workarounds that change credentials or remotes.

## 4. What to implement

Implement exactly the deliverables in `docs/implementation/MILESTONE_1.md`:

1. Python package skeleton (`pyproject.toml`, `src/vulntrace/`, `tests/`, `.gitignore`).
2. `python -m vulntrace doctor`.
3. `schemas/fixture_manifest.schema.json` and `schemas/method_result.schema.json`.
4. The fixture suite under `fixtures/reachability/`, including the five mandatory cases from feasibility trial 3 and the inlining case, at least 12 cases in total, and `manifest.json` with truth and rationale for each.
5. The linker-presence method.
6. `python -m vulntrace fixtures score --method linker`.
7. Unit and integration tests as specified.
8. `docs/results/M1_LINKER_RESULTS.md` containing only results you actually observed.

Follow the interfaces, schemas, build flags, environment variables and symbol-matching rules in the design documents. If you believe a design detail is wrong or unworkable, do not silently change it: implement the closest faithful version, and list the problem and your proposed change under "Design deviations" in your report.

## 5. Do not do these things

- Do not start Milestone 2 or later work: no Go call-graph helper, no `golang.org/x/tools`, no verdict engine, no vulndb or advisory code, no git fetching of other repositories, no LLM calls, no embeddings, retrieval, agents, database, API server or UI.
- Do not add dependencies beyond `pytest` and `jsonschema` without a written reason in the report.
- Do not refactor or reorganise anything outside the Milestone 1 scope.
- Do not change a fixture's `truth` to make a result match. If a fixture's truth was genuinely wrong, explain why in the report.
- Do not edit tests to hide a failure.

## 6. Honesty rules (most important)

- Never say a test, command, tool, build, integration or experiment succeeded unless you ran it in this session and saw the result.
- When reporting test results, paste the actual summary lines printed by the tool (for example, the final pytest line with passed/failed/skipped counts).
- If something was skipped, blocked or not attempted, say so plainly, with the reason.
- Distinguish clearly between what you observed and what you expect or assume.
- If a result contradicts the feasibility findings (for example, one of the five trial-3 cases behaves differently on this machine), report it as a finding. Do not "fix" it by changing the fixture or the test.

## 7. Run these before finishing

Run, and report the exact command and the printed outcome of each:

1. `python -m pytest tests/unit`
2. `python -m pytest tests/integration` (expected to skip with a clear message if Go is missing)
3. `python -m vulntrace doctor`
4. `python -m vulntrace fixtures score --method linker` twice, and confirm the results are identical apart from timing
5. `git status` and `git log --oneline` for your branch

## 8. Final report format

End with a report containing these sections, in this order:

1. **Environment** - OS, Python, Go, git versions as printed.
2. **Files changed** - every file added or modified, one line each, with its purpose.
3. **What was implemented** - mapped to the Milestone 1 deliverables (1 to 8).
4. **Test evidence** - each command from section 7 with its printed result.
5. **Acceptance criteria** - the 10 criteria from `MILESTONE_1.md`, each marked Met / Not met / Could not verify, with the evidence for each.
6. **Fixture results** - the per-case table (category, truth, observed linker result), with every mismatch explained.
7. **Design deviations** - anything you did differently from the documents, and why.
8. **Blockers and limitations** - missing tools, failed operations, unverified behaviour (for example, Windows `nm` output if not tested).
9. **Open issues and suggestions for Milestone 2** - short list; do not implement them.
10. **Git** - branch name, commit list, and whether the branch was pushed.

Then stop. Do not begin Milestone 2. Wait for the project owner's explicit approval.
