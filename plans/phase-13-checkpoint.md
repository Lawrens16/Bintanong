---
artifact: phase-checkpoint
phase: 13
status: in_progress
sequence: 8
plan: plans/phase-13-hosted-llm-agent-plan.md
head_commit: d1e22a90
working_tree: checkpoint staged for commit; head_commit is that commit's parent
updated_at: 2026-11-15T17:00:00+08:00
---

# Phase 13 checkpoint: hosted-LLM agent (fork)

## Completed Tasks

- Task 0 (records and PRD), commit `8fa9be52`: branch `feat/hosted-llm-agent` cut from `Lawrens16/dev` at
  `f1fe3f2b`; [PRD](2026-11-15-hosted-llm-fork-prd.md) drafted; [plan](phase-13-hosted-llm-agent-plan.md) saved;
  [hosting research](2026-11-15-phase-13-pre-phase-research.md); fork section in `AGENTS.md` and the ledger.
- Task 1 (feasibility probes, read-only): results below. Scripts and outputs are in the ignored
  `C:/Coding-projects/bintanong_workspace/audit-evidence/p13-probes-20261115/`.
- Task 2 (providers and settings), commit `136de9bb`, merged to `feat/hosted-llm-agent` and tagged `agent-m2`:
  `backend/bintanong_agent/{__init__,providers,settings}.py`, `tests/test_agent_providers.py`,
  `tests/test_agent_settings.py`. RED 32 failed (module missing), GREEN 32 passed; existing
  `tests/test_routing_transport.py` 23 passed (implementer's runs). Task review: spec compliant, approved,
  minors deferred to the final review. `openai` has no default model (`llm_model_required`).
  Milestone branches are merged locally; PRs on `origin` wait for the owner's go-ahead to push.
- Task 3 (corpus and search), commits `e7bd9912` + fix `c64af42f`, merged and tagged `agent-m3`:
  `backend/bintanong_agent/{corpus,search}.py`, `tests/test_agent_corpus.py`, `tests/test_agent_search.py`.
  RED 9 failed (modules missing), GREEN 9; review found the vector wrapper used min similarity 0.5 and
  omitted scope/version filters; fixed test-first (RED 2 failed, GREEN 11 passed), re-review clean.
  Read-only run on the real release (`probe_corpus_real.py`): 560 passages, 171 topics, topic directory
  11,646 characters; sample questions (TOR request, removal exam, overload, shifting) rank the expected
  Charter/Handbook passages first. Passage text is built from the chunk's field list, not through
  `render_reviewed_policy_context` (the paged loader already validates each chunk with it).
- Task 4 (curriculum tools), commits `bfe8508d`, `d08fd6e6`, `31da7477`, merged and tagged `agent-m4`:
  `backend/bintanong_agent/curriculum.py`, `tests/test_agent_curriculum.py`. RED 8 failed + 5 errors (module
  missing), GREEN 13; review + a read-only run on the real curricula found internal course ids in the
  unmet/unknown lists and uncaught bad-argument errors; fixed test-first, re-review clean. Controller run at
  the merged head: the five agent test files pass. Real curricula (`probe_curriculum_real.py`): "cc5",
  "CC-5", "cc 5/l" all resolve to CC 5/L; a rule check takes about 0.3 s; results name printed codes.

- Task 5 (tools, prompt, guards, agent loop), commit `3434ae13`, merged and tagged `agent-m5`:
  `backend/bintanong_agent/{tools,prompt,guards,agent}.py`, `tests/test_agent_{tools,guards,loop}.py`.
  Done inline by the controller after the 14 Nov implementer was cut off by the usage limit before writing
  anything. RED 59 failed (four modules missing), GREEN 59; neighbour passages added test-first (RED 1 failed,
  GREEN 61). All eight agent test files + `test_routing_transport.py` + `test_orchestration_adapters.py`:
  159 passed. Read-only run on the real release (`probe_task5_real.py`): 0 of 560 passages trip the
  private-id scan; system prompt with the topic directory is 15,327 characters; a search result with required
  neighbours is 6-16 thousand characters (13-28 passages); 4 topics exceed the 12-passage cap.
  **Not done:** the separate task reviewer (no subagent was dispatched in this session) and the full suite.
  Built interface for Task 6: `Agent(model, ToolRunner(search, corpus, curriculum), max_rounds=6)`,
  `await agent.answer(question, history, TurnState(program_id, curriculum_id, facts), progress)` ->
  `AgentAnswer(status, text, language, citations: tuple[Passage], used_rules)`; `answer` clears
  `state.fetched` / `state.rule_checks` at the start of each turn; progress stages `searching`, `checking`,
  `writing`; history is a list of `{role, content}` dicts. Search and curriculum exceptions other than the
  known error codes propagate out of `answer`.

- Task 6 (API composition and stream), commit `a46d812a`, merged and tagged `agent-m6`:
  `backend/bintanong_api/{agent_turns,agent_app}.py`, `tests/test_api_agent_{turns,app}.py`, and one widening
  of `backend/bintanong_api/app.py` (`ApiServices.turns`, default `None` keeps `ChatTurns`). RED 21 failed
  (modules missing), GREEN 21. All `tests/test_api_*.py` + `tests/test_agent_*.py` + transport/adapter tests:
  443 passed (the basetemp parent folder must exist first, or `tmp_path` tests error). Read-only start on the
  real release, no model call (`probe_agent_app_real.py`): startup 44.0 s, working set 187.1 MB, 39 curricula,
  `/health/ready` 200, 560 passages, 171 topics, 2132 catalog entries.
  `AgentTurns(ChatTurns)` keeps `prepare`/`checked_scope`; history is the session's committed exchanges
  (at most 8); a `temporarily_unavailable` reply is shown but not committed. `load_agent_app(env)` reads
  `SUPABASE_URL`, `SUPABASE_ANON_KEY`, provider variables, `BINTANONG_ALLOWED_ORIGINS` (comma-separated),
  `BINTANONG_ALLOW_GUESTS=1`, `BINTANONG_RELEASE_ID`, `BINTANONG_RESEARCH_AUTHORIZATION`.
  **Not done:** separate task reviewer; `BINTANONG_VECTOR_SEARCH` (keyword search only; deferred, no online use).

## Current Task

Task 7 (frontend labels), then the open items below before Task 8.

## Repository State

- Worktree `C:/Users/joel/orca/workspaces/Bintanong-personal/dev`, integration branch `feat/hosted-llm-agent`
  (milestone branches merged locally, tags `agent-m2`..`agent-m5`), nothing pushed.
  `origin` = `Lawrens16/Bintanong`; `upstream` = `bintanong420/Bintanong` is never pushed to.
- Only new files so far: `backend/bintanong_agent/` and `tests/test_agent_*.py`. No existing file under
  `backend/`, `frontend/` or `tests/` was edited.

## Verification Evidence

- `phase_state.py validate` after Task 0: State valid, active phase 13.
- Probe 1, chunks (`probe_chunks_memory.py`, `probe_row_caps.py`; anon key, GET only, 0 non-GET calls):
  active research release `p12-research-faqsplit-20261030`, authorization `research-owner-20261029`,
  560 chunks, 5 document versions. Readable chunk fields: `anchored, byte_sha256, chunk_id, chunk_type,
  chunker_version, content_hash, content_review, document_id, edition_id, scope, section_path, source_label,
  source_text, text, token_count, type_fields, version_id` plus spans. Snapshot is 4.38 MB as JSON.
  **Defect found:** `load_document_snapshot` as written fails with `invalid reviewed context record`, because
  an anon read returns at most 1000 rows per request and `source_spans` has 2529 (HTTP 206, `0-999/2529`), so
  243 of 560 chunks get no or partial spans. With `source_spans` read in pages (limit/offset, ordered by
  `chunk_id,span_order`) the unchanged loader passes and takes 2.12 s.
- Probe 2, topic directory (`probe_topics.py`, `probe_topic_groups.py`, `probe_local_catalogue.py`):
  `section_path` is empty on all rows; every row has `type_fields.reading_id`; 490 rows have
  `service_group.logical_step_id`. Grouping by it (reading id stem otherwise) gives 159 groups with readable ids
  such as `C-readmission`, `C-tor-copy`, `H-shifting`, `H-overload`; 43 groups (the Charter services) also carry
  a printed service title field. The local sealed catalogue gives 145 subjects with ids of the same kind
  (`charter_diploma`, `handbook_graduation`, `grade_completion`) and short claim phrases, no better titles.
- Probe 3, memory (Windows working set / private MB, one process): Python start 15.7 / 9.3; FastAPI app
  imports 84.2 / 65.6; + snapshot 104.5 / 82.9; + 39 ledgers 158.9 / 137.3; + 39 curriculum runtimes
  185.9 / 163.6. Under the 400 MB line, so curricula can load at startup. Startup cost: ledgers 22.5 s
  (39 reads), runtime build 28.5 s; 2132 catalog entries. Not measured: Linux RSS in the container and the
  short-lived Janus worker subprocess per rule check (`backend/bintanong_symbolic/runtime.py:233`); Task 8.
- Probe 4, Prolog image: `janus-swi==1.5.3` on PyPI ships only a Windows cp314 wheel and an sdist, so on Linux
  it compiles against the installed SWI-Prolog and needs 9.1.12 or later. Debian bookworm's `swi-prolog-nox`
  is 9.0.4, too old. The apt package is ruled out.
- Probe 5, provider docs (read 15 Nov 2026):
  - DeepSeek: base `https://api.deepseek.com`, `POST /chat/completions`, models `deepseek-flash` and
    `deepseek-v4-pro` (`deepseek-v4-flash` is a deprecated alias). OpenAI tool shape; `function.arguments` is
    a JSON string that "does not always generate valid JSON"; `tool` message needs `tool_call_id`;
    `max_tokens`; `response_format` `json_object`. `tool_choice` `required` is rejected in thinking mode.
    ([docs](https://api-docs.deepseek.com/), [chat completion](https://api-docs.deepseek.com/api/create-chat-completion))
  - OpenAI: `https://api.openai.com/v1/chat/completions`; same tool shape; `max_tokens` is deprecated in
    favour of `max_completion_tokens`. The function-calling guide says GPT-6 Astra and GPT-6.1 Sol need the
    Responses API for tools and its Chat Completions examples use GPT-5.6 Terra; that model's exact id was not
    shown. ([reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
    [guide](https://developers.openai.com/api/docs/guides/function-calling))
  - Gemini (OpenAI-compatible, beta): base `https://generativelanguage.googleapis.com/v1beta/openai/`;
    example models `gemini-4-hydrogen`, `gemini-3.8-flash`; `tools` + `tool_choice: "auto"` supported.
    ([docs](https://aistudio.google.com/docs/openai))
  - Anthropic: `POST https://api.anthropic.com/v1/messages`, headers `x-api-key`, `anthropic-version:
    2026-10-21`; `max_tokens` required; tools are `{name, description, input_schema}`; reply has `tool_use`
    blocks with `stop_reason: "tool_use"`; results go back as `tool_result` blocks (`tool_use_id`) in a user
    message. Current ids include `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`.
    ([docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview))

## Versions and Digests

- No dependency, lock, model or image change. Local: SWI-Prolog 10.1.15 (Windows), `janus-swi` 1.5.3,
  shared venv `C:/Coding-projects/bintanong_workspace/audit-evidence/p12-env-20261031/venv`.
- Existing `docker/api.Dockerfile` builds SWI-Prolog 10.0.2 from source on `python:3.13.15-slim-bookworm`.

## Decisions

- Owner, 15 Nov 2026: fork decisions, verbatim in `plans/owner-decisions-ledger.md`.
- Phase number: Phase 13 of this fork; the original build's Phase 13 deployment stays cancelled (29 Oct 2026).
- Context consulted at phase start: thesis physical pp. 17-18 (printed 16-17) and
  `Context/bintanong_full_runtime_routing_architecture.png`. Discrepancies, all by owner fork decision:
  (1) the thesis names a localized Tagalog/English NLP model and SEA-LION-E5 vector search; the fork uses a
  hosted LLM and, online, topic directory + keyword search judged by the LLM; (2) the diagram's separate
  router / RAG / Symbolic / Hybrid boxes become one agent that chooses tools per turn; Prolog via Janus still
  evaluates the rules; (3) output validation becomes four code guards. Unchanged: undergraduate scope, excluded
  audiences, read-only advisory tool, no learning from chats, private uploads kept apart,
  English/Filipino/Taglish input. The fork's results do not inherit the thesis evaluation figures.
- Task 3/6 design consequence of probe 1: the agent app reads `source_spans` in pages through a small
  read-only wrapper around the storage client (new code in the fork), then calls the unchanged
  `load_document_snapshot`. No edit to the original loader and no Supabase setting change.
- Task 4 consequence of probe 3: load all 39 curricula at startup (no lazy loading needed on the memory
  evidence so far); re-check on Linux in Task 8.
- Task 8 consequence of probe 4: keep a SWI-Prolog 10.x build stage as in `docker/api.Dockerfile` (proven),
  or copy SWI-Prolog from the official `swipl` image if a local build shows it works and is faster; the
  `janus-swi` sdist is compiled in a build stage. Chosen at the local image build.
- Task 2 defaults proposed from probe 5: `deepseek` -> `deepseek-flash`; `gemini` -> `gemini-3.8-flash`;
  `anthropic` -> `claude-haiku-5-5`; `openai` -> the GPT-5.6 Terra id, confirmed from the models list when the
  owner supplies a key (not guessed). OpenAI requests send `max_completion_tokens`; the others `max_tokens`.
- Topic directory: option A (derive from chunk rows: group id + printed service title where present) is
  recommended over option B (derived file from the local catalogue as a Render secret file), since B's
  labels are no better and A needs no extra file. **Owner chose A ("yeah do Option A"), 15 Nov 2026.**
- Guard 2 (ruling R6): `private_leak` checks the cited source cards (fetched this turn, no `sess-`/`fact-`
  ids via `foreign_ids`), not the reply text; the model is sent the student's course facts by printed code
  only, never session or fact ids. Guard 4 uses `EXCLUDED_PROGRAM_CUES` as is; staff-only questions rely on
  the system prompt (`out_of_scope` kind), since that list has no staff phrases.
- Session resume, 15 Nov 2026 (new CLI session): thesis pp. 17-18 and the routing PNG re-read; no new
  discrepancy beyond the three recorded above.
- Owner, 15 Nov 2026: PRD approved. The fork is separate from the thesis and not used in the final defense;
  it may later be offered publicly. Verbatim in the ledger.

## Known Failures or Blockers

- Render free memory has one unverified conflicting report (256 MB); re-read in the dashboard at deploy.
- Full-suite environmental baseline to compare against later: 82 failures and 9 collection errors.

- Open, found in Task 6: (1) grades the student types in chat are not passed to the rule check; only
  confirmed upload facts are, so "I passed CC 3, can I take CC 5?" evaluates as unknown. Proposed fix,
  test-first: an optional `student_results` argument on `check_prerequisite`. (2) Program and curriculum
  names shown in the picker are source file names (the original app reads names from its local config).
- `guards.py` imports `router.py` and `agent_app.py` imports `research_app._public_key`, which pull the
  original generation stack into memory; measured 187 MB on Windows, re-check on Linux in Task 8.

## Next Action

Task 7 (frontend labels) on `feat/agent-api`; then the typed-grades fix above, test-first.
Task 8 needs the owner's DeepSeek key in the ignored `.env`.

## Do Not Repeat

- Phase start inspection, thesis/PNG reading, hosting research, PRD drafting, branch creation and the five
  Task 1 probes are done. Do not re-ask the 15 Nov fork decisions.
- Do not call `load_document_snapshot` with an unpaged client against the hosted release; it fails as above.
