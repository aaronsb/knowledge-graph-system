/**
 * OAuth 2.0 Authorization Code Flow with PKCE
 *
 * Implements RFC 6749 (OAuth 2.0) + RFC 7636 (PKCE)
 * For secure browser-based authentication
 */

import axios from 'axios';
import {
  generateCodeVerifier,
  generateCodeChallenge,
  storePKCEVerifier,
  consumePKCEVerifier,
  storeAuthState,
  type OAuthTokenResponse,
  type StoredAuthState,
} from './oauth-utils';

// OAuth configuration - runtime config takes precedence over build-time env vars
// This enables CDN deployment without rebuilding
declare global {
  interface Window {
    APP_CONFIG?: {
      apiUrl: string;
      oauth: {
        clientId: string;
        redirectUri?: string | null;
      };
      app?: {
        name?: string;
        version?: string;
      };
    };
  }
}

const API_BASE_URL = window.APP_CONFIG?.apiUrl || import.meta.env.VITE_API_URL || 'http://localhost:8000';
const CLIENT_ID = window.APP_CONFIG?.oauth?.clientId || import.meta.env.VITE_OAUTH_CLIENT_ID || 'kg-viz';
const REDIRECT_URI =
  window.APP_CONFIG?.oauth?.redirectUri ||
  import.meta.env.VITE_OAUTH_REDIRECT_URI ||
  `${window.location.origin}/callback`;

export interface AuthorizationFlowConfig {
  scope?: string;
  state?: string; // Optional state for CSRF protection
}

/**
 * Start OAuth authorization flow - Combined login and authorization
 * Generates PKCE challenge and calls login-and-authorize endpoint
 */
export async function startAuthorizationFlow(
  username: string,
  password: string,
  config: AuthorizationFlowConfig = {}
): Promise<void> {
  // Generate PKCE parameters
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = await generateCodeChallenge(codeVerifier);

  // Store verifier for later use in callback
  storePKCEVerifier(codeVerifier);

  // Call combined login-and-authorize endpoint
  const formData = new URLSearchParams({
    username,
    password,
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    scope: config.scope || 'read:* write:*',
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
  });

  if (config.state) {
    formData.append('state', config.state);
  }

  const response = await axios.post(`${API_BASE_URL}/auth/oauth/login-and-authorize`, formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });

  const { code, state } = response.data;

  // Redirect to callback with authorization code
  const callbackUrl = new URL(REDIRECT_URI);
  callbackUrl.searchParams.set('code', code);
  if (state) {
    callbackUrl.searchParams.set('state', state);
  }

  window.location.href = callbackUrl.toString();
}

/**
 * Handle OAuth callback
 * Exchanges authorization code for access token using PKCE verifier
 */
export async function handleAuthorizationCallback(
  code: string,
  state?: string
): Promise<StoredAuthState> {
  // Retrieve PKCE verifier from storage
  const codeVerifier = consumePKCEVerifier();
  if (!codeVerifier) {
    throw new Error('PKCE verifier not found - possible CSRF attack or expired session');
  }

  // Exchange authorization code for access token
  const response = await axios.post<OAuthTokenResponse>(
    `${API_BASE_URL}/auth/oauth/token`,
    new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      redirect_uri: REDIRECT_URI,
      client_id: CLIENT_ID,
      code_verifier: codeVerifier,
    }),
    {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    }
  );

  const tokenData = response.data;

  // Calculate expiration time
  const expiresAt = new Date(Date.now() + tokenData.expires_in * 1000).toISOString();

  // Fetch user info using access token
  const userResponse = await axios.get(`${API_BASE_URL}/users/me`, {
    headers: {
      Authorization: `Bearer ${tokenData.access_token}`,
    },
  });

  const authState: StoredAuthState = {
    access_token: tokenData.access_token,
    refresh_token: tokenData.refresh_token,
    expires_at: expiresAt,
    token_type: tokenData.token_type,
    scope: tokenData.scope,
    user: userResponse.data,
  };

  // Store auth state
  storeAuthState(authState);

  return authState;
}

/**
 * Refresh access token using refresh token
 */
export async function refreshAccessToken(
  refreshToken: string
): Promise<StoredAuthState> {
  const response = await axios.post<OAuthTokenResponse>(
    `${API_BASE_URL}/auth/oauth/token`,
    new URLSearchParams({
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
      client_id: CLIENT_ID,
    }),
    {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    }
  );

  const tokenData = response.data;

  // Calculate new expiration time
  const expiresAt = new Date(Date.now() + tokenData.expires_in * 1000).toISOString();

  // Fetch updated user info
  const userResponse = await axios.get(`${API_BASE_URL}/users/me`, {
    headers: {
      Authorization: `Bearer ${tokenData.access_token}`,
    },
  });

  const authState: StoredAuthState = {
    access_token: tokenData.access_token,
    refresh_token: tokenData.refresh_token || refreshToken, // Use new refresh token if provided
    expires_at: expiresAt,
    token_type: tokenData.token_type,
    scope: tokenData.scope,
    user: userResponse.data,
  };

  // Update stored auth state
  storeAuthState(authState);

  return authState;
}

/**
 * Revoke access token (logout)
 */
export async function revokeAccessToken(accessToken: string): Promise<void> {
  try {
    await axios.post(
      `${API_BASE_URL}/auth/oauth/revoke`,
      new URLSearchParams({
        token: accessToken,
        token_type_hint: 'access_token',
      }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          Authorization: `Bearer ${accessToken}`,
        },
      }
    );
  } catch (error) {
    // Ignore errors - token might already be expired/invalid
    console.warn('Token revocation failed:', error);
  }
}
