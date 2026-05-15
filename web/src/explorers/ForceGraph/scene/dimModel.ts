/**
 * Shared dim model — one source of truth for hover/focus dimming so
 * every explorer that consumes the engine recedes by the same amount.
 *
 * Two tiers, matching the interaction model both Force Graph and
 * Document Explorer expose:
 *
 *   - HOVER  — transient, subtle. Pointer is over a node; its local
 *              topology stays lit while the rest steps back enough to
 *              read the neighborhood but not so far it reads as a mode
 *              change.
 *   - FOCUS  — persistent, aggressive. Set via right-click "Focus on
 *              node/document". Wins over hover when both are active.
 *
 * `*_DIM_ALPHA` multiplies node mesh colors (consumers bake it into the
 * per-node color array). `DIM_LABEL_OPACITY` is the label-plane opacity
 * for out-of-set nodes — labels dim via opacity, not color, so the
 * engine owns it on the single `activeIds` path. Consumers should NOT
 * pre-bake the alpha into label colors as well; that double-dims and is
 * what made Document Explorer look harsher than Force Graph.
 *
 * Fixed for now. If these become user-configurable, this is the seam.
 */

/** Node-color multiplier for out-of-set nodes under transient hover.
 *  Deliberately subtle — hover only steps the rest back ~10% so the
 *  local topology reads without the view feeling like it changed mode. */
export const HOVER_DIM_ALPHA = 0.9;

/** Node-color multiplier for out-of-set nodes under persistent focus. */
export const FOCUS_DIM_ALPHA = 0.05;

/** Label-plane opacity for out-of-set nodes (engine-applied, single path). */
export const DIM_LABEL_OPACITY = 0.15;
