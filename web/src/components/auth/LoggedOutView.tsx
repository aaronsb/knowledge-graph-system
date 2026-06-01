/**
 * <LoggedOutView> (ADR-705)
 *
 * The generalized "you can't load content here while signed out" surface.
 * Content workspaces fetch on mount and would otherwise dump a raw
 * "Request failed with status code 401"; this replaces that with a consistent,
 * session-aware view used everywhere via <ProtectedView>.
 *
 * It reuses the real NavigationGraph "Workstation Guide" so a signed-out visitor
 * also gets an idea of what the platform is and how it fits together — the same
 * guide authenticated users see on Home, kept as a single source of truth.
 */

import { useState } from 'react';
import { LogIn, Network } from 'lucide-react';
import { NavigationGraph } from '../home/NavigationGraph';
import { LoginModal } from './LoginModal';
import { useAuthStore } from '../../store/authStore';

interface LoggedOutViewProps {
  /** Noun for the headline, e.g. "the graph" → "Sign in to view the graph". */
  what?: string;
}

export function LoggedOutView({ what }: LoggedOutViewProps) {
  const sessionStatus = useAuthStore((s) => s.sessionStatus);
  const [showLogin, setShowLogin] = useState(false);
  const expired = sessionStatus === 'expired';

  return (
    <div className="h-full overflow-auto bg-background">
      <div className="max-w-3xl mx-auto px-6 py-10">
        {/* Sign-in prompt */}
        <div className="text-center mb-10">
          <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center shadow-lg">
            <Network className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold text-foreground mb-2">
            {expired ? 'Your session expired' : `Sign in to view ${what ?? 'this content'}`}
          </h2>
          <p className="text-muted-foreground mb-6">
            {expired
              ? 'Your session expired — sign in again to load this content.'
              : 'This content requires a signed-in session. Meanwhile, here’s how the workstation fits together.'}
          </p>
          <button
            onClick={() => setShowLogin(true)}
            className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors shadow-md"
          >
            <LogIn className="w-5 h-5" />
            {expired ? 'Sign In Again' : 'Sign In'}
          </button>
        </div>

        {/* Workstation guide — doubles as a help navigator for signed-out visitors */}
        <section>
          <h3 className="text-lg font-semibold text-foreground mb-1">Workstation Guide</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Click any node to explore. This is how the knowledge graph workstation works.
          </p>
          <div className="p-4 rounded-lg bg-card border border-border">
            <NavigationGraph />
          </div>
        </section>
      </div>

      <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} />
    </div>
  );
}
