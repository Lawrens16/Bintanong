---
artifact: phase-checkpoint
phase: 13
status: in_progress
sequence: 1
plan: plans/phase-13-hosted-llm-agent-plan.md
head_commit: f1fe3f2b
working_tree: Task 0 documents staged for the opening commit; head_commit is that commit's parent
updated_at: 2026-11-15T12:00:00+08:00
---

# Phase 13 checkpoint: hosted-LLM agent (fork)

## Completed Tasks

- Task 0 (records and PRD): branch `feat/hosted-llm-agent` cut from `Lawrens16/dev` at `f1fe3f2b`;
  [PRD](2026-11-15-hosted-llm-fork-prd.md) drafted with `create-prd`; [plan](phase-13-hosted-llm-agent-plan.md)
  saved with frontmatter; [hosting research](2026-11-15-phase-13-pre-phase-research.md); fork section added to
  `AGENTS.md` and the owner-decisions ledger; index and current progress updated.

## Current Task

Task 1: feasibility probes (read-only; no production code). PRD approval by the owner is pending and gates
Task 2 onward.

## Repository State

- Worktree `C:/Users/joel/orca/workspaces/Bintanong-personal/dev` (Orca workspace of the personal fork), branch
  `feat/hosted-llm-agent`, not pushed. `origin` = `Lawrens16/Bintanong`; `upstream` = `bintanong420/Bintanong`
  is never pushed to. `origin` held only `main` at phase start.
- No file under `backend/`, `frontend/` or `tests/` changed in Task 0.

## Verification Evidence

- `phase_state.py inspect` at start: State valid; no active phase, plan or checkpoint; latest handoff
  `plans/phase-12-handoff.md`; working tree clean; can advance: yes.
- `phase_state.py validate` after the Task 0 documents: State valid (result also in current progress).
- Task 0 is documentation only: no tests apply (stated exception; validation is `phase_state.py validate`).

## Versions and Digests

- No dependency, lock, model or image change. Provider model ids, base URLs and the SWI-Prolog package choice
  are Task 1 results and will be recorded here.
- Shared venv: `C:/Coding-projects/bintanong_workspace/audit-evidence/p12-env-20261031/venv` (present).

## Decisions

- Owner, 15 Nov 2026: fork decisions (hosting, tool-using agent, keyword retrieval online, four providers
  with DeepSeek first, four guards with guard 1 loosened, no Supabase change, original path untouched). Verbatim in
  `plans/owner-decisions-ledger.md`.
- Phase number: recorded as Phase 13 of this fork. The earlier Phase 13 (deployment) was cancelled on
  29 Oct 2026 and never created; that cancellation stands for the original build.
- Context consulted at phase start: thesis physical pp. 17-18 (printed 16-17, Scope and Limitations) and
  `Context/bintanong_full_runtime_routing_architecture.png`. Discrepancies, all by owner fork decision:
  (1) the thesis names a localized Tagalog/English NLP model and SEA-LION-E5 vector search; the fork uses a
  hosted LLM and, online, topic directory + keyword search judged by the LLM; (2) the routing diagram's
  separate router / RAG / Symbolic / Hybrid boxes become one agent that chooses tools per turn; Prolog via
  Janus still evaluates the rules; (3) output validation becomes four code guards. Unchanged: undergraduate
  scope, excluded audiences, read-only advisory tool, no learning from chats, private uploads kept apart,
  English/Filipino/Taglish input. The fork's results do not inherit the thesis evaluation figures.

## Known Failures or Blockers

- None. Full-suite environmental baseline to compare against later: 82 failures and 9 collection errors.
- Render free memory figure has one unverified conflicting report (256 MB); measured in Task 1, re-read at deploy.

## Next Action

Run the Task 1 probes (chunks, topic directory, memory, Prolog image, provider docs) from the ignored
`C:/Coding-projects/bintanong_workspace/audit-evidence/p13-probes-20261115/`, record each result here, and
show the owner the topic-directory samples and the PRD summary.

## Do Not Repeat

- Phase start inspection, thesis/PNG reading, hosting research, PRD drafting and branch creation are done.
- Do not re-ask the 15 Nov fork decisions.
