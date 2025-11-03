/**
 * OAuth 2.0 Utility Functions (ADR-054)
 *
 * Shared utilities for OAuth token management
 */

import { OAuthTokenInfo, OAuthTokenResponse } from './oauth-types';

/**
 * Check if an OAuth token is expired or about to expire
 *
 * @param tokenInfo - Token information with expires_at timestamp
 * @param bufferSeconds - How many seconds before expiry to consider token expired (default: 60)
 * @returns true if token is expired or will expire within buffer period
 */
export function isTokenExpired(tokenInfo: OAuthTokenInfo | null, bufferSeconds: number = 60): boolean {
  if (!tokenInfo) {
    return true;
  }

  const now = Math.floor(Date.now() / 1000);  // Current time in seconds
  const expiresWithBuffer = tokenInfo.expires_at - bufferSeconds;

  return now >= expiresWithBuffer;
}

/**
 * Convert OAuth token response to storable token info
 *
 * @param response - Token response from API
 * @param clientId - OAuth client ID
 * @returns Token info object ready for storage
 */
export function convertTokenResponse(response: OAuthTokenResponse, clientId: string): OAuthTokenInfo {
  const now = Math.floor(Date.now() / 1000);

  return {
    access_token: response.access_token,
    token_type: response.token_type,
    expires_at: now + response.expires_in,
    refresh_token: response.refresh_token,
    scope: response.scope,
    client_id: clientId,
  };
}

/**
 * Get time until token expires
 *
 * @param tokenInfo - Token information
 * @returns Seconds until expiration, or 0 if already expired
 */
export function getTimeUntilExpiry(tokenInfo: OAuthTokenInfo | null): number {
  if (!tokenInfo) {
    return 0;
  }

  const now = Math.floor(Date.now() / 1000);
  const remaining = tokenInfo.expires_at - now;

  return Math.max(0, remaining);
}

/**
 * Format expiry time as human-readable string
 *
 * @param tokenInfo - Token information
 * @returns Human-readable expiry time (e.g., "in 45 minutes")
 */
export function formatExpiryTime(tokenInfo: OAuthTokenInfo | null): string {
  if (!tokenInfo) {
    return 'expired';
  }

  const seconds = getTimeUntilExpiry(tokenInfo);

  if (seconds === 0) {
    return 'expired';
  }

  if (seconds < 60) {
    return `in ${seconds} second${seconds !== 1 ? 's' : ''}`;
  }

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `in ${minutes} minute${minutes !== 1 ? 's' : ''}`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `in ${hours} hour${hours !== 1 ? 's' : ''}`;
  }

  const days = Math.floor(hours / 24);
  return `in ${days} day${days !== 1 ? 's' : ''}`;
}

/**
 * Parse scope string into array
 *
 * @param scope - Space-separated scope string
 * @returns Array of individual scopes
 */
export function parseScopes(scope: string): string[] {
  if (!scope) {
    return [];
  }
  return scope.trim().split(/\s+/);
}

/**
 * Format scope array as space-separated string
 *
 * @param scopes - Array of scopes
 * @returns Space-separated scope string
 */
export function formatScopes(scopes: string[]): string {
  return scopes.join(' ');
}
