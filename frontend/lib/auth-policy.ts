type User = { email?: string; email_confirmed_at?: string | null; identities?: { provider?: string; identity_data?: Record<string, unknown> }[] };
// Owner, 16 Nov 2026 (hosted fork): chatting needs a PSU Google sign-in and there is no guest chat, so one
// person cannot spend the shared model balance. (Sign-in was off from 4 Nov; while false, nobody reaches the
// sign-in page or starts an OAuth flow.) The API enforces the same rule; these only choose pages and controls.
export const SIGN_IN_ENABLED = true;
export const GUESTS_ALLOWED = false;

export function pageRedirect(pathname: string, permitted: boolean, signInEnabled = SIGN_IN_ENABLED, guestsAllowed = GUESTS_ALLOWED) {
  if (pathname === "/login" && !signInEnabled) return "/";
  if (pathname === "/login" && permitted) return "/chat";
  if (pathname === "/chat" && !permitted && !guestsAllowed) return "/login";
  return null;
}

export function isPSUAccount(user: User | null | undefined) {
  const email = user?.email?.toLowerCase();
  return !!email && !!user?.email_confirmed_at && email.split("@").length === 2 && email.split("@")[1] === "psu.palawan.edu.ph"
    && !!user.identities?.some(identity => identity.provider === "google" && identity.identity_data?.email_verified === true
      && typeof identity.identity_data.email === "string" && identity.identity_data.email.toLowerCase() === email);
}
export function siteOrigin(requestUrl: string, configured?: string) {
  const request = new URL(requestUrl);
  if (!configured) {
    if (!["localhost", "127.0.0.1", "[::1]"].includes(request.hostname)) throw new Error("site_origin_required");
    return request.origin;
  }
  const url = new URL(configured);
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/" ||
      (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))) throw new Error("invalid_site_origin");
  return url.origin;
}
