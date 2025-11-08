/**
 * OAuth Client Credentials Grant Flow (ADR-054)
 *
 * Implements RFC 6749 Client Credentials Grant for machine-to-machine authentication (MCP server).
 *
 * Flow:
 * 1. Exchange client_id + client_secret for access token
 * 2. Use access token for API requests
 * 3. Re-authenticate when token expires (no refresh token)
 *
 * Usage:
 *   const flow = new ClientCredentialsFlow(apiUrl, clientId, clientSecret);
 *   const tokenInfo = await flow.authenticate();
 *   // Use tokenInfo.access_token for API requests
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import type { OAuthTokenResponse, OAuthTokenInfo, OAuthErrorResponse } from './oauth-types';
import { convertTokenResponse } from './oauth-utils';

export interface ClientCredentialsCallbacks {
  onSuccess?: (tokenInfo: OAuthTokenInfo) => void;
  onError?: (error: Error) => void;
}

export class ClientCredentialsFlow {
  private client: AxiosInstance;
  private clientId: string;
  private clientSecret: string;

  constructor(apiUrl: string, clientId: string = 'kg-mcp', clientSecret: string) {
    if (!clientSecret) {
      throw new Error('Client secret is required for client credentials flow');
    }

    this.clientId = clientId;
    this.clientSecret = clientSecret;
    this.client = axios.create({
      baseURL: apiUrl,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      timeout: 10000,  // 10 seconds
    });
  }

  /**
   * Authenticate using client credentials
   *
   * POST /auth/oauth/token
   * Body: grant_type=client_credentials&client_id=kg-mcp&client_secret=<secret>&scope=read:* write:*
   *
   * Returns access token (no refresh token for client_credentials grant)
   *
   * @param scope - OAuth scopes to request (default: "read:* write:*")
   * @param callbacks - Optional callbacks for success/error handling
   * @returns OAuth token information
   */
  async authenticate(
    scope: string = 'read:* write:*',
    callbacks?: ClientCredentialsCallbacks
  ): Promise<OAuthTokenInfo> {
    try {
      const params = new URLSearchParams({
        grant_type: 'client_credentials',
        client_id: this.clientId,
        client_secret: this.clientSecret,
        scope: scope,
      });

      const response = await this.client.post<OAuthTokenResponse>(
        '/auth/oauth/token',
        params.toString()
      );

      const tokenInfo = convertTokenResponse(response.data, this.clientId);
      callbacks?.onSuccess?.(tokenInfo);
      return tokenInfo;

    } catch (error) {
      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<OAuthErrorResponse>;
        const errorMessage = axiosError.response?.data?.error_description ||
                            axiosError.response?.data?.error ||
                            axiosError.message;

        // Check for authentication failure
        if (axiosError.response?.status === 401) {
          const err = new Error(`Authentication failed: Invalid client credentials`);
          callbacks?.onError?.(err);
          throw err;
        }

        const err = new Error(`Client credentials authentication failed: ${errorMessage}`);
        callbacks?.onError?.(err);
        throw err;
      }

      const err = error instanceof Error ? error : new Error('Unknown authentication error');
      callbacks?.onError?.(err);
      throw err;
    }
  }

  /**
   * Check if client credentials are valid
   *
   * Attempts to authenticate with the provided credentials.
   * Returns true if successful, false otherwise.
   *
   * @returns true if credentials are valid
   */
  async validateCredentials(): Promise<boolean> {
    try {
      await this.authenticate();
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Set new client secret
   *
   * Use this after rotating the client secret via:
   * POST /auth/oauth/clients/{client_id}/rotate-secret
   *
   * @param newSecret - The new client secret
   */
  setClientSecret(newSecret: string): void {
    if (!newSecret) {
      throw new Error('Client secret cannot be empty');
    }
    this.clientSecret = newSecret;
  }
}
