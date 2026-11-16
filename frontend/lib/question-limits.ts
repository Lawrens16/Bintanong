// Owner, 16 Nov 2026 (hosted fork): each person and the whole site have a daily question limit, and a question
// may be at most 1,000 characters. The server enforces all three; this file only words the refusals.
export const MAX_QUESTION_CHARS = 1000;

function wait(seconds: number | null) {
  if (seconds === null) return "Please try again later.";
  const hours = Math.ceil(seconds / 3600), minutes = Math.max(1, Math.ceil(seconds / 60));
  const amount = seconds >= 3600 ? `${hours} ${hours === 1 ? "hour" : "hours"}` : `${minutes} ${minutes === 1 ? "minute" : "minutes"}`;
  return `You can ask again in about ${amount}.`;
}

/** The message for a limit refusal, or null when `code` is not one of them. */
export function limitNotice(code: string, retryAfter: number | null) {
  if (code === "daily_limit_reached") return "You've reached your daily question limit. " + wait(retryAfter);
  if (code === "site_limit_reached") return "Bintanong has reached its question limit for today. " + wait(retryAfter);
  if (code === "message_too_long") return "Your question is too long. Please keep it under 1,000 characters.";
  return null;
}
