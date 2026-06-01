/**
 * <SessionBanner> (ADR-705)
 *
 * Ambient, chrome-level session treatment driven off the canonical
 * sessionStatus — defined once and rendered above the toolbar so every page
 * inherits it:
 *  - expired   → a loud, non-dismissible strip correcting the "I'm logged in"
 *                mental model.
 *  - anonymous → a quiet always-on "Viewing as guest" strip.
 *  - authenticated → nothing.
 *
 * The banner is *explanation only* — the single sign-in affordance lives in the
 * top-right UserProfile corner, so the banner deliberately carries no button to
 * avoid a duplicate sign-in control stacked in the same corner.
 */

import { AlertTriangle, Eye } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';

export function SessionBanner() {
  const sessionStatus = useAuthStore((s) => s.sessionStatus);

  if (sessionStatus === 'authenticated') return null;

  const expired = sessionStatus === 'expired';

  return (
    <div
      className={
        expired
          ? 'bg-status-warning/90 text-black px-4 py-2 flex items-center gap-2 text-sm'
          : 'bg-muted/50 text-muted-foreground border-b border-border px-4 py-1.5 flex items-center gap-2 text-xs'
      }
      role="status"
    >
      {expired ? (
        <AlertTriangle className="w-4 h-4 flex-none" />
      ) : (
        <Eye className="w-3.5 h-3.5 flex-none" />
      )}
      <span className="font-medium">
        {expired ? 'Your session expired' : 'Viewing as guest'}
      </span>
      <span className="opacity-80 truncate">
        {expired
          ? '— sign in to continue.'
          : '— sign in to save changes and access your data.'}
      </span>
    </div>
  );
}
