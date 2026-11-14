---
artifact: phase-plan
phase: 13
status: in_progress
master: plans/master_implementation_plan_original_long.md
previous_handoff: plans/phase-12-handoff.md
---

# Hosted-LLM Conversational Agent (Bintanong fork) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` to implement this plan
> task-by-task (a fresh implementer per task, a fresh reviewer before the next). Steps use checkbox syntax.
> Also apply `test-driven-development`, `karpathy-guidelines`, `systematic-debugging`,
> `verification-before-completion`, the repo's `bintanong-phase-handoff` and `conventional-commits` skills.

**Goal:** Replace the local Gemma answer path in this fork with one conversational, tool-using agent on a
hosted LLM API (DeepSeek first, then GPT, Gemini, Claude), deployable for $0 on Vercel + Render free,
without changing anything in Supabase.

**Architecture:** A new package `backend/bintanong_agent/` runs one chat loop per message: history + question
-> hosted model -> tools (search the existing chunks, read the curriculum rules and Prolog evaluation) ->
final reply with citations -> four light code guards. A new app factory serves it through the existing
FastAPI app, sessions, uploads and UI stream. The original Gemma path stays in the repo, untouched and runnable.

**Tech stack:** Python 3.13, FastAPI, `httpx` (already a dependency; no new packages, no lock change),
SWI-Prolog via `janus-swi`, Supabase PostgREST with the anon key, Next.js 16 frontend.

**Spec:** [PRD](2026-11-15-hosted-llm-fork-prd.md) (written in Task 0 with `create-prd`; owner approves it
before Task 2).

## Context

The original system makes up to about 10 Gemma calls per message, and about 30 host modules rewrite the
4B model's wording. It needs a GPU, a 2.5-3 GB embedder and local sealed files, so it cannot be hosted.
Owner decisions, 15 Nov 2026 (this planning session):

- Frontend on Vercel Hobby, backend on Render free (512 MB). No card, no cost.
- Tool-using chat agent; the LLM judges which chunks to use and how to word the reply.
- Online retrieval = topic directory + keyword search over the same Supabase chunks. The SEA-LION embedder
  cannot fit in 512 MB and Hugging Face Docker Spaces now need a paid plan. Vector search stays available
  behind the same interface where the embedder fits (the laptop).
- All four providers, DeepSeek first.
- Four guards stay in code, with guard 1 loosened as the owner directed (below).

## Global Constraints

- **No Supabase change.** No migrations, no writes, no RPC that writes, no service-role key read by the agent
  app. Reads use the anon key only. Supabase MCP is used for read-only checks only.
- **Original path untouched.** No behaviour change in `bintanong_routing`, `bintanong_generation`,
  `bintanong_orchestration`, `research_app.py`, `research.py`. New code imports from them; it does not edit them.
- **Git.** Push only to `origin` (`Lawrens16/Bintanong`). Never push to `upstream` (`bintanong420/Bintanong`).
  Conventional Commits, explicit staging, no AI attribution trailers.
- **No installs, downloads or lock changes.** Reuse the shared venv
  `C:/Coding-projects/bintanong_workspace/audit-evidence/p12-env-20261031/venv/Scripts/python.exe` (`$PY`).
- **Tests:** `PYTHONUTF8=1 $PY -B -m pytest -q -p no:cacheprovider <files> --basetemp <new audit-evidence run dir>`.
  Tracked tests use synthetic fixtures only. Secrets and source-derived data stay in ignored files.
- **Replies:** English question -> English; Filipino/Taglish -> Taglish. Undergraduate academic affairs only.
  Advisory, read-only.
- **Outward steps** (creating Render/Vercel projects, first push of a new branch, deploys) are confirmed
  with the owner at the moment they happen.

## The four code guards

1. **Eligibility comes from the reviewed rules (loosened).** Before answering "can I take X", the agent must
   have called the curriculum tool this turn. The tool returns the printed prerequisite rule and the Prolog
   evaluation; the LLM reads them and decides and words the answer itself. Course names are matched
   forgivingly ("cc5", "CC-5", "cc 5/l", a title) and the LLM picks from candidates, so a missing space or a
   dash no longer ends in "unknown". No byte-for-byte host verdict line and no wording regex.
2. **Private data never leaks.** Uploaded or typed grades stay in the owning session; code checks they never
   appear in citations, source cards or logs (existing `foreign_ids`).
3. **Policy answers cite a retrieved chunk.** A policy/procedure answer must cite at least one chunk fetched
   this turn. Unknown or missing citations get one retry, then an honest "couldn't verify, ask the office".
4. **Excluded-audience block.** Medicine, Law, graduate, laboratory school and staff-only questions get the
   fixed undergraduate-scope notice from code (existing `EXCLUDED_PROGRAM_CUES`).

Source gaps and conflicts, tone, language and office referrals are system-prompt guidance.

## Review Focus

- Student types a course loosely ("cc5", "math12/l", "Data Structures") -> candidates are found and the rule
  is evaluated; never a bare "unknown course". (Task 4 tests)
- Provider returns malformed tool arguments or an unknown tool name -> the error is fed back to the model once;
  the loop does not crash or spin. (Task 5 tests)
- Provider timeout / 429 / 5xx -> a friendly "temporarily unavailable" reply, no stack trace, no retry storm.
  (Task 2 tests)
- Model cites a chunk id it never fetched -> one repair, then the fallback reply. (Task 5 tests)
- Curriculum not chosen but an eligibility question is asked -> the agent asks which program/curriculum
  instead of guessing. (Task 4 and 5 tests)

## Phase records and branching (handoff skill)

- This work is recorded as **Phase 13: hosted-LLM agent (fork)**; the earlier Phase 13 deployment was cancelled
  and never created. Artifacts follow `.agents/skills/bintanong-phase-handoff/references/artifact-contract.md`:
  `plans/phase-13-hosted-llm-agent-plan.md` (this plan, with frontmatter, `previous_handoff: plans/phase-12-handoff.md`),
  `plans/phase-13-checkpoint.md`, later `plans/phase-13-handoff.md`; `plans/INDEX.md` and
  `plans/plan_current_progress/current_progress.md` updated. Run `phase_state.py inspect` at start and
  `validate` / `can-advance` at the end. Thesis pp. 17-18 and the routing PNG are re-read at phase start and
  the discrepancy (hosted LLM, LLM-judged retrieval) is recorded in the checkpoint.
- Checkpoint is updated after every task commit. Checkpoint, not chat, carries resumable state.
- Branches: integration branch `feat/hosted-llm-agent` cut from `Lawrens16/dev`. One short branch per milestone,
  merged into the integration branch by PR on `origin` after its reviewer passes:
  `feat/agent-providers` (Task 2), `feat/agent-corpus-search` (Task 3), `feat/agent-curriculum-tools` (Task 4),
  `feat/agent-loop-guards` (Task 5), `feat/agent-api` (Tasks 6-7), `feat/agent-deploy` (Task 8).
  Tasks 2, 3 and 4 are independent and may run in parallel subagents, each in its own worktree
  (`using-git-worktrees`). A tag `agent-m<N>` after each merge gives a rollback point.

## File structure

| File | Responsibility |
|---|---|
| `backend/bintanong_agent/providers.py` | `ChatModel` protocol, `OpenAICompatibleModel`, `AnthropicModel`, `ModelTurn`, `ToolCall` |
| `backend/bintanong_agent/settings.py` | `AgentSettings.from_env()`, `build_model(settings)` |
| `backend/bintanong_agent/corpus.py` | `Corpus`: release chunks as readable passages, short ids, neighbours, topic directory |
| `backend/bintanong_agent/search.py` | `SearchBackend`, `KeywordSearch` (BM25), `VectorSearch` (existing encoder + RPC) |
| `backend/bintanong_agent/curriculum.py` | `find_courses`, `CurriculumTools` over the existing symbolic adapter |
| `backend/bintanong_agent/tools.py` | Tool JSON schemas and `ToolRunner.run(name, arguments, turn)` |
| `backend/bintanong_agent/prompt.py` | `SYSTEM_PROMPT`, `build_messages(history, question, scope)` |
| `backend/bintanong_agent/guards.py` | The four guards |
| `backend/bintanong_agent/agent.py` | `Agent.answer(...) -> AgentAnswer` |
| `backend/bintanong_api/agent_turns.py` | Chat port: session history in, committed exchange out |
| `backend/bintanong_api/agent_app.py` | `load_agent_app()` uvicorn factory |
| `tests/test_agent_*.py` | One test file per module above |
| `docker/agent-api.Dockerfile`, `render.yaml`, `docs/development/hosted-agent-deploy.md` | Deployment |

## Tasks

### Task 0: Records and PRD

- [ ] Run `python -B .agents/skills/bintanong-phase-handoff/scripts/phase_state.py inspect --repo .`; note output.
- [ ] Read thesis physical pp. 17-18 (`pdftotext -f 17 -l 18 -layout`) and view the routing PNG.
- [ ] Create branch `feat/hosted-llm-agent` from `Lawrens16/dev`.
- [ ] Write the PRD with `create-prd` at `plans/2026-11-15-hosted-llm-fork-prd.md` (goals, non-goals, the
  acceptance criteria below, risks). Show the owner a short summary and get approval.
- [ ] Save this plan as `plans/phase-13-hosted-llm-agent-plan.md` with frontmatter; create
  `plans/phase-13-checkpoint.md`; update `plans/INDEX.md` and current progress.
- [ ] Add a "Fork: hosted-LLM agent, owner decisions 15 November 2026" section to `AGENTS.md` and
  `plans/owner-decisions-ledger.md`: in this fork these decisions supersede the Gemma-only, strict-guard and
  thesis-technology rules; the database rule and guard list are recorded verbatim.
- [ ] Record the hosting research (Render 512 MB, Hugging Face paid, Vercel 300 s) in
  `plans/2026-11-15-phase-13-pre-phase-research.md` with source links.
- [ ] `phase_state.py validate`; commit `docs(plans): open phase 13 hosted-llm agent fork`.

### Task 1: Feasibility probes (read-only; no production code)

Scripts live in an ignored `audit-evidence/p13-probes-20261115/` folder. Each result goes in the checkpoint.

- [ ] **Chunks:** with the anon key, call the existing `load_document_snapshot(client, release_id=..., authorization_ref=...)`
  (`backend/bintanong_api/hosted_snapshot.py:11`) against the active research release; record chunk count
  (expect 560), which fields are readable, and the time taken.
- [ ] **Topic directory:** check whether chunk rows alone give usable topic names (`type_fields.reading_id`,
  service titles, headings). The 145-topic catalogue is in the local sealed package, not Supabase. If rows are
  not enough, the fallback is a small derived file (topic id, label, chunk ids; no source text) supplied as a
  Render secret file. Show the owner a sample of each option and record the choice.
- [ ] **Memory:** measure process RSS after loading FastAPI + 39 curriculum bundles + the corpus. If above
  400 MB, Task 4 loads each curriculum on first use.
- [ ] **Prolog image:** check which SWI-Prolog package `janus-swi 1.5.3` accepts on Debian bookworm versus the
  source build in `docker/api.Dockerfile`; record the choice for Task 8.
- [ ] **Provider docs:** read current DeepSeek, OpenAI, Gemini (OpenAI-compatible) and Anthropic tool-calling
  docs via Context7/official pages; record base URLs, current model ids and request shapes in the checkpoint.
- [ ] Commit the checkpoint update `docs(plans): record phase 13 feasibility probes`.

### Task 2: Providers and settings

**Files:** create `backend/bintanong_agent/__init__.py`, `providers.py`, `settings.py`; test
`tests/test_agent_providers.py`, `tests/test_agent_settings.py`.

**Produces:**

```python
@dataclass(frozen=True)
class ToolCall: id: str; name: str; arguments: dict
@dataclass(frozen=True)
class ModelTurn: text: str; tool_calls: tuple[ToolCall, ...]
class ChatModel(Protocol):
    async def complete(self, messages: list[dict], tools: list[dict], *, max_output_tokens: int = 2048) -> ModelTurn: ...
class OpenAICompatibleModel:  # __init__(base_url, api_key, model, *, timeout_seconds=60, client=None)
class AnthropicModel:         # __init__(api_key, model, *, timeout_seconds=60, client=None)
@dataclass(frozen=True)
class AgentSettings: provider: Literal['deepseek','openai','gemini','anthropic']; model: str; api_key: str
    @classmethod
    def from_env(cls, env=os.environ) -> 'AgentSettings'
def build_model(settings: AgentSettings) -> ChatModel
```

Messages use the OpenAI chat shape (`role`, `content`, `tool_calls`, `tool` results); `AnthropicModel` converts.
Failures raise the existing `RuntimeFailure` (`backend/bintanong_routing/transport.py`) with codes
`model_timeout`, `model_connection_error`, `model_http_error`, `invalid_server_response`.
Env: `BINTANONG_LLM_PROVIDER` (default `deepseek`), `BINTANONG_LLM_MODEL` (default per provider from Task 1),
`DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`.

- [ ] Tests first (fake `httpx` client, as `tests/test_routing_transport.py` does):
  `test_openai_compatible_sends_tools_and_parses_tool_calls`, `test_openai_compatible_parses_plain_text`,
  `test_anthropic_converts_tool_results_and_parses_tool_use`, `test_timeout_maps_to_model_timeout`,
  `test_http_429_maps_to_model_http_error`, `test_malformed_tool_arguments_become_invalid_server_response`,
  `test_from_env_requires_key_for_selected_provider` (raises `ValueError('llm_api_key_required')`),
  `test_build_model_uses_provider_base_url` (one case per provider), `test_api_key_never_in_repr`.
- [ ] Run; expect import failures (RED). Implement. Run; expect pass. Commit `feat(agent): add hosted model providers`.

### Task 3: Corpus and search

**Files:** create `corpus.py`, `search.py`; test `tests/test_agent_corpus.py`, `tests/test_agent_search.py`.

**Consumes:** snapshot dict from `load_document_snapshot` (`chunks`, `versions`);
`render_reviewed_policy_context` (`backend/bintanong_contracts/reviewed_policy_context.py`).

**Produces:**

```python
@dataclass(frozen=True)
class Passage: short_id: str; chunk_id: str; title: str; source: str; page: int | None; text: str
               limits: tuple[str, ...]; neighbour_ids: tuple[str, ...]   # short ids
@dataclass(frozen=True)
class Topic: topic_id: str; label: str; passage_ids: tuple[str, ...]
class Corpus:
    @classmethod
    def from_snapshot(cls, snapshot: dict, topic_index: dict | None = None) -> 'Corpus'
    passages: tuple[Passage, ...]; topics: tuple[Topic, ...]
    def get(self, short_id: str) -> Passage            # KeyError when unknown
    def with_neighbours(self, short_ids: Iterable[str]) -> tuple[Passage, ...]
    def directory(self) -> str                           # compact topic list for the system prompt
class SearchBackend(Protocol):
    async def search(self, query: str, *, top_k: int = 8) -> tuple[Passage, ...]: ...
class KeywordSearch:   # __init__(corpus); BM25 (k1=1.5, b=0.75) over title + text, casefolded word tokens
class VectorSearch:    # __init__(corpus, encoder, client, release_id); existing QueryEncoder + retrieve_context RPC
```

Short ids are `C001`.. in sorted `chunk_id` order. `top_k` is clamped to 1..8.

- [ ] Tests first (synthetic chunks): `test_short_ids_are_stable_and_sorted`,
  `test_passage_text_keeps_field_names_and_source_limits`, `test_with_neighbours_adds_required_neighbours_once`,
  `test_directory_lists_every_topic`, `test_keyword_search_ranks_matching_passage_first`,
  `test_keyword_search_returns_empty_for_no_overlap`, `test_top_k_is_clamped_to_eight`,
  `test_vector_search_passes_stored_embedding_configuration` (fake encoder and client; asserts only an RPC read).
- [ ] RED, implement, GREEN. Commit `feat(agent): add read-only corpus and keyword search`.

### Task 4: Curriculum tools

**Files:** create `curriculum.py`; test `tests/test_agent_curriculum.py`.

**Consumes:** `MultiCurriculumSymbolicAdapter.execute(request, context)` (`backend/bintanong_orchestration/adapters.py:231`),
`PredicateRequest` / `RequestContext` contracts, the research catalog aliases built by
`build_multi_research_resources` (`backend/bintanong_runtime/research.py`), `load_release_curricula`.

**Produces:**

```python
@dataclass(frozen=True)
class CourseMatch: course_id: str; printed_code: str; title: str | None
def find_courses(catalog, curriculum_id: str, text: str, *, limit: int = 5) -> tuple[CourseMatch, ...]
class CurriculumTools:   # __init__(symbolic, catalog)
    async def prerequisite_check(self, curriculum_id, program_id, course_id, facts) -> dict
    async def course_facts(self, curriculum_id, program_id, course_id) -> dict
    async def term_courses(self, curriculum_id, program_id, year, term) -> dict
    async def affected_courses(self, curriculum_id, program_id, course_id) -> dict
```

`find_courses` compares after removing spaces, dashes, dots and a trailing `/L`, casefolded, against printed
codes and titles; exact normalized code first, then prefix, then title-word overlap. It returns candidates;
it never refuses. `prerequisite_check` returns `{course, printed_rule, evaluation: met|not_met|unknown,
unmet, unknown_facts, limits}` built from the Prolog result, as data for the LLM to read.

- [ ] Tests first (existing synthetic runtime fixtures): `test_find_courses_ignores_spacing_dash_and_lab_suffix`
  (`"cc5"`, `"CC-5"`, `"cc 5/l"` all return printed `CC 5/L` first), `test_find_courses_matches_title_words`,
  `test_find_courses_returns_several_candidates_when_ambiguous`, `test_find_courses_empty_for_nonsense`,
  `test_prerequisite_check_reports_met_not_met_and_unknown_separately`,
  `test_prerequisite_check_uses_only_session_facts`, `test_blank_prerequisite_reported_as_none`.
- [ ] RED, implement, GREEN. Commit `feat(agent): add forgiving course lookup and rule tools`.

### Task 5: Tools, prompt, guards, agent loop

**Files:** create `tools.py`, `prompt.py`, `guards.py`, `agent.py`; test `tests/test_agent_tools.py`,
`tests/test_agent_guards.py`, `tests/test_agent_loop.py`.

**Consumes:** Tasks 2-4; `EXCLUDED_PROGRAM_CUES` (`backend/bintanong_routing/router.py:147`), `foreign_ids`.

**Produces:**

```python
@dataclass
class TurnState: program_id: str | None; curriculum_id: str | None; facts: tuple
                 fetched: dict[str, Passage]; rule_checks: list[dict]
class ToolRunner:   # __init__(search: SearchBackend, corpus: Corpus, curriculum: CurriculumTools)
    schemas: list[dict]   # search_documents, open_topic, find_course, check_prerequisite,
                          # course_facts, list_term_courses, list_affected_courses
    async def run(self, name: str, arguments: dict, state: TurnState) -> str   # JSON text; errors as {"error": ...}
@dataclass(frozen=True)
class AgentAnswer: status: Literal['answered','clarification_needed','out_of_scope','insufficient_evidence',
                                   'temporarily_unavailable']
                   text: str; language: Literal['english','taglish']; citations: tuple[Passage, ...]
                   used_rules: bool
class Agent:   # __init__(model: ChatModel, tools: ToolRunner, *, max_rounds: int = 6)
    async def answer(self, question: str, history: list[dict], state: TurnState, progress=lambda stage: None) -> AgentAnswer
```

The final model turn is JSON: `{"kind": "answer"|"clarify"|"chat"|"out_of_scope", "language", "text",
"citations": ["C012"], "eligibility": bool}`. `guards.py`: `excluded_audience(question) -> bool`;
`citation_errors(final, state) -> list[str]` (`uncited_policy_answer`, `unknown_citation`);
`eligibility_errors(final, state)` (`rules_not_consulted` when `eligibility` is true and `state.rule_checks` is
empty); `private_leak(text, state)`. One repair round feeds the error codes back to the model; a second
failure returns the fixed fallback reply. Progress stages: `searching`, `checking`, `writing`.

- [ ] Tests first (scripted fake `ChatModel`): `test_search_tool_records_fetched_passages`,
  `test_unknown_tool_name_returns_error_json`, `test_bad_arguments_return_error_json`,
  `test_check_prerequisite_without_curriculum_returns_scope_needed`, `test_answer_with_fetched_citation_passes`,
  `test_unknown_citation_is_repaired_once_then_falls_back`, `test_uncited_policy_answer_falls_back`,
  `test_chat_kind_needs_no_citation` (greeting), `test_eligibility_without_rule_tool_is_repaired`,
  `test_eligibility_wording_is_left_to_the_model` (any text passes once the tool was called),
  `test_excluded_audience_question_never_reaches_the_model`, `test_private_grade_not_in_citations`,
  `test_loop_stops_at_max_rounds`, `test_model_failure_returns_temporarily_unavailable`,
  `test_history_is_sent_before_the_question`.
- [ ] RED, implement, GREEN. Commit `feat(agent): add tool-using chat loop with guards`.

### Task 6: API composition and stream

**Files:** create `backend/bintanong_api/agent_turns.py`, `agent_app.py`; test `tests/test_api_agent_turns.py`,
`tests/test_api_agent_app.py`. No edit to `chat.py` or `stream.py` unless a shared helper must be widened; any
such edit keeps existing tests green.

**Consumes:** `create_app`, `ApiServices`, `ApiSettings` (`backend/bintanong_api/app.py`), `SessionStore`,
`chat_stream` / `answer_parts` (`stream.py`), `SupabaseAuth`, `SupabaseStorageClient`, `_public_key` check
(`research_app.py:68`), `load_release_curricula`, `extract_isolated`.

**Produces:** `AgentTurns` with the same `prepare(request)` / `run(session, turn, progress)` surface as
`ChatTurns`, returning an object `answer_parts` accepts; `load_agent_app()` reading only env
(`SUPABASE_URL`, `SUPABASE_ANON_KEY`, provider vars, `BINTANONG_ALLOWED_ORIGINS`, `BINTANONG_ALLOW_GUESTS`,
`BINTANONG_RELEASE_ID`, `BINTANONG_RESEARCH_AUTHORIZATION`, optional `BINTANONG_TOPIC_INDEX`,
optional `BINTANONG_VECTOR_SEARCH=1`). Readiness = Supabase read + `probe_janus()`.

- [ ] Tests first: `test_turn_commits_exchange_and_history_reaches_next_turn`,
  `test_failed_turn_commits_nothing`, `test_stream_emits_status_text_sources_and_answer_parts`,
  `test_sources_endpoint_serves_cited_passage`, `test_app_refuses_service_role_key`,
  `test_app_starts_without_model_url_or_encoder`, `test_no_supabase_write_method_is_called` (spy client
  records every call; all are `select` or the read RPC).
- [ ] RED, implement, GREEN. Run the existing `tests/test_api_*.py` to show the original path is intact.
  Commit `feat(api): serve the hosted agent`.

### Task 7: Frontend labels

**Files:** modify `frontend/lib/student-transport.ts` and the status component under
`frontend/components/workspace/` for the stages `searching`, `checking`, `writing`, and a "waking up" line
when the first response takes over 10 s; tests beside the existing transport tests.

- [ ] Test first (`npm run test:ui` pattern), implement, pass; `npx tsc --noEmit`. Commit
  `feat(frontend): show agent progress stages`.

### Task 8: Local live check, image, deploy

- [ ] Owner puts the DeepSeek key in the ignored `.env`. Start `load_agent_app` with uvicorn and `next dev`.
- [ ] Ask the 12 live questions (Verification below); read each answer against its cited chunks; save the
  transcript in ignored audit-evidence; record results in the checkpoint. Fix defects test-first.
- [ ] Repeat a 4-question subset with each other provider whose key the owner supplies.
- [ ] Create `docker/agent-api.Dockerfile` (no torch), `render.yaml`, `.env.example` additions,
  `docs/development/hosted-agent-deploy.md`. Build and run the image locally; `/health/ready` returns 200;
  record memory use. Commit `build(agent): add container image and render blueprint`.
- [ ] With the owner: create the Render service and Vercel project, set env vars, deploy; check
  `/health/ready`, one chat through the Vercel URL, and the cold-start time.

### Task 9: Close the phase

- [ ] Full exit-gate verification (below). `requesting-code-review` on the integration branch.
- [ ] Write `plans/phase-13-handoff.md`; mark the checkpoint `superseded`; update `plans/INDEX.md`, README
  (new run path) and current progress; `phase_state.py validate` and `can-advance`.
- [ ] `finishing-a-development-branch`: PR `feat/hosted-llm-agent` -> `Lawrens16/dev` on `origin`.

## Acceptance criteria (exit gate)

- With `SUPABASE_URL`, `SUPABASE_ANON_KEY` and one provider key, the agent app starts with no GPU, no Gemma
  container, no encoder and no local sealed package.
- Switching provider is an env change; all four pass the same provider tests.
- Follow-ups use chat history; greetings and small talk get natural replies.
- Loosely typed course names resolve; eligibility replies follow the rule tool's result.
- Each guard has a RED-then-GREEN test and holds in the live check.
- No request path issues a Supabase write; the service-role key is never read.
- Original `research_app` path and its tests unchanged and passing.
- Backend fits Render free memory, or curricula load on first use.

## Verification

- `tests/test_agent_*.py` and `tests/test_api_agent_*.py`, then the existing routing, generation, orchestration
  and API test files. The full suite's known environmental baseline is 82 failures and 9 collection errors;
  compare failure lists against it rather than reading them as regressions.
- Frontend `npm run test:ui` and TypeScript check.
- Live, 12 questions from `docs/evaluation/benchmark-questions.md` in English, Tagalog and Taglish: two
  procedures, a fee, a grading question, a prerequisite check typed loosely ("pwede ba ko mag cc5?"), a failed
  course follow-up, a mixed course + procedure message, a follow-up that relies on the previous turn, a greeting,
  a graduate-program question, a question with no supporting chunk, a source-conflict topic. Results are
  development checks, not an accuracy claim, and do not inherit the thesis evaluation figures.
- Supabase MCP, read-only: row counts of `chunks`, `chunk_embeddings`, `knowledge_releases`, `active_release`
  before and after the live run are identical.

## Risks

- Keyword search can miss a chunk that shares no words with the question; the topic directory and the
  agent's English re-queries reduce this, and vector search remains the local fallback.
- Render free: sleeps after 15 minutes idle (about 1 minute to wake), 0.1 CPU; Prolog runs as a subprocess and
  may be slow. Measured in Task 8.
- Sessions live in one process; a Render restart clears chats. Accepted, since the fork must not write to the
  database.
- The fork reads whichever release the original system keeps active.
- With guard 1 loosened, an eligibility reply can be worded wrongly by the model; the live check reads every
  eligibility answer against the tool result.
