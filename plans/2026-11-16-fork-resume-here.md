# Resume here: hosted-LLM fork (state at 16 November 2026, 22:45)

Owner, 16 Nov: "just note that whenever someone is gonna work in this project again, because i will be back on
this maybe a week later." Read this first, then `plans/INDEX.md` and current progress. Check Git and the live site
before trusting anything below; it is a snapshot.

## Raise with the owner at the start of every session (owner, 16 Nov 2026)

**Keep-awake pinger for Render (not done yet).** Owner: "bring this up whenever i start another session in this
project ... because option 1 is a good idea". Render free sleeps after 15 quiet minutes and the first request
then waits 90-100 s (the program list showed "Loading programs…" that long). Fix: a free cron-job.org job opens
`https://bintanong-agent-api.onrender.com/health/live` every 10 minutes (one always-on service fits Render's 750
free hours a month). Needs the owner to create the cron-job.org account; give them the exact settings. Remove
this section once it is set up. (The site now explains the wait after 10 s; that is a stopgap, not the fix.)

## Where things stand

- **Live and public:** https://bintanong.vercel.app (Vercel) with the backend on Render free
  (https://bintanong-agent-api.onrender.com). Guests chat without signing in. Both run branch
  `feat/hosted-llm-agent` at `6edfc3c7` or later. Last live check 16 Nov 22:40: a guest question answered in 3.9 s.
- **On:** daily limits (20 questions per browser, 150 for the whole site, rolling 24 hours, counted in server
  memory, reset when Render sleeps or restarts), 5 per 5 minutes, 1,000-character question limit, 64 KB request
  limit, no public API description, three browser security headers, no grade uploads, personal details removed
  before text reaches the model.
- **Parked (built, tested, switched off):** PSU Google sign-in only. Every step to switch it on, and the decisions
  already made for it, are in [the parked note](2026-11-16-school-sign-in-parked.md). Do not re-ask those decisions.
- **Supabase:** unchanged from before 16 Nov (the cleanup job was added and then removed the same day). The app
  reads with the public key only. One old sign-in record (last used 31 Oct) exists.
- **Model:** DeepSeek `deepseek-flash`, thinking off, about $0.001 per question. The owner's prepaid balance was
  $1.41 on 15 Nov; check it in the DeepSeek console before more live testing.

## Open items (none blocking)

1. `main` is behind: PR #1 was merged into `main` at `7cff92c2` before the 16 Nov work. The site deploys from
   `feat/hosted-llm-agent`, so it is unaffected. Open a second PR when the owner wants `main` current.
2. Known gap in public mode: a script calling Render directly with a typed-in `Origin` and no cookie counts as a new
   person on every request; only the 150-a-day site cap bounds it. Switching sign-in on closes it.
3. Render free cold start: 90-100 s after sleep; see the keep-awake item at the top.
4. Optional from Phase 13: live-test GPT/Gemini/Claude when a key exists; read Render's Metrics tab under use.
5. Thesis-side items (scorer recall gap, RAGAS decisions, eight-failures handoff) are separate from this fork.

## Working notes for the next session

- Worktree: Orca workspace `Bintanong-personal/dev` (`C:/Users/joel/orca/workspaces/Bintanong-personal/dev`).
  Push only to `origin` (`Lawrens16/Bintanong`), never `upstream`. Render deploys are manual (owner clicks Deploy);
  Vercel redeploys on every push to `feat/hosted-llm-agent`.
- Tests: venv `C:/Coding-projects/bintanong_workspace/audit-evidence/p12-env-20261031/venv`; backend
  `python -m pytest tests/test_agent_*.py tests/test_api_*.py -p no:cacheprovider --basetemp <external folder>`
  (448 pass); frontend `npm run test:ui` with `BINTANONG_TEST_PYTHON` set to that venv's Python (126 pass),
  `npx tsc --noEmit`. Full suite baseline: 233 failed / 36 errors, same ids every run (mostly database tests
  needing a local Supabase); about 25 minutes.
- Local run without Docker: `audit-evidence/p13-security-20261116/start.sh <port> [NAME=value ...]` starts the
  agent app from the ignored `.env`. Start `next dev` with a hidden `Start-Process`, not a background shell (it
  returns 500 otherwise). Stop servers by port.
- Never put pg_cron or `auth`-schema SQL in `supabase/migrations`: storage tests apply that folder to a fresh
  database. Hosted-only SQL lives in `supabase/hosted/`.
- Records: [security plan](2026-11-16-hosted-agent-security-plan.md),
  [results](2026-11-16-hosted-agent-security-results.md), [Phase 13 handoff](phase-13-handoff.md),
  `plans/owner-decisions-ledger.md` (16 Nov entries), fork section of `AGENTS.md`.
