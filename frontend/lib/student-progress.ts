// Progress stages the API may send while an answer is prepared, and the line shown for each.
export const progressStages = ["waiting", "understanding", "searching", "checking", "writing"] as const;
export type ProgressStage = (typeof progressStages)[number];

const labels: Record<ProgressStage, string> = {
  waiting: "Waiting for a free answer slot… You can stop waiting.",
  understanding: "Checking the information for your question…",
  searching: "Searching the university documents…",
  checking: "Checking the curriculum rules…",
  writing: "Preparing the response…",
};

export const CONNECTING = "Connecting…";
// A hosted server that was idle needs time to start before it sends anything.
export const WAKING_UP_AFTER_MS = 10_000;
// Render free sleeps after 15 quiet minutes; waking took 90-100 s when measured on 16 Nov 2026.
export const WAKING_UP = "Waking up the server… The first reply after a quiet period can take up to 2 minutes.";

/** The program picker's loading line after `elapsedMs` of waiting for the list. */
export function programListText(elapsedMs: number): string {
  return elapsedMs < WAKING_UP_AFTER_MS ? "Loading programs…"
    : "Waking up the server… Loading the program list can take up to 2 minutes after a quiet period.";
}

export function progressLabel(stage: ProgressStage): string {
  return labels[stage];
}
