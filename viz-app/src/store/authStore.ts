/**
 * Auth Store - Zustand State Management
 *
 * Manages user authentication state including:
 * - Login/logout
 * - Token refresh
 * - User info
 * - Auth status
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

interface User {
  id: number;
  username: string;
  role: string;
}

interface AuthStore {
  // State
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: () => Promise<void>;
  logout: () => Promise<void>;
  handleCallback: (code: string, state?: string) => Promise<void>;
  refreshToken: () => Promise<void>;
  checkAuth: () => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  // Initial state
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  /**
   * Start OAuth login flow
   * Redirects to authorization endpoint
   */
  login: async () => {
    try {
      set({ isLoading: true, error: null });
      await startAuthorizationFlow({
        scope: 'read:* write:*',
      });
      // Note: User will be redirected, so this function won't return
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Login failed',
      });
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
        isLoading: false,
        error: null,
      });
    } catch (error) {
      // Clear local state even if revocation fails
      clearAuthState();
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Logout failed',
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
        isLoading: false,
        error: null,
      });
    } catch (error) {
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Authentication failed',
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
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        error: 'No refresh token available',
      });
      return;
    }

    try {
      const newAuthState = await refreshAccessToken(authState.refresh_token);

      set({
        user: newAuthState.user || null,
        accessToken: newAuthState.access_token,
        isAuthenticated: true,
        error: null,
      });
    } catch (error) {
      // Refresh failed - user needs to re-login
      clearAuthState();
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        error: 'Session expired - please login again',
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
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
      });
      return;
    }

    // Check if token is expired
    if (isTokenExpired(authState.expires_at)) {
      // Try to refresh token automatically
      if (authState.refresh_token) {
        get().refreshToken();
      } else {
        // No refresh token - clear state
        clearAuthState();
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
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
    });
  },

  /**
   * Clear error message
   */
  clearError: () => set({ error: null }),
}));
