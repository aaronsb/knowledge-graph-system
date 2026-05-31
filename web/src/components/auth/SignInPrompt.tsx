/**
 * <SignInPrompt> (ADR-705)
 *
 * The default in-place fallback for gated sections: a session-aware message
 * (anonymous vs expired) plus a Sign In button that opens the login modal.
 * Shown in place — never a redirect — per the browsable + read-only model.
 */

import { useState } from 'react';
import { LogIn, ShieldAlert } from 'lucide-react';
import { LoginModal } from './LoginModal';
import { reasonMessage, type CapabilityReason } from '../../hooks/useCapability';

interface SignInPromptProps {
  /** Why the gate is closed; controls the headline copy. */
  reason: CapabilityReason;
  /** Optional context line, e.g. "to access admin settings". */
  detail?: string;
}

export function SignInPrompt({ reason, detail }: SignInPromptProps) {
  const [showLogin, setShowLogin] = useState(false);

  const expired = reason === 'expired';
  const forbidden = reason === 'forbidden';
  const headline = expired
    ? 'Your session expired'
    : forbidden
      ? 'You don’t have access'
      : 'Sign in required';

  return (
    <div className="h-full flex items-center justify-center bg-background">
      <div className="text-center max-w-sm">
        <ShieldAlert className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-foreground">{headline}</h2>
        <p className="text-muted-foreground mt-2">
          {forbidden ? reasonMessage(reason) : detail ? `Sign in ${detail}.` : 'Sign in to continue.'}
        </p>
        {!forbidden && (
          <button
            onClick={() => setShowLogin(true)}
            className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors shadow-md"
          >
            <LogIn className="w-4 h-4" />
            Sign In
          </button>
        )}
        <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} />
      </div>
    </div>
  );
}
