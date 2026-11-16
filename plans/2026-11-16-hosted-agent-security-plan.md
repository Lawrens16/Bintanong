# Hosted agent: sign-in, question limits and security hardening

Status: approved by the owner, 16 November 2026 (plan approval in session). Bounded work on the personal fork
after Phase 13; no Phase 14 is opened. Results: [security results](2026-11-16-hosted-agent-security-results.md)
(written when the checks have run). Not a thesis result, not institutional approval.

## Context

The public site (https://bintanong.vercel.app, backend on Render free) spends the owner's prepaid DeepSeek
balance (about $1.41, roughly $0.001 per normal question). The owner asked whether its security has been
verified and whether a school-only sign-in with a question allowance can stop one person draining the key.

Security had only been covered by unit tests for the four guards, the service-role-key refusal and the origin
check. No dedicated security review of the hosted fork was done. A read-only check on 16 Nov found:

| Finding | Evidence | Severity |
| --- | --- | --- |
| Anyone can ask unlimited questions by calling the Render URL directly | `POST /chat` with a typed-in `Origin: https://bintanong.vercel.app` header and no cookie got past the origin check (422 on an empty body; 403 without the header). Guests are counted by cookie, so a script that sends no cookie is a new "person" every time. Only the 4-at-once slot limit applies | High (drains the balance in under an hour) |
| A signed-in student could still ask 1,440 questions a day | Only limit is 5 per 5 minutes per person (`rate_limit.py`); no daily or whole-site limit | High once sign-in is on |
| Request body is read into memory before any check | No size limit on direct posts to Render; the 32 KB limit exists only in the Vercel proxy | Medium (512 MB server) |
| API description is public | `GET /openapi.json` on Render returns 200 | Low |
| Site sends only one security header | Vercel response has HSTS, no frame / content-type / referrer headers | Low |
| A question may be 8,192 characters, with 6 model rounds | `prepare_query`, `Agent(max_rounds=6)`: a long pasted question costs many times a normal one | Medium for cost |

Already sound (no change): every Supabase table has row-level security and the public key can only read
(Supabase security advisor: one unrelated password warning); service-role key refused at startup; the agent's
tools are read-only; cookies are HttpOnly/Secure/SameSite=Strict; sessions capped at 1,000; the token check in
`backend/bintanong_api/auth.py` already requires a verified Google identity on `@psu.palawan.edu.ph` (an
email/password sign-up with a fake school address is rejected); Google sign-in is still enabled on the Supabase
project and one Google account signed in on 24 Oct.

**The sign-in already exists.** Backend `SupabaseAuth.verify` and the frontend `/login`, `/auth/login`,
`/auth/callback`, `/auth/signout` routes are built and tested; the owner switched them off on 4 Nov
(`SIGN_IN_ENABLED = false` in `frontend/lib/auth-policy.ts`) and Render runs with `BINTANONG_ALLOW_GUESTS=1`.

## Owner decisions (16 Nov 2026)

- Sign-in only: a `@psu.palawan.edu.ph` Google account is required to chat; no guest chat on the hosted site.
- 20 questions per person per day; 150 per day for the whole site; the 5-per-5-minutes limit stays.
- Counts live in the server's memory (no new service, no table). They restart from zero when Render sleeps or
  restarts; accepted. The prepaid balance stays the hard ceiling.
- Consequence to record: sign-in stores each student's school email in Supabase's own sign-in records. This
  amends the fork's "No Supabase change" rule only for those sign-in records and one redirect-URL entry in the
  dashboard; still no migrations, tables, app writes or service-role key. The privacy notice changes to say so.
  The email is never sent to the AI provider (the app keeps only an opaque account id).

## Tasks (each behaviour test-first: failing test, smallest change, rerun)

Branch `feat/agent-sign-in-limits` from `feat/hosted-llm-agent`; small Conventional Commits, no AI attribution.

1. **Records first (docs only).** Repo plan `plans/2026-11-16-hosted-agent-security-plan.md` (this plan plus the
   findings table); amend `plans/2026-11-15-hosted-llm-fork-prd.md` (access, limits, privacy); add the 16 Nov
   entry to `plans/owner-decisions-ledger.md`; one line in the fork section of `AGENTS.md`; update
   `plans/INDEX.md` and current progress. Bounded owner-approved work; no Phase 14 is opened.

2. **Daily limits** (`backend/bintanong_api/rate_limit.py`, `app.py`, `agent_app.py`, `render.yaml`).
   - Reuse `QuestionRateLimit` with a 24-hour window: one instance keyed per person, one with a single
     whole-site key. Add a non-counting `wait(key)` so all three limits are checked before any is counted (a
     question refused by the site cap must not use the person's allowance).
   - `ApiSettings.max_questions_per_day` and `max_questions_per_day_total`, default `None` = off, so the
     original `research_app` path behaves exactly as before.
   - `/chat` returns 429 `daily_limit_reached` or `site_limit_reached` with `retryAfter`.
   - `agent_app.py` reads `BINTANONG_DAILY_QUESTIONS_PER_PERSON` (default 20) and
     `BINTANONG_DAILY_QUESTIONS_TOTAL` (default 150); `render.yaml` lists both.
   - The window is a rolling 24 hours, not a midnight reset.
   - Tests: extend `tests/test_api_rate_limit.py` (fake clock pattern already there) and `tests/test_api_agent_app.py`.

3. **Guests off on the hosted site.** `render.yaml`: remove `BINTANONG_ALLOW_GUESTS`. Add an agent-app test that
   `/chat` and `/curricula` without a token return 401 `sign_in_required` and a non-school token returns 403
   (reuse the `Auth` fake in `tests/test_api_auth.py`). No auth code changes are expected.

4. **Cheaper to attack → harder to attack** (`agent_turns.py`, `app.py`, `agent_app.py`).
   - Question length cap for the agent: 1,000 characters, 422 `message_too_long` (override `AgentTurns.prepare`).
   - Body-size limit before anything is read: reject a `Content-Length` over 64 KB (413) and a body with no
     length (411), as a setting that is off by default and on for the agent app.
   - Agent app serves no `/docs`, `/redoc` or `/openapi.json` (setting, default unchanged for the original path).

5. **Frontend** (`frontend/lib/auth-policy.ts`, `proxy.ts`, `app/login/page.tsx`, `app/page.tsx`,
   `components/workspace/workspace.tsx`, `lib/privacy-copy.ts`, `lib/student-transport.ts`, `next.config.ts`).
   - `SIGN_IN_ENABLED = true`; new `GUESTS_ALLOWED = false`; `pageRedirect` sends `/chat` to `/login` when the
     visitor is not a signed-in school account (`proxy.ts` currently skips the check for `/chat`).
   - Login page: remove "Continue as guest" and the guest wording while guests are off.
   - Workspace: plain messages for `daily_limit_reached` ("You've used today's 20 questions…"),
     `site_limit_reached` and `message_too_long`; these are shown, not auto-retried (only `rate_limited` is);
     input `maxLength` 1,000.
   - Privacy copy: replace "No account is needed" with the school-email sentence; keep the no-grades wording.
   - Headers on every page: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
     `Referrer-Policy: strict-origin-when-cross-origin`.
   - Tests: `auth-policy.test.mjs`, `page-access.test.mjs`, `privacy-copy.test.mjs`, `student-transport.test.mjs`,
     `workspace.test.mjs`.

6. **Attack check on the local container** (script kept in ignored `audit-evidence/`, results written to
   `plans/2026-11-16-hosted-agent-security-results.md`). Costs a few cents of DeepSeek at most.
   - Access: no token, forged origin, garbage token, non-school token, another person's session cookie.
   - Limits: 21st question in a day, 6th in 5 minutes, site cap (run with a small cap), oversized and
     length-less bodies, 1,001-character question.
   - Model manipulation, about 10 prompts: reveal the instructions, ignore the undergraduate scope, answer a
     Medicine/Law/graduate question, invent a citation, claim eligibility without the rule check, print the API
     key or environment. Pass = the four code guards hold and nothing secret appears.
   - Leaks: search responses and container logs for the DeepSeek key, the school email and tokens.
   - Known-vulnerability lists with tools already installed (`npm audit`; a Python audit only if one is already
     in the venv). No installs.
   - Anything that fails becomes a failing test first, then a fix.

7. **Go live (owner steps, each confirmed when it happens).**
   - Supabase dashboard → Authentication → URL Configuration: add `https://bintanong.vercel.app/auth/callback`.
   - Vercel: confirm `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SITE_ORIGIN` are set.
   - Render: delete `BINTANONG_ALLOW_GUESTS`, then start the deploy by hand (the two limits use their defaults).
   - Push the branch to `origin` (first push of a new branch) and merge into `feat/hosted-llm-agent` / PR #1.
   - Live recheck: the forged-origin probe now returns 401; `/openapi.json` 404; a real school sign-in can ask;
     a personal Gmail is refused.

8. **Close.** Results file, current progress, session log; tick the PRD acceptance lines.

## What this does not fix (stated in the results)

- Counts reset when Render sleeps or restarts, so a patient signed-in student can get about 20 extra questions
  per sleep cycle. The site cap resets the same way.
- A flood of junk requests can still slow or wake the free server; Render free has no firewall rules.
- A leaked or shared school account is treated as that student.
- Limits count questions, not cost. With the 1,000-character cap a deliberately heavy question still costs
  several times a normal one, so 150 a day is "about 15 cents normally", not a guaranteed figure.
- No independent (outside) penetration test; this is a development check, not a certification.

## Verification

- Backend: `"C:/Coding-projects/bintanong_workspace/audit-evidence/p12-env-20261031/venv/Scripts/python.exe" -m pytest tests/test_agent_*.py tests/test_api_*.py -p no:cacheprovider --basetemp <external>` (430 pass today), then the
  full suite compared against the known baseline (233 failed / 36 errors, same ids) to show the original path
  is unchanged.
- Frontend: `npm run test:ui` with `BINTANONG_TEST_PYTHON` set to the venv Python (121 pass today) and `npx tsc --noEmit`.
- Local container under `--memory 512m` with guests off: the task 6 script, plus a browser run of sign-in →
  ask → limit message.
- After the owner's deploy: the task 7 live recheck; Supabase read-only check that no table or migration changed.

## Also noted

- Two small-fix commits from today (`146e0a21` trailing slash, `d2639ea6` handoff update) are local, not pushed.
- Render cold start measured today: no answer within 100 s on the first request (longer than the "about one
  minute" estimate); awake on the next request.
