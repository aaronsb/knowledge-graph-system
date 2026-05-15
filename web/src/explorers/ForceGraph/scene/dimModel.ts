/**
 * Shared dim model — one source of truth for hover/focus dimming so
 * every explorer that consumes the engine recedes by the same amount.
 *
 * Two interaction tiers, matching the model both Force Graph and
 * Document Explorer expose:
 *
 *   - hover  — transient, subtle. Pointer is over a node; its local
 *              topology stays lit while the rest steps back just enough
 *              to read the neighborhood without feeling like a mode
 *              change.
 *   - focus  — persistent, aggressive. Set via right-click "Focus on
 *              node/document". Wins over hover when both are active.
 *
 * Each tier is ONE node carrying every property it affects, so the
 * node mesh and its label can never drift apart: tune a tier in one
 * place and the dot and its text move together. (The previous flat
 * constants let label opacity and node alpha be set independently —
 * that's what made hover read harsher on labels than on dots.)
 *
 * The engine itself stays primitive — Scene/Nodes/Edges/labels take
 * plain numbers. This map is a consumer-side convenience; explorers
 * resolve a tier to its spec and feed the numbers in. A future
 * consumer with a different interaction vocabulary isn't forced to
 * adopt ours.
 *
 * Fixed for now. If these become user-configurable, this is the seam.
 */

export type DimTier = 'hover' | 'focus';

export interface DimSpec {
  /** Color multiplier for out-of-set node meshes, edges, and arrows
   *  (edges visually couple to their endpoints, so they share the
   *  node figure rather than carrying a separate alpha). */
  nodeAlpha: number;
  /** Plane opacity for out-of-set node and edge labels. */
  labelOpacity: number;
}

export const DIM_MODEL: Record<DimTier, DimSpec> = {
  hover: { nodeAlpha: 0.9, labelOpacity: 0.9 },
  focus: { nodeAlpha: 0.05, labelOpacity: 0.15 },
};
