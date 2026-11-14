# CP8 report: final report, README and interview notes

Branch: `claude/vulntrace-ai-build-5f8jgi`. No model was run, no Colab, no new experiment, no change to code behaviour, verdict rules, prompts or existing result files.

## 1. Environment

Printed by the commands, in this session's sandbox:

| Item | Output |
|---|---|
| OS | `Linux vm 6.18.44-fc-v470 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 x86_64 GNU/Linux` |
| Python | `Python 3.13.18` (project venv `.venv`, created with `pip install -e ".[dev,agent]"`; project-local, nothing system-wide) |
| Go | `go version go1.24.7 linux/amd64` |
| git | `git version 2.43.0` |
| Docker | `Docker version 29.9.2, build a82e528` client; the daemon is not reachable (`failed to connect to the docker API at unix:///var/run/docker.sock`), so no container was started and the pgvector tests skip locally |

Network: outbound HTTPS works through the agent proxy (the venv install and `git push` succeeded). `go` module downloads were not needed: `helper fetch` printed `helper modules downloaded` instantly because the module cache was already populated, so **the one network step of the quickstart was not exercised from an empty cache in this session**; the triage then ran with `GOPROXY=off`. CP8 itself needs nothing beyond GitHub.

## 2. Files changed (`git diff --stat origin/main..HEAD`, plus this report)

| File | Purpose |
|---|---|
| `src/vulntrace/eval/summary.py` (new) | Results summary generator: builds `summary.json` / `SUMMARY.md` and the README key-results table from committed result files, reusing the existing statistics code |
| `src/vulntrace/__main__.py` | Adds the `results summary [--check] [--root]` subcommand (8 lines; no existing behaviour touched) |
| `docs/results/summary.json`, `docs/results/SUMMARY.md` (new) | Generated headline numbers, one table per experiment, each row linking its source; sha256 of every file read |
| `README.md` | Rewritten for a reader: what/how (Mermaid)/key results (generated table)/what did not work/offline quickstart/zero cost/map/licence status |
| `docs/FINAL_REPORT.md` (new) | Final report |
| `docs/DEVELOPMENT.md` (new) | The pre-CP8 README's evaluation/development command list, moved unchanged |
| `docs/INTERVIEW_NOTES.md` (new) | Pitch and 15 questions with evidence links |
| `tests/unit/test_cp8_summary.py`, `tests/unit/test_cp8_docs.py` (new) | Regeneration, source-hash, cross-check against results documents, number, pair/interval, link and wording-limit tests |
| `docs/PROJECT_DEFINITION.md`, `docs/architecture/DATA_FLOW.md`, `docs/architecture/SYSTEM_ARCHITECTURE.md`, `docs/decisions/ARCHITECTURE_DECISIONS.md`, `docs/decisions/RISKS_AND_OPEN_QUESTIONS.md`, `docs/design/PROJECT_STRUCTURE.md`, `docs/evaluation/DATASET_STRATEGY.md`, `docs/evaluation/EVALUATION_PLAN.md`, `docs/research/FEASIBILITY_FINDINGS.md`, `docs/testing/TESTING_STRATEGY.md` | Short "CP8 note / superseded" lines only; design history kept |
| `docs/progress/STATUS.md`, `docs/progress/reports/CP8_REPORT.md` | Ledger and this report |

`git diff origin/main..HEAD -- src helper schemas` shows only `__main__.py` and the new `summary.py`; no file under `docs/results/` other than the two new generated files changed; no prompt, verdict rule or fixture was touched.

## 3. Deliverables

| # | Deliverable | State |
|---|---|---|
| 1 | Results summary generator, `SUMMARY.md`, `summary.json`, regeneration test | Done. Covers datasets, CP4, CP5 (E1, S1, HyDE), CP5b, CP6, CP7 (fixtures, D1/D4 distributions), CP7b; every row names its source file(s) |
| 2 | README | Done. The key-results table is generated (markers in README) and compared exactly by a test |
| 3 | Final report | Done |
| 4 | Interview notes | Done (15 questions; contains a bracketed placeholder asking the owner to add, in their own words, what they decided and reviewed themselves; I cannot know that) |
| 5 | Housekeeping | Done as notes (section 7). `SUPERVISOR_HANDOFF.md` not touched |
| 6 | Tests | Done (section 4); CI green on the last code commit (section 5) |

## 4. Test evidence

| Command | Printed summary |
|---|---|
| `.venv/bin/python -m pytest tests/unit tests/contract -q` (before any change) | `849 passed, 10 skipped in 15.48s` |
| same, after all changes | `887 passed, 10 skipped in 14.02s` (38 new tests; the 10 skips are 9 pgvector tests needing `psycopg`, not installed locally, and one "only enforced in CI") |
| `cd helper && GOTOOLCHAIN=local CGO_ENABLED=0 GOPROXY=off go test ./...` | `ok  	vulntrace/helper	3.827s` |
| `.venv/bin/python -m pytest tests/integration -q` | `134 passed, 2 skipped in 190.74s (0:03:10)` (2 skips: opt-in network smoke tests) |
| `.venv/bin/python -m vulntrace results summary --check` | `summary files are up to date` |
| in a fresh clone of the pushed branch (fresh venv): the same `--check`, plus `pytest tests/unit/test_cp8_summary.py tests/unit/test_cp8_docs.py -q` | `summary files are up to date`; `38 passed in 2.56s` |

Quickstart in the fresh clone (acceptance 5), commands exactly as in the README, with `GOPROXY=off`:

```
30b5b4e CP8 task 5: 'superseded by' notes in design docs the experiments overturned (design history kept)
helper modules downloaded
triage exit 0
wrote data/demo/fixture.html (1 verdict(s), 6895 bytes)
REACHABLE PASSED []        <- verdict, verification status, reason codes read from data/demo/fixture_direct_call.json
```

The committed real-application page also builds with no network: `python -m vulntrace demo build --verdict docs/results/cp7b/verdicts/gitleaks__GO-2025-4020.json --out data/demo/d3.html` printed `wrote data/demo/d3.html (1 verdict(s), 19804 bytes)`.

## 5. Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | `results summary` regenerates `SUMMARY.md` and `summary.json` exactly | Met | `test_summary_files_are_up_to_date`, `--check`; also green in CI on Ubuntu / Python 3.12 |
| 2 | No number in README, final report, notes that is not in `summary.json` or a cited result file; tests check README and notes | Met, with a stated limit | `test_no_number_outside_the_summary` and `test_pairs_and_intervals_exist_in_the_summary` run on all three documents (the final report too). It catches numbers absent from the summary, "k of n" pairs and `[low, high]` intervals that do not exist there; it cannot detect a correct number attached to the wrong claim. Whole-number tokens are matched against whole numbers in the summary, but small integers appear in it, so a wrong small count could still pass. Mitigation: the README table is generated and compared exactly. The checker caught real errors of mine during the session (bounds copied from an early printout) |
| 3 | Every negative result stated with its consequence for the design | Met | Final report sections 6.3 to 6.9 each have a "What it changed" paragraph; README "What did not work"; `test_negative_results_are_stated_with_their_consequence` |
| 4 | Wording limits respected | Met by review plus tests | Reachability only (`test_reachability_not_exploitability`); REACHABLE "needs a human look"; adjudication described as two Claude reviewers, supervisor reconciliation, owner spot-check, never ground truth (`test_adjudication_is_never_called_ground_truth`); govulncheck "not worse"; Mode 2 numbers used BM25; go1.26.10 outside CI; required phrases tested. Final read-through by me, not by the supervisor yet |
| 5 | Quickstart runs offline on a fixture in a clean checkout | Met, with a caveat | Section 4. Caveat: the Go module cache was already populated, so the initial download was not exercised |
| 6 | No behaviour, result-file, prompt or verdict-rule change | Met | Section 2 (`git diff --stat`) |
| 7 | All tests pass locally and in CI on the last commit; report; STATUS `AWAITING_REVIEW` | Met for the last code commit | CI run 150 on `30b5b4e` (all jobs and steps `success`, including Go unit tests, integration tests and the pgvector job); runs on the three earlier commits were also `success`. The commit that adds this report and the STATUS change is documentation only; its CI result is stated in my closing message, not in this file |

## 6. Results

`docs/results/summary.json` and `docs/results/SUMMARY.md` are the results of this checkpoint. They are produced by `python -m vulntrace results summary` and contain no number that is not computed from committed files. Examples (copied from `SUMMARY.md`): CP4 hybrid MRR 0.599 [0.519, 0.683] vs B-ID 0.397 [0.317, 0.478]; hybrid vs BM25 paired 0.028 [-0.011, 0.065]; E1 llama paired recall -0.271 [-0.337, -0.207]; agent qwen A2 minus A0 -0.208 [-0.304, -0.112]; fixtures Mode 1 false NOT_REACHABLE 0 of 22; D3 REACHABLE paths able to run 0/7 = 0.000 [0.000, 0.354].

## 7. Design deviations

1. **The summary also rewrites the README table** between markers (spec: `SUMMARY.md` and `summary.json` only). Reason: spec asks for a README table "taken from `summary.json`" with a test; generating it makes the match exact. `--check` verifies all three files.
2. **Raw values, rounded once.** My first version rounded to 4 decimals before formatting to 3 and printed values that differed from the results documents in the last digit (for example recall 0.570 vs 0.569). Fixed: rows keep the raw float, only the JSON is rounded (6 decimals). `test_numbers_equal_those_printed_in_the_results_documents` compares every CP4/CP5/CP5b/CP6 mean/delta row to the printed cell in the corresponding results document. Four CP4 rows are not tables in that document (code-search vs bge-small, commit subjects for hybrid and BM25, ID-mask control); they are listed in the test as computed only by the summary (same code, same files).
3. **Final report covers the same experiments from `summary.json` only.** CP1/CP2 numbers (naive/linker/VTA comparison) live in the results documents, whose score files (`results/cp1`, `results/cp2`) are not committed, so they are described qualitatively and linked, with no numbers.
4. **Not repeated in the summary:** the D1 E0 baseline from CP3's document (its source `results/cp3` is not committed); the E0 numbers used are the ones inside the committed CP5 files.
5. The README no longer carries the old design-phase document index and CP1-CP6 command list. The command list was moved unchanged to the new `docs/DEVELOPMENT.md` and is linked from the README map (new file, listed here because it is not in the spec).

Stale or contradictory documents found (notes added where listed in section 2; none deleted):

- `SYSTEM_ARCHITECTURE.md`, `DATA_FLOW.md`, `PROJECT_DEFINITION.md`, `ARCHITECTURE_DECISIONS.md` (ADR-005, 007, 008 still say "Proposed"; outcome lines added), `EVALUATION_PLAN.md` (MA1), `TESTING_STRATEGY.md` (CP8 line), `RISKS_AND_OPEN_QUESTIONS.md`, `FEASIBILITY_FINDINGS.md` (LLM "precision" proposal not confirmed), `DATASET_STRATEGY.md` (D3 "owner adjudication"), `PROJECT_STRUCTURE.md` ("none of the code directories exist yet").
- **Not touched, for the supervisor:** `docs/progress/SUPERVISOR_HANDOFF.md`: its "State at 22 Oct 2026" section is superseded by its own later section but still reads as current if read top to bottom; it also uses different pronouns/names for the owner in different places.
- `docs/design/INTERFACES_AND_CONTRACTS.md` and `DATA_MODEL.md` were not re-read line by line for stale statements; `RootCauseSelection` and the C2/C14 flow are described as designed there.
- ADR status fields were left as written ("Proposed"); only an outcome line was added.

## 8. Blockers and limitations

- Docker daemon unavailable: pgvector tests skipped locally (CI ran them: job `pgvector` `success`).
- The adjudication description relies on the CP7b review and report; I did not re-verify any adjudication.
- The number check has the limits in acceptance 2. The final report was written from the generated summary, but its prose claims (design rationale, experiment setups) rest on the checkpoint reports and reviews, which I read but did not re-derive.
- Interview notes: the owner-contribution sentence is a placeholder for the owner.
- The licence is undecided (no licence file); README says so.
- The CP4/CP5 hyperparameters and prompts were not re-inspected.

## 9. Suggestions for the next checkpoint (not implemented)

- Decide a licence.
- Supervisor: refresh `SUPERVISOR_HANDOFF.md`; consider whether the README should keep an evaluation-commands section.
- Optional, new checkpoint: path-feasibility check for REACHABLE; re-run Mode 2 with the intended hybrid retriever; newer Go in CI.

## 10. Git

Branch `claude/vulntrace-ai-build-5f8jgi`; every push below succeeded:

```
30b5b4e CP8 task 5: 'superseded by' notes in design docs the experiments overturned (design history kept)
d63076e CP8 tasks 2-4, 6: final report, interview notes, README number/link/wording checks; datasets rows for D4 date skew and truncation
65f0deb CP8 task 1: results summary generator (results summary -> SUMMARY.md, summary.json, README key-results table) with regeneration, source-hash and results-document cross-check tests; README rewritten
62b6bb7 CP8: session starts; STATUS IN_PROGRESS, branch claude/vulntrace-ai-build-5f8jgi, task list
```

plus the final commit with this report and STATUS `AWAITING_REVIEW`. No pull request was opened (per instructions).
