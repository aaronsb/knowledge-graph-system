/**
 * <ProtectedView> (ADR-705)
 *
 * Page-level gate for content workspaces. When the user can't load content
 * (anonymous or expired), renders the generalized <LoggedOutView> instead of
 * letting the workspace mount, fetch, and dump a raw 401. Nav stays browsable
 * (browsable + read-only model) — the content area just shows a graceful,
 * consistent signed-out surface.
 *
 * Use this to wrap whole route elements. For smaller in-section gates, use
 * <RequireCapability> / <Gated> instead.
 */

import React from 'react';
import { useCapability } from '../../hooks/useCapability';
import { LoggedOutView } from './LoggedOutView';

interface ProtectedViewProps {
  /** Noun for the signed-out headline, e.g. "the graph". */
  what?: string;
  children: React.ReactNode;
}

export function ProtectedView({ what, children }: ProtectedViewProps): React.ReactElement {
  const { can } = useCapability();
  if (!can) return <LoggedOutView what={what} />;
  return <>{children}</>;
}
