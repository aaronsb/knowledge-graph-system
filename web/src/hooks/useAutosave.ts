/**
 * Autosave — the exploration session, projected as a saved-query entry.
 *
 * The exploration session is already persisted to localStorage (graphStore's
 * partialize). This hook synthesizes a `ReplayableDefinition` view of it
 * so it can appear as a single distinguished entry in the saved-queries
 * panel ("Autosave"), and so the welcome state can offer a "Restore last
 * session" call-to-action that uses the same replay path as any other
 * saved exploration.
 *
 * There is at most one autosave at a time — it reflects the current
 * session. Clean loads (`loadExplore` with `loadMode: 'clean'`, etc.) reset
 * the session, which makes the autosave disappear. A new session starts
 * accumulating on the next action.
 *
 * Why not store this as a real saved-query definition: the session would
 * either need to round-trip through the API (heavy for per-browser state)
 * or duplicate into a second localStorage slot (two sources of truth that
 * must stay in sync). Synthesizing on read is cheaper and avoids both.
 *
 * @verified 8ee95a9f
 */

import { useMemo } from 'react';
import { useGraphStore, type ExplorationSession } from '../store/graphStore';
import { generateCypher, parseCypherStatements } from '../utils/cypherGenerator';
import type { ReplayableDefinition } from './useQueryReplay';

/** Sentinel id used to identify the autosave entry inside the panel list. */
export const AUTOSAVE_ID = -1;

/** Convert an ExplorationSession into the shape `useQueryReplay` consumes. */
function sessionToReplayable(session: ExplorationSession): ReplayableDefinition {
  const script = generateCypher(session);
  const statements = parseCypherStatements(script);
  return {
    id: AUTOSAVE_ID,
    name: 'Autosave',
    definition_type: 'exploration',
    definition: { statements },
  };
}

/**
 * Returns the current autosave entry (replayable shape) when the exploration
 * session has at least one step, or null when there's nothing to restore.
 *
 * Re-computes when the session's step list changes; stable otherwise.
 */
export function useAutosave(): ReplayableDefinition | null {
  const session = useGraphStore((s) => s.explorationSession);

  return useMemo(() => {
    if (!session || session.steps.length === 0) return null;
    return sessionToReplayable(session);
  }, [session]);
}

/**
 * Convenience selector — true when there's an autosave the user could restore.
 * Lighter than calling `useAutosave()` just to check existence.
 */
export function useHasAutosave(): boolean {
  return useGraphStore((s) => (s.explorationSession?.steps.length ?? 0) > 0);
}
