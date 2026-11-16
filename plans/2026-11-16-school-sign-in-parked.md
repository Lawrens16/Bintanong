# School sign-in: built, tested, switched off (parked 16 November 2026)

Owner, 16 Nov 2026: "can we just scrap that login thing, dont entirely scrap it but save it somewhere if i've finally
made up my mind in implementing this login thing, for now keep it public." The site is public; this note is how to
switch the sign-in on later. Decisions already made for it (do not re-ask): PSU Google accounts only, no guest
chat, 20 questions per person and 150 per site per day, sign-in records deleted 7 days after last use, data
requests to bintanongbinturong@gmail.com. [Security plan](2026-11-16-hosted-agent-security-plan.md),
[results](2026-11-16-hosted-agent-security-results.md), ledger entries of 16 Nov.

Last commit with sign-in fully on: `5801c990` (`git show 5801c990:frontend/lib/privacy-copy.ts` has its notice).

## What stays on while the site is public

Daily limits (20 per browser, 150 for the site), the 1,000-character question limit, the 64 KB request limit, no
public API description, and the three browser security headers. Guests are counted by an anonymous browser cookie,
so a script that sends no cookie is a new "person" on every request; only the site cap of 150 a day then limits it.

## Switching it on (in this order)

1. Code (test-first, small commit):
   - `frontend/lib/auth-policy.ts`: `SIGN_IN_ENABLED = true`, `GUESTS_ALLOWED = false`; flip `tests/page-access.test.mjs`.
   - `frontend/lib/privacy-copy.ts`: add `signInRecord` to `privacyNoticeBody` and `informationAnswer`, and replace
     "No account is needed" / the browser-cookie sentence (as at `5801c990`); update `tests/privacy-copy.test.mjs`.
   - `render.yaml`: remove `BINTANONG_ALLOW_GUESTS`.
2. Vercel, Production environment: `NEXT_PUBLIC_SUPABASE_URL=https://jyrudbiuajahsucsorco.supabase.co`,
   `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (the public `sb_publishable_...` key), `SITE_ORIGIN=https://bintanong.vercel.app`.
   These are built into the page, so redeploy after adding them. Missing on 16 Nov: the sign-in button showed
   "unavailable" and nobody could chat.
3. Supabase, Authentication -> URL Configuration: Site URL `https://bintanong.vercel.app`, or add
   `https://bintanong.vercel.app/auth/callback` to Redirect URLs. Google sign-in is already enabled there.
4. Supabase: apply `supabase/hosted/2026-11-16-delete-unused-sign-ins.sql` (pg_cron + one cleanup job) so the
   notice's 7-day promise is true. Removed on 16 Nov when sign-in was parked.
5. Render: delete `BINTANONG_ALLOW_GUESTS`, then deploy by hand, together with or before the Vercel deploy.
6. Check live: `/chat` redirects to `/login`; a school account can ask; a personal Gmail is refused; a direct
   `POST /chat` to Render with a typed-in Origin and no sign-in returns 401.
