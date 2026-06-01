/**
 * useCapability (ADR-705)
 *
 * One hook that answers "may this user do this right now, and if not, why?" by
 * combining the canonical session status with the ADR-400 permission map.
 * Components consume this instead of hand-rolling `if (!isAuthenticated)` checks,
 * so gating stays consistent and distinguishes anonymous from expired.
 */

import { useAuthStore } from '../store/authStore';

export type CapabilityReason = 'ok' | 'anonymous' | 'expired' | 'loading' | 'forbidden';

export interface Capability {
  /** Whether the user may perform the action right now. */
  can: boolean;
  /** Why not (or 'ok'). Drives the tooltip / prompt copy. */
  reason: CapabilityReason;
}

/**
 * Resolve a capability. Omit resource/action for a plain authentication check
 * (any authenticated user passes); pass both to also require a permission.
 */
export function useCapability(resource?: string, action?: string): Capability {
  const sessionStatus = useAuthStore((s) => s.sessionStatus);
  // Subscribe to permissions so the result recomputes when they load/change.
  const permissions = useAuthStore((s) => s.permissions);

  if (sessionStatus !== 'authenticated') {
    return { can: false, reason: sessionStatus === 'expired' ? 'expired' : 'anonymous' };
  }

  if (resource && action) {
    // Permissions load asynchronously after auth. Until they arrive, report
    // 'loading' rather than a hard 'forbidden' so consumers don't flash a
    // "you don't have permission" state for a user who may well have it.
    if (permissions === null) return { can: false, reason: 'loading' };
    const allowed = permissions.can[`${resource}:${action}`] === true;
    if (!allowed) return { can: false, reason: 'forbidden' };
  }

  return { can: true, reason: 'ok' };
}

/**
 * Standard human-readable copy for a non-`ok` reason. `label` is the verb phrase
 * for the action, e.g. "approve jobs" → "Sign in to approve jobs".
 */
export function reasonMessage(reason: CapabilityReason, label = 'do this'): string {
  switch (reason) {
    case 'anonymous':
      return `Sign in to ${label}`;
    case 'expired':
      return 'Your session expired — sign in to continue';
    case 'loading':
      return 'Checking permissions…';
    case 'forbidden':
      return "You don't have permission to do this";
    default:
      return '';
  }
}
