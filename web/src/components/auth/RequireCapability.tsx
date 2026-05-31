/**
 * <RequireCapability> / <RequireAuth> (ADR-705)
 *
 * Section/page wrappers. When the user has the capability, children render.
 * Otherwise the section shows an in-place fallback (default: <SignInPrompt>) —
 * never a redirect — per the browsable + read-only model.
 *
 *   <RequireAuth detail="to access admin settings">
 *     <AdminPanels />
 *   </RequireAuth>
 */

import React from 'react';
import { useCapability } from '../../hooks/useCapability';
import { SignInPrompt } from './SignInPrompt';

interface RequireCapabilityProps {
  /** Resource for a permission check (omit for a plain auth check). */
  resource?: string;
  /** Action for a permission check. */
  action?: string;
  /** Context line passed to the default SignInPrompt, e.g. "to access admin settings". */
  detail?: string;
  /** Custom fallback; overrides the default SignInPrompt when provided. */
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export function RequireCapability({
  resource,
  action,
  detail,
  fallback,
  children,
}: RequireCapabilityProps): React.ReactElement {
  const { can, reason } = useCapability(resource, action);
  if (can) return <>{children}</>;
  if (fallback !== undefined) return <>{fallback}</>;
  return <SignInPrompt reason={reason} detail={detail} />;
}

/** Plain authentication gate — any authenticated user passes. */
export function RequireAuth(props: Omit<RequireCapabilityProps, 'resource' | 'action'>): React.ReactElement {
  return <RequireCapability {...props} />;
}
