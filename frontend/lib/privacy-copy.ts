// Owner, 15 Nov 2026 (hosted-LLM fork): answers use a third-party AI service, so Bintanong accepts no grade files
// and asks students not to type grades or identity; a course check needs only passed / failed / not taken.
export const UPLOADS_ENABLED = false;

// Owner, 16 Nov 2026: the site stays public for now; the school sign-in is kept switched off (see auth-policy.ts).
export const privacyNoticeBody =
  "Bintanong follows the Data Privacy Act of 2012 (Republic Act No. 10173). Your questions are answered with help " +
  "from a third-party AI service. Don't enter your name, student number, grades or other personal details; just say " +
  "whether you passed, failed or haven't taken a course. Bintanong doesn't save your chats; they are cleared when " +
  "your session ends.";

export const informationAnswer =
  "No account is needed. Each browser can ask a limited number of questions each day; an anonymous browser cookie " +
  "with no personal details counts them. Your questions are answered with help from a third-party AI service, so " +
  "don't enter your name, student number, grades or other personal details; just say whether you passed, failed or " +
  "haven't taken a course. Bintanong doesn't save your chats: they stay in temporary memory and clear when you start " +
  "a new chat or your session ends.";

// Parked with the sign-in, for when it is switched on: Google gives Supabase the name, school email and profile photo
// link; the job in `supabase/hosted/` deletes the record 7 days after the last sign-in. When switching sign-in on,
// add `signInRecord` to the notice and FAQ as well (see the parked-sign-in plan).
export const DATA_CONTACT = "bintanongbinturong@gmail.com";
export const signInRecord =
  "Sign-in keeps your name, school email address and Google profile photo link, only to confirm you're a PSU student " +
  "and to count your daily questions. It's deleted automatically 7 days after you last sign in; to see or delete it " +
  `sooner, email ${DATA_CONTACT}. Your sign-in details are not shared with the AI service.`;

/** Shown under the sign-in button. */
export const signInNotice = signInRecord + " Chats stay temporary.";
