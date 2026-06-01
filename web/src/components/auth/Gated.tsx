/**
 * <Gated> (ADR-705)
 *
 * Wraps a single interactive control (typically a <button>). When the user
 * cannot perform the action, the child is rendered disabled with a reason
 * tooltip (native `title`, matching the codebase convention), per the
 * browsable + read-only model. Wrapping a control in <Gated> makes correct
 * gating the default rather than something each component must remember.
 *
 *   <Gated resource="jobs" action="approve" label="approve jobs">
 *     <button onClick={approve}>Approve</button>
 *   </Gated>
 */

import React from 'react';
import { useCapability, reasonMessage } from '../../hooks/useCapability';

interface GatedProps {
  /** Resource for a permission check (omit for a plain auth check). */
  resource?: string;
  /** Action for a permission check. */
  action?: string;
  /** Verb phrase for the tooltip, e.g. "approve jobs". */
  label?: string;
  /** The single interactive element to gate. */
  children: React.ReactElement;
}

export function Gated({ resource, action, label, children }: GatedProps): React.ReactElement {
  const { can, reason } = useCapability(resource, action);
  if (can) return children;

  // Disable the control and surface why. `disabled` is honored by form
  // controls (the intended targets); `aria-disabled` + `title` cover the rest.
  return React.cloneElement(children, {
    disabled: true,
    'aria-disabled': true,
    title: reasonMessage(reason, label),
  } as Partial<typeof children.props>);
}
