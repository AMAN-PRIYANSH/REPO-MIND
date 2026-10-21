# Session wrapper prompt

Paste everything below the line into Claude Code at the start of **every** session, including sessions that continue after a usage-limit stop. You do not need to change anything in it; it reads the current checkpoint from the repository.

Recommended model and effort are listed in the current checkpoint's specification (top of the file). Set them before pasting, with `/model ...` and `/effort ...`.

---

You are continuing the VulnTrace AI build in this repository.

Follow `CLAUDE.md` exactly. Then:

1. Read `docs/progress/STATUS.md`. Identify the current checkpoint, its state, and its branch.
2. If the state is `AWAITING_REVIEW`, `APPROVED` or `NOT_RELEASED`, do nothing except report the state and stop. Work is only allowed when the state is `READY`, `IN_PROGRESS` or `CHANGES_REQUESTED`.
3. Read the checkpoint specification in `docs/implementation/checkpoints/`, and the documents it lists as required reading. If the state is `CHANGES_REQUESTED`, read the review notes at the end of that specification first.
4. Check out the checkpoint branch (create it from `main` if it does not exist). Set the state to `IN_PROGRESS` in STATUS.md, copy the deliverables into the task list there, commit, and push.
5. Check the environment before writing code: OS, Python, Go, git, Docker, and whether the network can reach what the checkpoint needs. Record the output in your report. Do not install anything system-wide. Project-local Python packages in a virtual environment are fine if the checkpoint allows them.
6. Do the work in small steps. After each completed deliverable: run its tests, commit, push, tick it in STATUS.md.
7. If you approach your usage limit, follow section 6 of `CLAUDE.md` and stop cleanly.
8. When all acceptance criteria are met or blocked, write `docs/progress/reports/CPn_REPORT.md` in the format below, set the state to `AWAITING_REVIEW`, commit, push, and stop.

Never start the next checkpoint. Never claim a result you did not observe.

## Report format (`docs/progress/reports/CPn_REPORT.md`)

1. **Environment** - OS, Python, Go, git, Docker versions as printed; network checks.
2. **Files changed** - every file added or modified, one line each, with its purpose.
3. **Deliverables** - each deliverable from the specification: done / partly done / not done.
4. **Test evidence** - each command run, with the printed summary line.
5. **Acceptance criteria** - each criterion: Met / Not met / Could not verify, with evidence.
6. **Results** - tables produced by code (copy from the generated result files), if the checkpoint produces results.
7. **Design deviations** - anything done differently from the documents, and why.
8. **Blockers and limitations** - missing tools, failed operations, unverified behaviour.
9. **Suggestions for the next checkpoint** - short list; do not implement them.
10. **Git** - branch, commit list (`git log --oneline` for the branch), and whether each push succeeded.
