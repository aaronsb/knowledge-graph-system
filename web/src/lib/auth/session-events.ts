/**
 * Session lifecycle events (ADR-705)
 *
 * Decouples the API client's 401 interceptor from the auth store. The
 * interceptor cannot import the store (the store imports the client), so it
 * signals session transitions via window CustomEvents and the store subscribes.
 *
 *  - `kg:session-expired`   — credentials existed but are now invalid and could
 *                             not be refreshed; the UI should treat the session
 *                             as expired (loud treatment).
 *  - `kg:session-refreshed` — a token refresh succeeded mid-flight; the store
 *                             should re-sync from storage.
 */

export const SESSION_EXPIRED_EVENT = 'kg:session-expired';
export const SESSION_REFRESHED_EVENT = 'kg:session-refreshed';

/** Signal that the session has expired and could not be refreshed. */
export function emitSessionExpired(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
  }
}

/** Signal that an in-flight token refresh succeeded. */
export function emitSessionRefreshed(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(SESSION_REFRESHED_EVENT));
  }
}

/** Subscribe to session-expired; returns an unsubscribe function. */
export function onSessionExpired(handler: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  window.addEventListener(SESSION_EXPIRED_EVENT, handler);
  return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
}

/** Subscribe to session-refreshed; returns an unsubscribe function. */
export function onSessionRefreshed(handler: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  window.addEventListener(SESSION_REFRESHED_EVENT, handler);
  return () => window.removeEventListener(SESSION_REFRESHED_EVENT, handler);
}
