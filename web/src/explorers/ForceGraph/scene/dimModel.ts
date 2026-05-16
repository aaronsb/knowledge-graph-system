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
 * One number per tier, applied uniformly to nodes, edges, AND their
 * labels. Nodes/edges dim by color-multiply, labels by plane opacity —
 * but on the dark scene background color-multiply toward black and
 * opacity toward background are perceptually the same, so a single
 * value reads as one consistent recede across all four element kinds.
 *
 * Deliberately NOT split per element kind: a per-kind knob is what let
 * labels and dots drift to different strengths. If a tier needs to be
 * gentler because labels vanish before dots do, raise the one number —
 * that softens everything together, which is the point.
 *
 * The engine itself stays primitive — Scene/Nodes/Edges/labels take
 * plain numbers. This map is a consumer-side convenience; explorers
 * resolve a tier to its alpha and feed the number in. A future
 * consumer with a different interaction vocabulary isn't forced to
 * adopt ours.
 *
 * Fixed for now. If these become user-configurable, this is the seam.
 */

export type DimTier = 'hover' | 'focus';

/** Out-of-set alpha per tier: color multiplier for node meshes / edges /
 *  arrows, and plane opacity for node / edge labels. One value drives
 *  all of them so the dim reads consistently. */
export const DIM_MODEL: Record<DimTier, number> = {
  hover: 0.9,
  focus: 0.1,
};
