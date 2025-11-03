/**
 * OAuth 2.0 Type Definitions (ADR-054)
 *
 * Shared types for OAuth client flows:
 * - Device Authorization Grant (CLI)
 * - Client Credentials (MCP)
 */

/**
 * OAuth token response from token endpoint
 */
export interface OAuthTokenResponse {
  access_token: string;
  token_type: string;  // Always "Bearer"
  expires_in: number;  // Seconds until expiration (3600 = 1 hour)
  refresh_token?: string;  // Only for user-delegated grants (not client_credentials)
  scope: string;  // Space-separated scopes
}

/**
 * Device authorization response (RFC 8628)
 */
export interface DeviceAuthorizationResponse {
  device_code: string;  // Long code for polling
  user_code: string;  // Short human-friendly code (e.g., "ABCD-1234")
  verification_uri: string;  // URL where user enters code
  verification_uri_complete?: string;  // URL with code pre-filled
  expires_in: number;  // Seconds until codes expire (600 = 10 minutes)
  interval: number;  // Polling interval in seconds (5)
}

/**
 * Device code status
 */
export interface DeviceCodeStatus {
  status: 'pending' | 'authorized' | 'denied' | 'expired';
  user_code: string;
  expires_at: string;  // ISO 8601 timestamp
}

/**
 * OAuth error response (RFC 6749)
 */
export interface OAuthErrorResponse {
  error: string;  // Error code
  error_description?: string;  // Human-readable description
  error_uri?: string;  // URI with error information
}

/**
 * Stored OAuth token information
 */
export interface OAuthTokenInfo {
  access_token: string;
  token_type: string;
  expires_at: number;  // Unix timestamp (seconds)
  refresh_token?: string;
  scope: string;
  client_id: string;  // Which OAuth client this token belongs to
}

/**
 * OAuth grant types
 */
export type OAuthGrantType =
  | 'authorization_code'
  | 'urn:ietf:params:oauth:grant-type:device_code'
  | 'client_credentials'
  | 'refresh_token';

/**
 * OAuth client configuration
 */
export interface OAuthClientConfig {
  client_id: string;
  client_secret?: string;  // Only for confidential clients (MCP)
  grant_types: OAuthGrantType[];
  api_url: string;
}
