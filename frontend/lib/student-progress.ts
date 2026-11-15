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
export const WAKING_UP = "Waking up the server… The first reply after a quiet period can take about a minute.";

export function progressLabel(stage: ProgressStage): string {
  return labels[stage];
}
