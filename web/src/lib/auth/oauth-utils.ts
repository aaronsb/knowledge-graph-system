/**
 * OAuth 2.0 Utilities for Viz App
 *
 * Implements Authorization Code Flow with PKCE (RFC 7636)
 * For secure authentication in browser-based single-page applications
 */

/**
 * Generate cryptographically secure random string
 */
function generateRandomString(length: number): string {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Base64 URL encode (RFC 4648)
 */
function base64UrlEncode(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

/**
 * Generate PKCE code verifier (RFC 7636)
 * Random string of 43-128 characters
 */
export function generateCodeVerifier(): string {
  return generateRandomString(32); // 64 hex chars
}

/**
 * Check if we're in a secure context where crypto.subtle is available
 */
export function isSecureContext(): boolean {
  return typeof crypto !== 'undefined' && typeof crypto.subtle !== 'undefined';
}

/**
 * Generate PKCE code challenge from verifier (RFC 7636)
 * SHA-256 hash of verifier, base64url encoded
 *
 * In DEV mode only: Falls back to "plain" method in non-secure contexts (HTTP)
 * In PROD: Requires secure context, will throw if unavailable
 */
export async function generateCodeChallenge(verifier: string): Promise<{ challenge: string; method: 'S256' | 'plain' }> {
  // Check if crypto.subtle is available
  if (!isSecureContext()) {
    // DEV ONLY: Allow insecure fallback for local development over HTTP
    // This code block is tree-shaken out of production builds
    if (import.meta.env.DEV) {
      console.warn(
        '%c INSECURE CRYPTO FALLBACK ',
        'background: #ff6b6b; color: white; font-weight: bold;',
        'crypto.subtle unavailable (non-HTTPS). Using plain PKCE - DEV ONLY!'
      );
      return { challenge: verifier, method: 'plain' };
    }

    // PROD: Throw error - must use HTTPS
    throw new Error(
      'Secure context required: crypto.subtle is unavailable. ' +
      'The application must be served over HTTPS in production.'
    );
  }

  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return { challenge: base64UrlEncode(hash), method: 'S256' };
}

/**
 * OAuth Token Response
 */
export interface OAuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string;
  scope?: string;
}

/**
 * Stored Auth State (in localStorage)
 */
export interface StoredAuthState {
  access_token: string;
  refresh_token?: string;
  expires_at: string; // ISO 8601 timestamp
  token_type: string;
  scope?: string;
  user?: {
    id: number;
    username: string;
    role: string;
  };
}

/**
 * Check if access token is expired or about to expire
 */
export function isTokenExpired(expiresAt: string, bufferSeconds: number = 60): boolean {
  const expiryTime = new Date(expiresAt).getTime();
  const now = Date.now();
  const bufferMs = bufferSeconds * 1000;
  return now >= (expiryTime - bufferMs);
}

/**
 * Store auth state in localStorage
 */
export function storeAuthState(state: StoredAuthState): void {
  localStorage.setItem('kg_auth', JSON.stringify(state));
}

/**
 * Get auth state from localStorage
 */
export function getAuthState(): StoredAuthState | null {
  const stored = localStorage.getItem('kg_auth');
  if (!stored) return null;

  try {
    return JSON.parse(stored);
  } catch {
    return null;
  }
}

/**
 * Clear auth state from localStorage
 */
export function clearAuthState(): void {
  localStorage.removeItem('kg_auth');
  localStorage.removeItem('kg_pkce_verifier'); // Clean up PKCE state too
}

/**
 * Store PKCE verifier temporarily during OAuth flow
 */
export function storePKCEVerifier(verifier: string): void {
  localStorage.setItem('kg_pkce_verifier', verifier);
}

/**
 * Get and remove PKCE verifier after OAuth callback
 */
export function consumePKCEVerifier(): string | null {
  const verifier = localStorage.getItem('kg_pkce_verifier');
  if (verifier) {
    localStorage.removeItem('kg_pkce_verifier');
  }
  return verifier;
}
