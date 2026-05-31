/**
 * <SessionBanner> (ADR-705)
 *
 * Ambient, chrome-level session treatment driven off the canonical
 * sessionStatus — defined once and rendered above the toolbar so every page
 * inherits it:
 *  - expired   → a loud, non-dismissible banner correcting the "I'm logged in"
 *                mental model.
 *  - anonymous → a quiet always-on "Viewing as guest" strip.
 *  - authenticated → nothing.
 */

import { useState } from 'react';
import { AlertTriangle, Eye, LogIn } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { LoginModal } from './LoginModal';

export function SessionBanner() {
  const sessionStatus = useAuthStore((s) => s.sessionStatus);
  const [showLogin, setShowLogin] = useState(false);

  if (sessionStatus === 'authenticated') return null;

  const expired = sessionStatus === 'expired';

  return (
    <>
      <div
        className={
          expired
            ? 'bg-status-warning/90 text-black px-4 py-2 flex items-center justify-between text-sm'
            : 'bg-muted/50 text-muted-foreground border-b border-border px-4 py-1.5 flex items-center justify-between text-xs'
        }
        role="status"
      >
        <div className="flex items-center gap-2 min-w-0">
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
        <button
          onClick={() => setShowLogin(true)}
          className={
            expired
              ? 'flex-none inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-black/10 hover:bg-black/20 font-medium transition-colors'
              : 'flex-none inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md hover:bg-accent hover:text-accent-foreground transition-colors'
          }
        >
          <LogIn className="w-3.5 h-3.5" />
          Sign In
        </button>
      </div>
      <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} />
    </>
  );
}
