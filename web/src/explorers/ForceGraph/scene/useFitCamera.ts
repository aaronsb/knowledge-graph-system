/**
 * First-load camera fit — "fake zoom-extents".
 *
 * The camera mounts at a fixed distance; a freshly-seeded graph settles
 * into a cluster that is tiny and off-centre in that fixed view, so the
 * user had to manually zoom every time. On the first appearance of nodes
 * this fires the shared orientAndFrame action once: it rotates to the
 * graph's broad face and eases in (orientView/useOrientAndFrame own that
 * geometry + tween — this hook owns only *when*).
 *
 * Two deliberate constraints:
 *
 *  - First load ONLY. We arm on a 0→N transition (first appearance, or a
 *    fresh graph after the prior was cleared). Incremental growth (Add
 *    Adjacent), filters, and follow keep N>0 throughout, so they never
 *    re-arm and the camera stays where the user left it — re-fitting on
 *    every change is the camera-side of the "sproing" trap PR #371 fixed
 *    for the sim. A manual Fit/Reheat is the intended escape hatch.
 *
 *  - Settle by time, not by a radius heuristic. We wait a fixed window
 *    (SETTLE_MS) for the force layout to relax before framing it, rather
 *    than watching the bounding radius: the user asked for a predictable
 *    "let physics settle ~2s, then zoom", and a fixed timer is robust
 *    under the demand frameloop where a frame-delta heuristic misfires.
 *    We keep the demand loop pumping while armed so the window actually
 *    elapses even after the sim quiesces and stops invalidating.
 *
 * Lives in the shared Scene, so Force Graph and Document Explorer both
 * get it from one implementation.
 *
 * @verified 3e3afbcd
 */

import { useEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import type { EventDispatcher } from 'three';
import type { EngineNode } from '../types';

/**
 * How long to let the force layout relax before framing it. The user's
 * stated intent ("wait some amount of time for physics to settle ...
 * say, 2000 msec"); also comfortably longer than drei's controls take to
 * mount, so the orient tween has a target to lerp by the time it fires.
 */
const SETTLE_MS = 2000;

/**
 * Arm a one-shot orient on the graph's first appearance.
 *
 * `orient` is the whole-graph branch of the shared orientAndFrame action
 * (Scene wires `useOrientAndFrame().orient`). Idempotent under
 * StrictMode's double-invoked effects: the 0→N guard only arms once per
 * real transition.
 *
 * @verified 3e3afbcd
 */
export function useFitCamera(orient: () => void, nodes: EngineNode[]): void {
  const invalidate = useThree((s) => s.invalidate);
  const controls = useThree((s) => s.controls) as EventDispatcher | null;

  const armedRef = useRef(false);
  const firedRef = useRef(false);
  const armedAtRef = useRef(0);
  // Whether the previous render had any nodes — the 0→N edge is the
  // "first load" signal (see header). StrictMode re-runs the effect with
  // the same nodes.length; once this is true a re-run won't re-arm.
  const hadNodesRef = useRef(false);

  useEffect(() => {
    const has = nodes.length > 0;
    if (has && !hadNodesRef.current) {
      armedRef.current = true;
      firedRef.current = false;
      armedAtRef.current = performance.now();
      invalidate();
    }
    hadNodesRef.current = has;
  }, [nodes.length, invalidate]);

  // If the user grabs the camera during the settle window, abandon the
  // pending fit — firing it at t=2s anyway would yank the view out from
  // under them (the same "sproing" this hook's header says it avoids,
  // just on the first-load path). The orient tween has its own cancel;
  // this guards the trigger that hasn't fired yet. firedRef doubles as
  // "spent" so it never arms again this lifetime.
  useEffect(() => {
    if (!controls) return;
    const abort = () => {
      if (armedRef.current && !firedRef.current) {
        armedRef.current = false;
        firedRef.current = true;
      }
    };
    controls.addEventListener('start', abort);
    return () => controls.removeEventListener('start', abort);
  }, [controls]);

  useFrame(() => {
    if (!armedRef.current || firedRef.current) return;
    // Keep the demand frameloop alive until the settle window elapses —
    // the sim stops invalidating once it quiesces, and without this the
    // timer check would never run again and the fit would never fire.
    invalidate();
    if (performance.now() - armedAtRef.current < SETTLE_MS) return;
    firedRef.current = true;
    armedRef.current = false;
    orient();
  });
}
