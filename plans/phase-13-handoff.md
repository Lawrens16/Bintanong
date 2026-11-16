---
artifact: phase-handoff
phase: 13
status: complete
plan: plans/phase-13-hosted-llm-agent-plan.md
final_commit: b37c4902
next_phase: 14
completed_at: 2026-11-15T21:30:00+08:00
completion_scope: hosted-LLM agent built, verified and deployed for the personal fork with the disclosed gaps below; not a thesis result, not institutional approval
---

# Phase 13 final handoff: hosted-LLM agent (personal fork)

The fork now answers through one tool-using chat agent on a hosted model API, reading the same hosted Supabase
release read-only, and runs for $0 at https://bintanong.vercel.app (Vercel) with the backend on Render free
(https://bintanong-agent-api.onrender.com). It is separate from the thesis (owner, 15 Nov 2026): it does not
implement the thesis k-NN/cosine retrieval online, its results are not thesis results, and it is not
institutional approval or proof that the sources are current. The original Gemma path is unchanged.

## Exit evidence

| Gate (plan) | Evidence | Result |
| --- | --- | --- |
| Starts with Supabase URL + anon key + one provider key; no GPU, Gemma, encoder or sealed package | `load_agent_app`; container under `--memory 512m` ready in 41 s; Render `/health/ready` 200 | PASS |
| Provider switch is an env change; all four pass the provider tests | `tests/test_agent_providers.py`, `test_agent_settings.py` (fake HTTP); live: DeepSeek only | PASS for tests; live GPT/Gemini/Claude not run (no keys) |
| Follow-ups use history; greetings answered naturally | live check `follow-up`, `greeting`; browser follow-up turn | PASS |
| Loose course names resolve; eligibility follows the rule tool | "cc5", "CC-5", "cc 5/l" -> CC 5/L; live CC 5/L and CS 6 answers match the Prolog results, stated grades used | PASS |
| Each guard RED then GREEN, and holds live | guards 1-4 tests (`test_agent_guards.py`, `test_agent_loop.py`); live: graduate question blocked with no model call, cited answers only cite fetched passages, eligibility answers called the rule tool | PASS; guard 2 not exercised live (no upload in the live check) |
| No Supabase write; service-role key never read | `test_no_supabase_write_method_is_called`; service-role key refused at startup; Supabase MCP read-only: newest row in chunks, embeddings, releases, ledgers dated 24-29 Oct 2026; active release `p12-research-faqsplit-20261030` 560 chunks / 39 curricula | PASS |
| Original `research_app` path and tests unchanged | only `bintanong_api/app.py` widened (`ApiServices.turns`, default keeps `ChatTurns`); full suite identical to the starting commit (below) | PASS |
| Fits Render free memory | local 157.6 MiB of a 512 MiB cap after a rule check; Render metrics not read | PASS locally; Render-side reading open |

**Full suite**, branch `b37c4902` vs starting commit `f1fe3f2b`, same venv, `--continue-on-collection-errors`:
both 233 failed / 36 errors with the identical id set (`comm` empty both ways); branch 6631 passed vs 6474
(+157 new tests); 9 collection errors are missing `jsonschema`/`cv2` in the shared venv; most failures are
storage database tests without a local Supabase. Logs: `audit-evidence/p13-full-suite2/`. The plan's recorded
baseline (82 failures, 9 collection errors) came from an earlier environment; the same-run comparison is the evidence.
**Focused:** API + agent + transport/adapter tests 458 passed; frontend `npm run test:ui` 118/118
(`BINTANONG_TEST_PYTHON` = venv Python), `npx tsc --noEmit` exit 0.

## Live and deployment evidence

- Live check, 14 DeepSeek turns on the real release (`audit-evidence/p13-live-20261115/transcript-{off,on}.json`):
  every key fact checked against its cited passage text was present. Thinking off: $0.0136 at peak prices for
  14 turns (about $0.001 per question), 88% of input tokens cached, 1.5-7.1 s per answer; thinking on cost 71%
  more for slightly fuller wording, so thinking stays off. Development check only, not an accuracy claim.
- Browser run on the container: found and fixed two defects (cited answers cut off by the frontend source-id
  rule; English after Taglish replied in Taglish), then rechecked: English reply, Sources (6), source card text.
- Public site (15 Nov): class card answer with 6 Charter sources in 5.7 s; Taglish CC 5/L eligibility in 7.0 s.

## Commits and artifacts

32 non-merge commits on `feat/hosted-llm-agent` from `f1fe3f2b`; milestone tags `agent-m2`..`agent-m8` (local).
New code: `backend/bintanong_agent/` (providers, settings, corpus, search, curriculum, tools, prompt, guards,
agent), `backend/bintanong_api/{agent_turns,agent_app}.py`, `frontend/lib/student-progress.ts`, tests
`tests/test_agent_*.py`, `tests/test_api_agent_*.py`, `frontend/tests/student-progress.test.mjs`. Deploy:
`docker/agent-api.Dockerfile` (+ `.dockerignore`), `render.yaml`, `docs/development/hosted-agent-deploy.md`,
`knowledge/manifests/program-display-names.json`. Branch pushed to `origin` (`Lawrens16/Bintanong`) only.

## Versions and digests

`swipl:10.0.2` base, Python 3.13.15 (uv 0.12.17), locked backend `api` extra, `janus-swi` 1.5.3 compiled in the
image; local image `363132369997`, 662 MB. Model `deepseek-flash` (thinking disabled). No dependency, lock,
model or Supabase change.

## Deviations and rulings

- Tasks 5-8 were implemented inline by the controller after the 14 Nov implementer was cut off; no separate
  per-task reviewer ran. The whole-branch review was done inline by the same agent (no defect found beyond those
  fixed in the browser run), so it is not an independent review.
- Rulings R1-R6 (`.superpowers/sdd/.../progress.md`, summarized in the checkpoint); owner decisions on 15 Nov:
  thinking off and caching order, stated grades to the rule check, display names, base-image downloads, push.
- Vector search (`BINTANONG_VECTOR_SEARCH`) not wired into the app: keyword search only online.

## Unresolved risks

- **Privacy disclosure:** questions, chat history and the student's stated or uploaded course results are sent
  to the DeepSeek API to answer. The site's privacy notice says what is typed "is kept temporarily and is not
  stored permanently"; whether the provider's retention matches that is not verified. Owner decision needed.
- Public link spends the owner's DeepSeek balance ($1.41 at 15 Nov; 5 questions / 5 min per person).
- Render free sleeps after 15 min; cold-start time and Render memory not measured on Render.
- Sessions live in memory: a restart or sleep clears chats. The fork reads whichever release is active.
- Repository is a public fork; GitHub does not allow making a fork private without detaching it.

## Next-phase prerequisites

Updated 16 Nov 2026: PR #1 is open on the fork (`feat/hosted-llm-agent` -> `main`; the fork has no `dev`
branch) and waits for the owner's review and merge. The privacy and visibility decisions are made (15 Nov: no
grades or identity, uploads off, repository stays public; see `plans/owner-decisions-ledger.md`). A trailing
slash in `BINTANONG_ALLOWED_ORIGINS` is now accepted. Still optional: measure Render cold start and memory on
Render, live-test another provider when a key is available.
