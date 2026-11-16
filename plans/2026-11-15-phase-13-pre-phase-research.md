# Phase 13 pre-phase research: free hosting for the hosted-LLM fork, 15 November 2026

Bounded to the [Phase 13 plan](phase-13-hosted-llm-agent-plan.md): where a $0, no-card deployment can run and
what that forces in the design. Sources re-checked by web search on 15 November 2026. Provider API details
(base URLs, model ids, tool-call shapes) are a Task 1 probe and are recorded in the checkpoint, not here.

## 1. What already exists (do not repeat)

- Hosted research release with 560 chunks, readable with the anon key (`backend/bintanong_api/hosted_snapshot.py`).
- 39 reviewed curriculum bundles and the Prolog adapter (`backend/bintanong_orchestration/adapters.py`).
- FastAPI app, sessions, uploads, stream and the Next.js UI (Phase 11).
- Latency profile: the original path is about 10 Gemma calls per message on a local GPU.

## 2. Findings

| Question | Evidence | Consequence |
| --- | --- | --- |
| Backend host at $0 | Render free web service: spins down after 15 minutes without inbound traffic; waking "takes about one minute"; 750 free instance hours per workspace per month; filesystem is ephemeral; Render may restart a free service at any time ([Deploy for Free](https://render.com/docs/free)). Instance list gives Free as 512 MB RAM / 0.1 CPU ([Render docs mirror](https://render.com/docs/llms-full.txt)). | Backend must fit 512 MB with no model weights. Sessions in memory are lost on restart (accepted: the fork must not write to the database). UI shows a "waking up" line. |
| Conflicting Render figure | One mid-2026 blog lists Free as 256 MB ([jwatte.com review](https://jwatte.com/blog/render-com-platform-review/)); not confirmed by an official page. | Unverified. Task 1 measures memory; Task 8 reads the instance size shown in the Render dashboard before deploying. |
| Embedder online | SEA-LION E5 600M needs about 2.5-3 GB loaded (Phase 3/5 handoffs). Hugging Face: Gradio and Docker Spaces now need a paid plan to create (PRO for personal accounts); only static Spaces stay free ([Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview), [forum thread](https://discuss.huggingface.co/t/docker-sdk-now-marked-as-paid-when-creating-a-new-space/177580/5)). | No free host fits the embedder. Online retrieval = topic directory + keyword search over the same chunks; vector search stays behind the same interface for the laptop. |
| Frontend host at $0 | Vercel Hobby functions: 300 s default and maximum with Fluid compute ([limits](https://vercel.com/docs/functions/limitations), [changelog](https://vercel.com/changelog/higher-defaults-and-limits-for-vercel-functions-running-fluid-compute), [Hobby plan](https://vercel.com/docs/plans/hobby)). | A proxied chat stream that waits about 1 minute for Render to wake plus the answer fits inside 300 s. |

## 3. Options and recommendation

| Option | Gain | Cost / risk | Recommendation |
| --- | --- | --- | --- |
| Vercel Hobby + Render free + hosted LLM API, keyword search | $0, no card, no GPU | Cold start about 1 minute; 0.1 CPU; keyword search can miss chunks with no shared words | **Chosen by the owner, 15 Nov 2026** |
| Hugging Face Docker Space with the embedder | Vector search online | Needs a paid plan | Not taken |
| Paid GPU host for the original Gemma path | Thesis stack online | Monthly cost | Not taken |

Build-speed notes: Tasks 2 (providers), 3 (corpus/search) and 4 (curriculum tools) share no state and can run
in parallel subagents; the API reuses `create_app`, `SessionStore`, `chat_stream` and the existing test fakes.

## 4. Limits of this research

Free-tier terms change; figures above are as read on 15 November 2026 and are re-read at deploy time.
Research proposes; the hosted model, keyword retrieval and loosened guard 1 rest on the owner's 15 November
2026 fork decisions, recorded in `AGENTS.md` and `plans/owner-decisions-ledger.md`.
