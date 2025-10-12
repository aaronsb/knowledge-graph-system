/**
 * Token Manager
 *
 * Manages JWT token lifecycle: storage, retrieval, validation, expiration.
 * Tokens are stored in the user's config file (~/.config/kg/config.json).
 */

import { ConfigManager } from '../config.js';

export interface TokenInfo {
  access_token: string;
  token_type: string;
  expires_at: number;  // Unix timestamp (seconds)
  username: string;
  role: string;
}

export class TokenManager {
  constructor(private config: ConfigManager) {}

  /**
   * Store JWT token with metadata
   *
   * @param tokenInfo Token information including access token, expiration, user details
   */
  storeToken(tokenInfo: TokenInfo): void {
    this.config.set('auth.token', tokenInfo.access_token);
    this.config.set('auth.token_type', tokenInfo.token_type);
    this.config.set('auth.expires_at', tokenInfo.expires_at);
    this.config.set('auth.username', tokenInfo.username);
    this.config.set('auth.role', tokenInfo.role);

    // Also update top-level username for backwards compatibility
    this.config.set('username', tokenInfo.username);
  }

  /**
   * Retrieve stored token (returns null if expired or not found)
   *
   * @returns Token information or null if not authenticated
   */
  getToken(): TokenInfo | null {
    const token = this.config.get('auth.token');
    if (!token) {
      return null;
    }

    const tokenInfo: TokenInfo = {
      access_token: token,
      token_type: this.config.get('auth.token_type') || 'bearer',
      expires_at: this.config.get('auth.expires_at') || 0,
      username: this.config.get('auth.username') || '',
      role: this.config.get('auth.role') || ''
    };

    // Check if token is expired (with 5-minute buffer)
    if (this.isTokenExpired(tokenInfo)) {
      return null;
    }

    return tokenInfo;
  }

  /**
   * Check if token is expired (with 5-minute buffer for safety)
   *
   * @param tokenInfo Token information to check
   * @returns true if token is expired or will expire within 5 minutes
   */
  isTokenExpired(tokenInfo: TokenInfo): boolean {
    const now = Math.floor(Date.now() / 1000);
    const BUFFER_SECONDS = 5 * 60;  // 5-minute buffer

    return tokenInfo.expires_at <= now + BUFFER_SECONDS;
  }

  /**
   * Clear stored token (logout)
   */
  clearToken(): void {
    this.config.delete('auth');
  }

  /**
   * Check if user is logged in (valid token exists)
   *
   * @returns true if user has a valid, non-expired token
   */
  isLoggedIn(): boolean {
    return this.getToken() !== null;
  }

  /**
   * Get current username from token
   *
   * @returns Username or null if not logged in
   */
  getUsername(): string | null {
    const tokenInfo = this.getToken();
    return tokenInfo ? tokenInfo.username : null;
  }

  /**
   * Get current user role from token
   *
   * @returns User role or null if not logged in
   */
  getRole(): string | null {
    const tokenInfo = this.getToken();
    return tokenInfo ? tokenInfo.role : null;
  }

  /**
   * Get token expiration time as a human-readable string
   *
   * @returns Formatted expiration time or null if not logged in
   */
  getExpirationString(): string | null {
    const tokenInfo = this.getToken();
    if (!tokenInfo) {
      return null;
    }

    const expiresAt = new Date(tokenInfo.expires_at * 1000);
    return expiresAt.toLocaleString();
  }

  /**
   * Get minutes until token expiration
   *
   * @returns Minutes until expiration or null if not logged in
   */
  getMinutesUntilExpiration(): number | null {
    const tokenInfo = this.getToken();
    if (!tokenInfo) {
      return null;
    }

    const now = Math.floor(Date.now() / 1000);
    const secondsUntilExpiration = tokenInfo.expires_at - now;

    return Math.floor(secondsUntilExpiration / 60);
  }

  /**
   * Create TokenInfo from login response
   *
   * @param loginResponse Response from /auth/login endpoint
   * @returns TokenInfo object ready to be stored
   */
  static fromLoginResponse(loginResponse: {
    access_token: string;
    token_type: string;
    expires_in: number;
    user: {
      username: string;
      role: string;
    };
  }): TokenInfo {
    const now = Math.floor(Date.now() / 1000);

    return {
      access_token: loginResponse.access_token,
      token_type: loginResponse.token_type,
      expires_at: now + loginResponse.expires_in,
      username: loginResponse.user.username,
      role: loginResponse.user.role
    };
  }
}
