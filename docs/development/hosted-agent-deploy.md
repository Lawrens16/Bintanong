# Deploying the hosted-LLM agent (personal fork)

The fork's backend answers with one tool-using chat agent on a hosted model API (DeepSeek by default) and reads the
same hosted Supabase release as the research build. It needs no GPU, no Gemma container, no embedding model and no
local sealed package. It is separate from the thesis: its results are not thesis results and do not inherit the
thesis evaluation figures. It is not institutional approval or a statement that the sources are current.

Target: backend on Render (free web service, 512 MB), frontend on Vercel (Hobby). Both cost $0 and need no card.

## Boundaries

- **Supabase is read-only.** The app reads with the public anon (publishable) key and refuses a service-role key at
  startup. It issues `select` reads only; it never writes, migrates or calls a writing RPC.
- **Chats live in memory.** A restart or a Render sleep clears sessions and chat history.
- **No grades or identity (owner, 15 Nov 2026).** Grade-file uploads are switched off; email addresses, phone
  numbers and student numbers are removed before text reaches the model; students are asked only whether they
  passed, failed or have not taken a course. Questions and chat history go to the configured model provider
  (currently DeepSeek, `deepseek-flash`); the site's notice describes it generally as a third-party AI service.
- **Model cost.** Each question is a few model calls. Measured on 15 Nov 2026 with `deepseek-flash`, thinking off:
  about $0.001 per question at peak prices, half that off-peak (14 live turns cost $0.0136). Thinking is off unless
  `BINTANONG_LLM_THINKING=1`; it cost 71% more in the same check.

## Environment

| Variable | Value |
| --- | --- |
| `SUPABASE_URL` | Hosted project URL |
| `SUPABASE_ANON_KEY` | Public anon or publishable key (never the service-role key) |
| `BINTANONG_LLM_PROVIDER` | `deepseek` (or `openai`, `gemini`, `anthropic`) |
| `DEEPSEEK_API_KEY` | Provider key; `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` for the others |
| `BINTANONG_LLM_MODEL` | Optional; defaults `deepseek-flash`, `gemini-3.8-flash`, `claude-haiku-5-5`; required for `openai` |
| `BINTANONG_LLM_THINKING` | Optional `1` turns DeepSeek thinking on |
| `BINTANONG_ALLOWED_ORIGINS` | Comma-separated site origins allowed to post, e.g. the Vercel URL (a trailing `/` is ignored) |
| `BINTANONG_ALLOW_GUESTS` | `1` lets visitors chat without signing in |
| `BINTANONG_RELEASE_ID` | `p12-research-faqsplit-20261030` |
| `BINTANONG_RESEARCH_AUTHORIZATION` | `research-owner-20261029` |

The frontend's server-side proxy forwards the browser's `Origin`, so `BINTANONG_ALLOWED_ORIGINS` must list the site
origin students open (the Vercel URL), not the Render URL.

## Run locally

Put the values in the ignored repository-root `.env`, then:

```bash
# backend (Python 3.13 venv with the backend `api` extra and SWI-Prolog 10 installed)
uvicorn --factory backend.bintanong_api.agent_app:load_agent_app --host 127.0.0.1 --port 8022 --env-file .env
# frontend (frontend/.env.local: API_INTERNAL_URL=http://127.0.0.1:8022, SITE_ORIGIN=http://localhost:3217)
cd frontend && npx next dev -p 3217
```

Startup reads the release and all 39 curricula (about 45 s), then `/health/ready` returns 200.

## Container image

`docker/agent-api.Dockerfile` starts from the official `swipl:10.0.2` image, installs Python 3.13 with `uv` and the
backend's locked `api` dependencies (no torch), and compiles `janus-swi` against that SWI-Prolog. Its build context is
limited by `docker/agent-api.Dockerfile.dockerignore` to `backend/` and `knowledge/`, without
`backend/bintanong_tools/` or any ignored dataset folder.

```bash
docker build -f docker/agent-api.Dockerfile -t bintanong-agent-api .
docker run --rm -p 10000:10000 --env-file .env -e BINTANONG_ALLOWED_ORIGINS=http://localhost:3217 bintanong-agent-api
curl http://127.0.0.1:10000/health/ready
```

## Render (backend)

1. Push the branch to the fork (`origin`), never to `upstream`.
2. Render dashboard -> New -> Blueprint -> pick the fork and branch. `render.yaml` defines one free Docker web
   service in Singapore with health check `/health/live` and manual deploys.
3. Enter the `sync: false` values when asked: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DEEPSEEK_API_KEY`,
   `BINTANONG_ALLOWED_ORIGINS` (the Vercel URL; it can be updated after the frontend exists).
4. Deploy, then open `https://<service>.onrender.com/health/ready`.

Render free services sleep after 15 minutes without traffic; the first request then waits for a cold start (startup
alone is about 45 s). The frontend shows a "waking up" line after 10 s.

## Vercel (frontend)

1. New project from the fork, root directory `frontend`.
2. Environment: `API_INTERNAL_URL=https://<service>.onrender.com`, `SITE_ORIGIN=https://<project>.vercel.app`,
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
3. Deploy, then put the Vercel URL in Render's `BINTANONG_ALLOWED_ORIGINS` and redeploy the backend.
