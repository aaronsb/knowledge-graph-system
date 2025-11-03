/**
 * OAuth Token Refresh Manager (ADR-054)
 *
 * Handles automatic token refresh using refresh_token grant.
 *
 * Note: Only works with grants that return refresh tokens (device flow, authorization code).
 * Client credentials grant does NOT receive refresh tokens - must re-authenticate instead.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import type { OAuthTokenResponse, OAuthTokenInfo, OAuthErrorResponse } from './oauth-types';
import { convertTokenResponse, isTokenExpired } from './oauth-utils';

export interface TokenRefreshCallbacks {
  onRefreshStart?: () => void;
  onRefreshSuccess?: (tokenInfo: OAuthTokenInfo) => void;
  onRefreshError?: (error: Error) => void;
}

export class TokenRefreshManager {
  private client: AxiosInstance;

  constructor(apiUrl: string) {
    this.client = axios.create({
      baseURL: apiUrl,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      timeout: 10000,  // 10 seconds
    });
  }

  /**
   * Refresh an expired access token using a refresh token
   *
   * POST /auth/oauth/token
   * Body: grant_type=refresh_token&refresh_token=<token>&client_id=<client_id>
   *
   * Returns new access token and same refresh token
   *
   * @param tokenInfo - Current token information (must have refresh_token)
   * @param callbacks - Optional callbacks for progress tracking
   * @returns New token information with refreshed access token
   */
  async refreshToken(
    tokenInfo: OAuthTokenInfo,
    callbacks?: TokenRefreshCallbacks
  ): Promise<OAuthTokenInfo> {
    if (!tokenInfo.refresh_token) {
      throw new Error('Cannot refresh token: No refresh token available (client_credentials grant?)');
    }

    callbacks?.onRefreshStart?.();

    try {
      const params = new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: tokenInfo.refresh_token,
        client_id: tokenInfo.client_id,
      });

      const response = await this.client.post<OAuthTokenResponse>(
        '/auth/oauth/token',
        params.toString()
      );

      // Convert response and preserve client_id
      const newTokenInfo = convertTokenResponse(response.data, tokenInfo.client_id);
      callbacks?.onRefreshSuccess?.(newTokenInfo);
      return newTokenInfo;

    } catch (error) {
      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<OAuthErrorResponse>;
        const errorMessage = axiosError.response?.data?.error_description ||
                            axiosError.response?.data?.error ||
                            axiosError.message;

        const err = new Error(`Token refresh failed: ${errorMessage}`);
        callbacks?.onRefreshError?.(err);
        throw err;
      }

      const err = error instanceof Error ? error : new Error('Unknown error during token refresh');
      callbacks?.onRefreshError?.(err);
      throw err;
    }
  }

  /**
   * Automatically refresh token if expired or about to expire
   *
   * Checks if token is expired (or will expire within buffer period).
   * If so, refreshes it. Otherwise, returns the original token.
   *
   * @param tokenInfo - Current token information
   * @param bufferSeconds - Refresh if expiring within this many seconds (default: 60)
   * @param callbacks - Optional callbacks for progress tracking
   * @returns Token information (refreshed if needed)
   */
  async autoRefresh(
    tokenInfo: OAuthTokenInfo | null,
    bufferSeconds: number = 60,
    callbacks?: TokenRefreshCallbacks
  ): Promise<OAuthTokenInfo> {
    if (!tokenInfo) {
      throw new Error('Cannot refresh token: No token information available');
    }

    // Check if token needs refresh
    if (!isTokenExpired(tokenInfo, bufferSeconds)) {
      // Token is still valid, no refresh needed
      return tokenInfo;
    }

    // Token expired or about to expire - refresh it
    return await this.refreshToken(tokenInfo, callbacks);
  }

  /**
   * Revoke a token (access or refresh)
   *
   * POST /auth/oauth/revoke
   * Body: token=<token>&token_type_hint=access_token|refresh_token&client_id=<client_id>
   *
   * @param token - Token to revoke (access_token or refresh_token)
   * @param tokenTypeHint - Type of token ('access_token' or 'refresh_token')
   * @param clientId - OAuth client ID
   */
  async revokeToken(
    token: string,
    tokenTypeHint?: 'access_token' | 'refresh_token',
    clientId?: string
  ): Promise<void> {
    try {
      const params = new URLSearchParams({
        token: token,
        ...(tokenTypeHint && { token_type_hint: tokenTypeHint }),
        ...(clientId && { client_id: clientId }),
      });

      await this.client.post('/auth/oauth/revoke', params.toString());
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<OAuthErrorResponse>;
        const errorMessage = axiosError.response?.data?.error_description ||
                            axiosError.response?.data?.error ||
                            axiosError.message;
        throw new Error(`Token revocation failed: ${errorMessage}`);
      }
      throw error;
    }
  }

  /**
   * Revoke all tokens for a user (access and refresh)
   *
   * Convenience method to revoke both access and refresh tokens
   *
   * @param tokenInfo - Token information
   */
  async revokeAll(tokenInfo: OAuthTokenInfo): Promise<void> {
    // Revoke access token
    await this.revokeToken(tokenInfo.access_token, 'access_token', tokenInfo.client_id);

    // Revoke refresh token if present
    if (tokenInfo.refresh_token) {
      await this.revokeToken(tokenInfo.refresh_token, 'refresh_token', tokenInfo.client_id);
    }
  }
}
