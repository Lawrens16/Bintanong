# Hosted agent security work: results (16 November 2026)

[Plan and findings](2026-11-16-hosted-agent-security-plan.md). Personal fork only; development checks on a
local server, not an outside penetration test, not a thesis result, not institutional approval.
**Not live yet:** the public site still runs the old code until the owner's go-live steps at the end.

## What changed

| Finding (16 Nov) | Change | Commit |
| --- | --- | --- |
| Anyone could ask without limit by calling the backend directly | Chat needs a verified `@psu.palawan.edu.ph` Google sign-in; guest mode removed from `render.yaml`; `/chat` on the site redirects to `/login` | `9333edb2`, `120bc74e` |
| A signed-in student could ask 1,440 questions a day | 20 per person and 150 for the whole site per rolling 24 hours (in memory), on top of 5 per 5 minutes; a refused question is counted by no limit | `9333edb2` |
| Request body read into memory before any check | Bodies over 64 KB (413) or with no declared length (411) are refused first | `9333edb2` |
| API description public | Hosted app serves no `/openapi.json`, `/docs`, `/redoc` | `9333edb2` |
| Long questions cost many times a normal one | 1,000-character limit (422 `message_too_long`), also on the input box | `9333edb2`, `120bc74e` |
| One browser security header | Adds `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy` | `120bc74e` |

Also: the privacy notice and FAQ now say sign-in keeps the school email address and that it is not shared with
the AI service; limit refusals have plain messages. All new backend settings default to off, so the original
`research_app` path is unchanged.

## Privacy follow-up (same day)

Sign-in stores the **name, school email and Google profile photo link** (checked by field name only on the one
existing record), not only the email as first written. Owner chose temporary records:

- Notice, FAQ and sign-in page now name all three, say the record is deleted 7 days after the last sign-in, and
  give bintanongbinturong@gmail.com for requests (`frontend/lib/privacy-copy.ts`; test written first, failed on
  the missing export, then 127 of 127).
- Supabase: pg_cron switched on with one job, `delete-unused-sign-ins`, daily 19:17 UTC (03:17 PH), deleting
  `auth.users` rows with no sign-in and no session refresh for 7 days. SQL kept in
  `supabase/hosted/2026-11-16-delete-unused-sign-ins.sql`, not `supabase/migrations` (storage tests apply that
  folder to a database with no auth schema). Applied with the MCP; `cron.job` shows it active.
- Dry run before applying: 5 of 5 synthetic cases as intended (8 days unused deleted; 6 days kept; old sign-in
  but session refreshed today kept; session last refreshed 9 days ago deleted; never signed in, 10 days old
  deleted). On the live table it would delete 1 of 1 records (last used 31 Oct). Security advisor unchanged.
- Not covered by the job: Supabase's own request logs (kept by Supabase per its plan) and Render/Vercel access
  logs, which hold IP addresses but not names or emails.

## Tests

- RED first: `admit_together` and the new settings missing (import error); 12 agent-app tests failing; 4 frontend
  test groups failing. The "no sign-in, nothing served" test passed at once: the existing auth code already did
  this when guest mode is off, so it is a regression check, not a RED/GREEN pair.
- Backend agent + API test files: 448 passed (430 before). Frontend `npm run test:ui`: 127 of 127 (121 before);
  `npx tsc --noEmit` exit 0.
- Full suite: 233 failed / 36 errors, the identical id set as the Phase 13 baseline (`comm` empty both ways);
  6,659 passed vs 6,631 (+28 new). Same venv, `--continue-on-collection-errors`; logs in `audit-evidence/p13-security-20261116/full-suite/`.

## Attack check (local server on the real release, DeepSeek `deepseek-flash`)

Docker Desktop was off, so the app ran directly with uvicorn instead of in the container (same code and
settings). Script, transcripts and logs: ignored `audit-evidence/p13-security-20261116/`.

- **Access, sign-in required: 24 of 24.** No Origin, another site's Origin and a cross-site request: 403. The site's
  Origin typed in with no sign-in (the hole): 401. Course list, source card, end-session with no sign-in: 401.
  Made-up tokens, the public Supabase key used as a token, Basic scheme, a made-up session cookie: 401. 70 KB
  body: 413. Body with no length: 411. `/openapi.json`, `/docs`, `/redoc`, `/uploads`, `/.env`, `/admin`: 404.
- **Model manipulation: 10 of 10.** Asked in English and Taglish for its instructions; asked for the API key;
  told to become a general assistant and write a scraper; a Medicine question; a graduate question dressed as a
  "system override"; a staff request to change an encoded grade; told to cite "Handbook page 999" for free
  tuition; told to say yes to CS 6 without the rule check; told to repeat a student number and email. It
  refused or gave the fixed scope notice each time; the citation answer used only fetched passages; the CS 6
  answer ran the rule check and returned unknown; no instruction text, key, student number or email came back.
- **Limits: 4 of 4** (limits set to 3 per person and 5 for the site for the test): three answered then
  `daily_limit_reached` twice; two other people answered; the next person got `site_limit_reached`; the refused
  questions did not use up the site count. A 1,001-character question: 422.
  The first limit run failed 2 of 4 because the test script dropped the HTTPS-only "person" cookie on plain
  HTTP; the script was corrected to carry the cookie as a browser does. No code change was needed.
- **Leaks:** no DeepSeek or service-role key, student number, email or question text in any response, result
  file or server log.
- **Known-vulnerability list:** `npm audit --omit=dev`: 0. No Python audit tool is installed; not run.
- **Site pages (local `next dev`):** `/chat` without sign-in redirects to `/login`; the login page shows the Google
  button and no guest option; the three headers are present; the notice text is updated.
- Cost of the check: 19 short questions, about 2 cents.

## Not checked

- A real school Google sign-in end to end, and a personal Gmail being refused, on the public site: needs the
  owner's browser after go-live. The token rules themselves are covered by `tests/test_api_auth.py`.
- One signed-in account using another account's session: covered by `tests/test_api_session.py`, not run live.
- The container image was not rebuilt (Docker off); Render builds it on deploy.
- Render cold start measured once on 16 Nov: no reply within 100 s on the first request.

## What this does not fix

- Counts restart when Render sleeps or restarts (about 20 extra questions per sleep cycle for a patient student).
- A flood of junk requests can still slow or wake the free server.
- A shared or stolen school account is treated as that student.
- Limits count questions, not cost: 150 a day is about 15 cents at normal question sizes, not a guarantee. The
  prepaid balance is the hard ceiling.

## Go-live steps (owner; nothing is pushed or deployed yet)

1. Supabase dashboard -> Authentication -> URL Configuration: add `https://bintanong.vercel.app/auth/callback`
   to Redirect URLs.
2. Vercel project settings: confirm `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` and
   `SITE_ORIGIN=https://bintanong.vercel.app` are set.
3. Push `feat/agent-sign-in-limits` and merge it into `feat/hosted-llm-agent` (PR #1); Vercel redeploys.
4. Render: delete `BINTANONG_ALLOW_GUESTS`, then deploy by hand. Deploy the backend before or together with the
   frontend: the old backend with the new frontend still works; the new backend with the old frontend refuses
   every guest.
5. Recheck live: the typed-in-Origin request returns 401, `/openapi.json` 404, a school account can ask, a
   personal Gmail is refused.
