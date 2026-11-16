// Owner, 15 Nov 2026 (hosted-LLM fork): answers use a third-party AI service, so Bintanong accepts no grade files
// and asks students not to type grades or identity; a course check needs only passed / failed / not taken.
export const UPLOADS_ENABLED = false;

// Owner, 16 Nov 2026: chatting needs a school Google sign-in. Google gives Supabase the name, school email and
// profile photo link; a scheduled job deletes the record 7 days after the last sign-in. Daily question counts use
// an anonymous account number held in server memory, never the name or email.
export const DATA_CONTACT = "bintanongbinturong@gmail.com";
const signInRecord =
  "Sign-in keeps your name, school email address and Google profile photo link, only to confirm you're a PSU student " +
  "and to count your daily questions. It's deleted automatically 7 days after you last sign in; to see or delete it " +
  `sooner, email ${DATA_CONTACT}.`;

export const privacyNoticeBody =
  "Bintanong follows the Data Privacy Act of 2012 (Republic Act No. 10173). Your questions are answered with help " +
  "from a third-party AI service. Don't enter your name, student number, grades or other personal details; just say " +
  "whether you passed, failed or haven't taken a course. Bintanong doesn't save your chats; they are cleared when " +
  "your session ends. You sign in with your @psu.palawan.edu.ph Google account. " + signInRecord +
  " Your sign-in details are not shared with the AI service.";

export const informationAnswer =
  "You sign in with your @psu.palawan.edu.ph Google account, and each student can ask a limited number of questions " +
  "each day. " + signInRecord + " Your sign-in details are not shared with the AI service. " +
  "Your questions are answered with help from a third-party AI service, so don't enter your " +
  "name, student number, grades or other personal details; just say whether you passed, failed or haven't taken a " +
  "course. Bintanong doesn't save your chats: they stay in temporary memory and clear when you start a new chat or " +
  "your session ends.";

/** Shown under the sign-in button. */
export const signInNotice = signInRecord + " Chats stay temporary.";
