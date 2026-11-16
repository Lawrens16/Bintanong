# PRD: Bintanong fork with a hosted-LLM chat agent

Status: approved by the owner, 15 November 2026 ("I approve the PRD."). It gated Task 2 onward of the
[Phase 13 plan](phase-13-hosted-llm-agent-plan.md). [Hosting research](2026-11-15-phase-13-pre-phase-research.md).

## 1. Summary

A fork of Bintanong that answers students through one chat agent running on a hosted LLM API
(DeepSeek first; GPT, Gemini and Claude by a setting). It reads the same reviewed Supabase chunks and the
same curriculum rules, and it can be put online for $0. The original local Gemma system stays in the
repository, untouched and runnable.

## 3. Background

The original system needs a GPU, a 2.5-3 GB embedding model and local sealed files. It makes up to about
10 Gemma calls per message, and about 30 host modules rewrite the small model's wording. It cannot be hosted
for free, and loosely typed course names ("cc5") can end in "unknown". Hosted models can now call tools and
write natural English and Taglish, so one agent can search, read the rules and word the reply itself.

## 4. Objective

Let a student open a web link and chat with Bintanong without the owner's laptop running.

Key results (checked in the Phase 13 live check; development checks, not an accuracy claim):

1. The backend starts with only `SUPABASE_URL`, `SUPABASE_ANON_KEY` and one provider key: no GPU, no Gemma
   container, no embedder, no local sealed package, and it fits Render free memory (512 MB).
2. 12 of 12 live questions get a reply that matches its cited chunks or the rule tool's result, across
   English, Tagalog and Taglish.
3. Supabase row counts (`chunks`, `chunk_embeddings`, `knowledge_releases`, `active_release`) are identical
   before and after the live run, and no request path issues a write.

## 5. Market segments

- **PalSU undergraduate students** who need a quick answer about a procedure, a fee, a grading rule or
  whether they can take a course, and who type casually in English, Filipino or Taglish.
- **The research team (owner and panel)** who need a link to show the system without a GPU machine.

Constraints: undergraduate academic affairs only; advisory and read-only; $0 hosting, no card; no change to
Supabase; no new Python packages or lock changes.

## 6. Value propositions

**Students**
- Who: undergraduates asking about academic affairs.
- Why: they want the right step or rule without reading the Handbook or Charter.
- What before: the original runs only on the owner's machine, takes many model calls, and rigid wording or a
  missing space in a course code can end in "unknown".
- How: one chat agent that searches the reviewed chunks, reads the curriculum rule and its evaluation, and
  writes the reply itself with citations.
- What after: an online chat that follows up naturally, understands loose course names, and still cites its source.
- Alternatives: ask the office, read the PDFs, or use a general chatbot that does not know PalSU's reviewed
  documents and gives no page reference.

**Research team**
- Who: the owner and reviewers.
- Why: show and test the system anywhere.
- What before: a local stack with Docker, a GPU and about 100 s start-up.
- How: Vercel (frontend) + Render free (backend) + a hosted model, switchable by one setting.
- What after: a shareable link; provider comparison by changing an environment variable.
- Alternatives: keep the laptop demo, or pay for a GPU host.

Statement: Bintanong's reviewed knowledge and rules, answered by a hosted chat agent that any student can
reach from a link, at no hosting cost.

## 7. Solution

### 7.2 Key features

- **Tool-using chat agent** (`backend/bintanong_agent/`): history + question -> hosted model -> tools ->
  reply with citations. The model judges which chunks to use and how to word the reply.
- **Online retrieval:** topic directory + keyword search (BM25) over the same Supabase chunks. Vector search
  stays behind the same interface where the embedder fits (the laptop).
- **Curriculum tools:** forgiving course lookup ("cc5", "CC-5", "cc 5/l", a title) and the existing Prolog
  rule evaluation, returned as data for the model to read.
- **Four provider options:** DeepSeek, OpenAI, Gemini, Anthropic; changed by environment variable.
- **Four code guards:**
  1. Eligibility answers require the curriculum tool to have been called this turn (wording left to the model).
  2. Private grades never appear in citations, source cards or logs.
  3. A policy answer cites at least one chunk fetched this turn; one retry, then "couldn't verify, ask the office".
  4. Medicine, Law, graduate, laboratory school and staff-only questions get the fixed undergraduate-scope notice.
- **Same web UI**, with progress labels (searching, checking, writing) and a "waking up" line.

### 7.3 Technology

Python 3.13, FastAPI, `httpx`, SWI-Prolog via `janus-swi`, Supabase PostgREST with the anon key, Next.js 16.
Replies: English question -> English; Filipino/Taglish -> Taglish.

### 7.4 Assumptions and open questions

- Assumed: the backend with 39 curriculum bundles and 560 chunks fits in 512 MB (measured in Task 1; if not,
  curricula load on first use).
- Settled (owner, 15 Nov): the topic directory comes from the chunk rows (option A); no derived file.
- Assumed: SWI-Prolog installs on the Render image without a source build (Task 1).
- Open: which provider keys besides DeepSeek the owner will supply.
- Known risk: keyword search can miss a chunk that shares no words with the question.
- Known risk: with guard 1 loosened, the model can word an eligibility reply wrongly; every eligibility
  answer in the live check is read against the tool result.
- This fork departs from the thesis-named local model and vector-only retrieval (no k-NN or cosine search
  online). Owner, 15 Nov: it is separate from the thesis and will not be used in the final defense; it is a
  working version that may later be offered publicly as a contribution to the university.

## 8. Release

- **First version:** agent package, API app, frontend labels, local live check with 12 questions, container
  image, Render + Vercel deploy done together with the owner.
- **Later:** other providers' live subsets as keys arrive; vector search online if a free host fits the embedder.
- **Not doing:** any Supabase migration or write; any change to the original Gemma path; new sources or
  scope; saved chat history across restarts; institutional release or accuracy claims; paid hosting.
- **Time:** about one to two weeks of sessions; Tasks 2-4 can run side by side.

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
