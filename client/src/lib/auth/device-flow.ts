/**
 * OAuth Device Authorization Grant Flow (ADR-054)
 *
 * Implements RFC 8628 Device Authorization Grant for CLI authentication.
 *
 * Flow:
 * 1. Request device and user codes from server
 * 2. Display user_code to user with verification URL
 * 3. Poll token endpoint until user authorizes (or timeout/denial)
 * 4. Store access and refresh tokens
 *
 * Usage:
 *   const flow = new DeviceAuthFlow(apiUrl, clientId);
 *   const codes = await flow.requestDeviceCode();
 *   console.log(`Go to ${codes.verification_uri} and enter: ${codes.user_code}`);
 *   const tokens = await flow.pollForToken(codes.device_code, codes.interval);
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  DeviceAuthorizationResponse,
  OAuthTokenResponse,
  OAuthTokenInfo,
  OAuthErrorResponse,
} from './oauth-types';
import { convertTokenResponse } from './oauth-utils';

export interface DeviceFlowCallbacks {
  onDeviceCodeReceived?: (codes: DeviceAuthorizationResponse) => void;
  onPollStart?: () => void;
  onPollTick?: (attempt: number) => void;
  onAuthorizationPending?: () => void;
  onSlowDown?: () => void;
  onSuccess?: (tokenInfo: OAuthTokenInfo) => void;
  onError?: (error: Error) => void;
}

export class DeviceAuthFlow {
  private client: AxiosInstance;
  private clientId: string;

  constructor(apiUrl: string, clientId: string = 'kg-cli') {
    this.clientId = clientId;
    this.client = axios.create({
      baseURL: apiUrl,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      timeout: 10000,  // 10 seconds for API calls
    });
  }

  /**
   * Step 1: Request device and user codes from the authorization server
   *
   * POST /auth/oauth/device
   * Body: client_id=kg-cli&scope=read:* write:*
   *
   * Returns codes and verification URL for the user
   */
  async requestDeviceCode(scope: string = 'read:* write:*'): Promise<DeviceAuthorizationResponse> {
    try {
      const params = new URLSearchParams({
        client_id: this.clientId,
        scope: scope,
      });

      const response = await this.client.post<DeviceAuthorizationResponse>(
        '/auth/oauth/device',
        params.toString()
      );

      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<OAuthErrorResponse>;
        const errorMessage = axiosError.response?.data?.error_description ||
                            axiosError.response?.data?.error ||
                            axiosError.message;
        throw new Error(`Failed to request device code: ${errorMessage}`);
      }
      throw error;
    }
  }

  /**
   * Step 2: Poll token endpoint until user authorizes
   *
   * POST /auth/oauth/token
   * Body: grant_type=urn:ietf:params:oauth:grant-type:device_code&device_code=<code>&client_id=kg-cli
   *
   * Polls every `interval` seconds until:
   * - User authorizes (returns tokens)
   * - User denies (throws error)
   * - Device code expires (throws error)
   * - Timeout reached (throws error)
   *
   * @param deviceCode - Device code from requestDeviceCode()
   * @param interval - Polling interval in seconds (from requestDeviceCode())
   * @param maxAttempts - Maximum number of poll attempts (default: 120 = 10 minutes at 5s interval)
   * @param callbacks - Optional callbacks for progress tracking
   * @returns OAuth token information
   */
  async pollForToken(
    deviceCode: string,
    interval: number = 5,
    maxAttempts: number = 120,
    callbacks?: DeviceFlowCallbacks
  ): Promise<OAuthTokenInfo> {
    callbacks?.onPollStart?.();

    let attempt = 0;
    let currentInterval = interval * 1000;  // Convert to milliseconds

    while (attempt < maxAttempts) {
      attempt++;
      callbacks?.onPollTick?.(attempt);

      try {
        // Wait before polling (except first attempt)
        if (attempt > 1) {
          await this.sleep(currentInterval);
        }

        const params = new URLSearchParams({
          grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
          device_code: deviceCode,
          client_id: this.clientId,
        });

        const response = await this.client.post<OAuthTokenResponse>(
          '/auth/oauth/token',
          params.toString()
        );

        // Success! User authorized
        const tokenInfo = convertTokenResponse(response.data, this.clientId);
        callbacks?.onSuccess?.(tokenInfo);
        return tokenInfo;

      } catch (error) {
        if (axios.isAxiosError(error)) {
          const axiosError = error as AxiosError<OAuthErrorResponse>;
          const errorCode = axiosError.response?.data?.error;
          const errorDescription = axiosError.response?.data?.error_description;

          // Handle OAuth error responses
          if (errorCode === 'authorization_pending') {
            // User hasn't completed authorization yet - continue polling
            callbacks?.onAuthorizationPending?.();
            continue;
          } else if (errorCode === 'slow_down') {
            // Server requested slower polling - increase interval by 5 seconds
            currentInterval += 5000;
            callbacks?.onSlowDown?.();
            continue;
          } else if (errorCode === 'access_denied') {
            // User explicitly denied authorization
            const err = new Error('User denied authorization');
            callbacks?.onError?.(err);
            throw err;
          } else if (errorCode === 'expired_token' || errorDescription?.includes('expired')) {
            // Device code expired
            const err = new Error('Device code expired. Please try again.');
            callbacks?.onError?.(err);
            throw err;
          } else {
            // Other OAuth error
            const err = new Error(`OAuth error: ${errorDescription || errorCode || axiosError.message}`);
            callbacks?.onError?.(err);
            throw err;
          }
        }

        // Non-axios error
        const err = error instanceof Error ? error : new Error('Unknown error during polling');
        callbacks?.onError?.(err);
        throw err;
      }
    }

    // Max attempts reached
    const err = new Error('Polling timeout: User did not authorize within the expected time');
    callbacks?.onError?.(err);
    throw err;
  }

  /**
   * Complete device flow: request codes and poll for token
   *
   * Convenience method that combines requestDeviceCode() and pollForToken()
   *
   * @param scope - OAuth scopes to request
   * @param callbacks - Optional callbacks for progress tracking
   * @returns OAuth token information
   */
  async authenticate(scope: string = 'read:* write:*', callbacks?: DeviceFlowCallbacks): Promise<OAuthTokenInfo> {
    // Step 1: Get device and user codes
    const codes = await this.requestDeviceCode(scope);
    callbacks?.onDeviceCodeReceived?.(codes);

    // Step 2: Poll for token
    return await this.pollForToken(codes.device_code, codes.interval, undefined, callbacks);
  }

  /**
   * Sleep utility for polling
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
