/**
 * Auth Store - Zustand State Management
 *
 * Manages user authentication state including:
 * - Login/logout
 * - Token refresh
 * - User info
 * - Auth status
 * - Permissions (ADR-409)
 */

import { create } from 'zustand';
import {
  startAuthorizationFlow,
  handleAuthorizationCallback,
  refreshAccessToken,
  revokeAccessToken,
} from '../lib/auth/authorization-code-flow';
import {
  getAuthState,
  clearAuthState,
  isTokenExpired,
  type StoredAuthState,
} from '../lib/auth/oauth-utils';
import { onSessionExpired, onSessionRefreshed } from '../lib/auth/session-events';
import { apiClient } from '../api/client';

interface User {
  id: number;
  username: string;
  role: string;
}

/**
 * Canonical session status (ADR-705).
 *
 * Un-collapses the `isAuthenticated: false` ambiguity so the UI can treat a
 * never-logged-in user differently from one whose session expired:
 *  - `anonymous`     — no credentials (never logged in, or logged out)
 *  - `authenticated` — a valid, non-expired token is present
 *  - `expired`       — credentials existed but are gone/rejected and could not
 *                      be refreshed (gets the loud "session expired" treatment)
 */
export type SessionStatus = 'anonymous' | 'authenticated' | 'expired';

/**
 * Permissions state (ADR-409)
 * Loaded after authentication, provides easy permission checking
 */
interface PermissionsState {
  role: string;
  roleHierarchy: string[];
  can: Record<string, boolean>;  // "resource:action" -> boolean
}

interface AuthStore {
  // State
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  sessionStatus: SessionStatus;  // ADR-705: anonymous | authenticated | expired
  hydrated: boolean;             // ADR-705: initial checkAuth (incl. any refresh) has resolved
  isLoading: boolean;
  error: string | null;

  // Permissions (ADR-409)
  permissions: PermissionsState | null;
  permissionsLoading: boolean;

  // Actions
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  handleCallback: (code: string, state?: string) => Promise<void>;
  refreshToken: () => Promise<void>;
  checkAuth: () => void;
  clearError: () => void;

  // Permission actions (ADR-409)
  loadPermissions: () => Promise<void>;
  hasPermission: (resource: string, action: string) => boolean;
  isPlatformAdmin: () => boolean;
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  // Initial state
  user: null,
  accessToken: null,
  isAuthenticated: false,
  sessionStatus: 'anonymous',
  hydrated: false,
  isLoading: false,
  error: null,

  // Permissions (ADR-409)
  permissions: null,
  permissionsLoading: false,

  /**
   * Start OAuth login flow with credentials
   * Calls login-and-authorize endpoint, then redirects to callback
   */
  login: async (username: string, password: string) => {
    try {
      set({ isLoading: true, error: null });
      await startAuthorizationFlow(username, password, {
        scope: 'read:* write:*',
      });
      // Note: User will be redirected, so this function won't return
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Login failed',
      });
      throw error; // Re-throw so LoginModal can handle it
    }
  },

  /**
   * Logout - revoke token and clear state
   */
  logout: async () => {
    const { accessToken } = get();

    try {
      set({ isLoading: true, error: null });

      // Revoke access token on server
      if (accessToken) {
        await revokeAccessToken(accessToken);
      }

      // Clear local state
      clearAuthState();
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        sessionStatus: 'anonymous',
        isLoading: false,
        error: null,
        permissions: null,  // ADR-409: Clear permissions on logout
      });
    } catch (error) {
      // Clear local state even if revocation fails
      clearAuthState();
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        sessionStatus: 'anonymous',
        isLoading: false,
        error: error instanceof Error ? error.message : 'Logout failed',
        permissions: null,  // ADR-409: Clear permissions on logout
      });
    }
  },

  /**
   * Handle OAuth callback
   * Exchange authorization code for access token
   */
  handleCallback: async (code: string, state?: string) => {
    try {
      set({ isLoading: true, error: null });

      const authState = await handleAuthorizationCallback(code, state);

      set({
        user: authState.user || null,
        accessToken: authState.access_token,
        isAuthenticated: true,
        sessionStatus: 'authenticated',
        isLoading: false,
        error: null,
      });

      // Load permissions after successful auth (ADR-409)
      get().loadPermissions();
    } catch (error) {
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        sessionStatus: 'anonymous',
        isLoading: false,
        error: error instanceof Error ? error.message : 'Authentication failed',
        permissions: null,  // ADR-409: Clear permissions on auth failure
      });
    }
  },

  /**
   * Refresh access token
   * Uses refresh token from storage
   */
  refreshToken: async () => {
    const authState = getAuthState();
    if (!authState || !authState.refresh_token) {
      // No credentials at all → anonymous; a present token we cannot refresh → expired.
      const hadCredentials = !!authState;
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        sessionStatus: hadCredentials ? 'expired' : 'anonymous',
        hydrated: true,
        error: hadCredentials ? 'No refresh token available' : null,
        permissions: null,  // ADR-409
      });
      return;
    }

    try {
      const newAuthState = await refreshAccessToken(authState.refresh_token);

      set({
        user: newAuthState.user || null,
        accessToken: newAuthState.access_token,
        isAuthenticated: true,
        sessionStatus: 'authenticated',
        hydrated: true,
        error: null,
      });

      // Reload permissions after token refresh (ADR-409)
      get().loadPermissions();
    } catch (error) {
      // Refresh failed - user needs to re-login
      clearAuthState();
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        sessionStatus: 'expired',
        hydrated: true,
        error: 'Session expired - please login again',
        permissions: null,  // ADR-409
      });
    }
  },

  /**
   * Check authentication status
   * Loads auth state from localStorage and validates token
   */
  checkAuth: () => {
    const authState = getAuthState();

    if (!authState) {
      // Never logged in (or logged out) → anonymous, not expired.
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        sessionStatus: 'anonymous',
        hydrated: true,
      });
      return;
    }

    // Check if token is expired
    if (isTokenExpired(authState.expires_at)) {
      // Try to refresh token automatically (refreshToken sets sessionStatus + hydrated)
      if (authState.refresh_token) {
        get().refreshToken();
      } else {
        // No refresh token - session expired
        clearAuthState();
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
          sessionStatus: 'expired',
          hydrated: true,
          error: 'Session expired',
        });
      }
      return;
    }

    // Token is valid - restore auth state
    set({
      user: authState.user || null,
      accessToken: authState.access_token,
      isAuthenticated: true,
      sessionStatus: 'authenticated',
      hydrated: true,
    });

    // Load permissions after restoring auth (ADR-409)
    get().loadPermissions();
  },

  /**
   * Clear error message
   */
  clearError: () => set({ error: null }),

  // ==========================================================================
  // Permission Methods (ADR-409)
  // ==========================================================================

  /**
   * Load user's effective permissions from API
   * Called automatically after authentication
   */
  loadPermissions: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) {
      set({ permissions: null });
      return;
    }

    set({ permissionsLoading: true });

    try {
      const data = await apiClient.getCurrentUserPermissions();
      set({
        permissions: {
          role: data.role,
          roleHierarchy: data.role_hierarchy,
          can: data.can,
        },
        permissionsLoading: false,
      });
    } catch (error) {
      console.error('Failed to load permissions:', error);
      set({
        permissions: null,
        permissionsLoading: false,
      });
    }
  },

  /**
   * Check if user has a specific permission
   * Usage: hasPermission('users', 'read') or hasPermission('admin', 'status')
   */
  hasPermission: (resource: string, action: string): boolean => {
    const { permissions } = get();
    if (!permissions) return false;

    const key = `${resource}:${action}`;
    return permissions.can[key] === true;
  },

  /**
   * Check if user is a platform admin (highest privilege level)
   */
  isPlatformAdmin: (): boolean => {
    const { permissions } = get();
    if (!permissions) return false;

    return permissions.roleHierarchy.includes('platform_admin');
  },
}));

// ============================================================================
// Session event wiring (ADR-705)
//
// The API client's 401 interceptor signals session transitions via window
// events (it cannot import this store). Subscribe once at module load so a
// mid-session expiry — detected on any request — flips the store to `expired`
// and a successful in-flight refresh re-syncs from storage.
// ============================================================================

const unsubscribeExpired = onSessionExpired(() => {
  // The interceptor has already cleared stored credentials.
  useAuthStore.setState({
    user: null,
    accessToken: null,
    isAuthenticated: false,
    sessionStatus: 'expired',
    error: 'Session expired - please login again',
    permissions: null,
  });
});

const unsubscribeRefreshed = onSessionRefreshed(() => {
  // Storage was updated by the refresh; re-sync the in-memory token/user.
  const authState = getAuthState();
  if (authState) {
    useAuthStore.setState({
      user: authState.user || null,
      accessToken: authState.access_token,
      isAuthenticated: true,
      sessionStatus: 'authenticated',
      error: null,
    });
    // Permissions may have changed across the refresh; reload them so the
    // interceptor-driven refresh path matches refreshToken()/checkAuth().
    useAuthStore.getState().loadPermissions();
  }
});

// Avoid stacking duplicate window listeners across Vite HMR reloads (dev only).
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    unsubscribeExpired();
    unsubscribeRefreshed();
  });
}
