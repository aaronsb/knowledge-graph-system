/**
 * Authentication Client
 *
 * HTTP client for authentication endpoints.
 * Wraps REST API calls to /auth/* endpoints.
 */

import axios, { AxiosInstance } from 'axios';
import { OAuthTokenResponse } from './oauth-types.js';

// ========== Request/Response Types ==========

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: number;
    username: string;
    role: string;
    created_at: string;
    last_login: string | null;
    disabled: boolean;
  };
}

export interface UserCreateRequest {
  username: string;
  password: string;
  role: 'read_only' | 'contributor' | 'curator' | 'admin';
}

export interface UserUpdateRequest {
  role?: 'read_only' | 'contributor' | 'curator' | 'admin';
  password?: string;
  disabled?: boolean;
}

export interface UserResponse {
  id: number;
  username: string;
  role: string;
  created_at: string;
  last_login: string | null;
  disabled: boolean;
}

export interface UserListResponse {
  users: UserResponse[];
  total: number;
  skip: number;
  limit: number;
}

export interface APIKeyCreateRequest {
  name: string;
  scopes?: string[];
  expires_at?: string;  // ISO 8601 datetime
}

export interface APIKeyResponse {
  id: number;
  name: string;
  key_prefix: string;
  scopes: string[];
  created_at: string;
  last_used: string | null;
  expires_at: string | null;
  key?: string;  // Only present on creation!
}

export interface APIKeyListResponse {
  api_keys: APIKeyResponse[];
  count: number;
}

// ========== OAuth 2.0 Types (ADR-054) ==========

export interface OAuthClientCreateRequest {
  username: string;
  password: string;
  client_name?: string;
  scope?: string;
}

export interface OAuthClientResponse {
  client_id: string;
  client_secret: string;
  client_name: string;
  client_type: string;
  grant_types: string[];
  scopes: string[];
  created_at: string;
  created_by: number;
}

export interface OAuthTokenRequest {
  grant_type: 'client_credentials';
  client_id: string;
  client_secret: string;
  scope?: string;
}

// Note: OAuthTokenResponse is imported from './oauth-types.js'

// ========== Auth Client Class ==========

export class AuthClient {
  private client: AxiosInstance;

  constructor(baseUrl: string) {
    this.client = axios.create({
      baseURL: baseUrl,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }

  // ========== Public Endpoints (No Auth) ==========

  /**
   * Login with username/password (OAuth2 password flow)
   *
   * @deprecated Use createPersonalOAuthClient() instead (ADR-054 unified OAuth)
   * @param request Username and password
   * @returns JWT token and user details
   * @throws 401 if credentials invalid, 400 if validation fails
   */
  async login(request: LoginRequest): Promise<LoginResponse> {
    // OAuth2 password flow requires application/x-www-form-urlencoded
    const formData = new URLSearchParams();
    formData.append('username', request.username);
    formData.append('password', request.password);

    const response = await this.client.post<LoginResponse>('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });

    return response.data;
  }

  /**
   * Create a personal OAuth client (ADR-054 - GitHub CLI-style authentication)
   *
   * This is the preferred authentication method for CLI tools.
   * Flow:
   * 1. User provides username + password
   * 2. Server creates long-lived OAuth client credentials
   * 3. Client stores client_id + client_secret
   * 4. Future requests use client credentials grant
   *
   * @param request Username, password, and optional client name/scope
   * @returns OAuth client credentials (client_secret shown only once!)
   * @throws 401 if credentials invalid, 400 if validation fails
   */
  async createPersonalOAuthClient(request: OAuthClientCreateRequest): Promise<OAuthClientResponse> {
    // OAuth endpoint requires application/x-www-form-urlencoded
    const formData = new URLSearchParams();
    formData.append('username', request.username);
    formData.append('password', request.password);

    if (request.client_name) {
      formData.append('client_name', request.client_name);
    }

    if (request.scope) {
      formData.append('scope', request.scope);
    }

    const response = await this.client.post<OAuthClientResponse>(
      '/auth/oauth/clients/personal',
      formData,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    );

    return response.data;
  }

  /**
   * Get OAuth access token using client credentials grant (ADR-054)
   *
   * Use this after creating a personal OAuth client to get access tokens.
   * Access tokens are short-lived and should be refreshed as needed.
   *
   * @param request Client credentials (client_id, client_secret)
   * @returns OAuth access token
   * @throws 401 if client credentials invalid
   */
  async getOAuthToken(request: OAuthTokenRequest): Promise<OAuthTokenResponse> {
    const formData = new URLSearchParams();
    formData.append('grant_type', 'client_credentials');
    formData.append('client_id', request.client_id);
    formData.append('client_secret', request.client_secret);

    if (request.scope) {
      formData.append('scope', request.scope);
    }

    const response = await this.client.post<OAuthTokenResponse>(
      '/auth/oauth/token',
      formData,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    );

    return response.data;
  }

  /**
   * Delete a personal OAuth client (ADR-054)
   *
   * Called by `kg logout` to revoke OAuth credentials.
   * Requires authentication with a valid access token.
   *
   * @param token Access token for authentication
   * @param clientId Client ID to delete
   * @throws 401 if token invalid, 403 if not owner, 404 if client not found
   */
  async deletePersonalOAuthClient(token: string, clientId: string): Promise<void> {
    await this.client.delete(`/auth/oauth/clients/personal/${clientId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  }

  /**
   * Register new user
   *
   * Note: In production, this endpoint may be restricted to admins.
   * For now, it's public to allow initial user creation.
   *
   * @param request User creation details
   * @returns Created user details
   * @throws 400 if validation fails, 409 if username taken
   */
  async register(request: UserCreateRequest): Promise<UserResponse> {
    const response = await this.client.post<UserResponse>('/auth/register', request);
    return response.data;
  }

  // ========== Authenticated Endpoints (JWT Required) ==========

  /**
   * Validate current token and get user profile
   *
   * @param token JWT access token
   * @returns Current user details
   * @throws 401 if token invalid/expired
   */
  async validateToken(token: string): Promise<UserResponse> {
    const response = await this.client.get<UserResponse>('/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  /**
   * Update current user profile
   *
   * @param token JWT access token
   * @param updates Fields to update (username, password)
   * @returns Updated user details
   * @throws 401 if token invalid/expired, 400 if validation fails
   */
  async updateCurrentUser(
    token: string,
    updates: { username?: string; password?: string }
  ): Promise<UserResponse> {
    const response = await this.client.put<UserResponse>('/auth/me', updates, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  // ========== API Key Management ==========

  /**
   * Create API key for current user
   *
   * @param token JWT access token
   * @param request API key details
   * @returns API key response (includes plaintext key, shown only once!)
   * @throws 401 if token invalid/expired
   */
  async createAPIKey(token: string, request: APIKeyCreateRequest): Promise<APIKeyResponse> {
    const response = await this.client.post<APIKeyResponse>('/auth/api-keys', request, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  /**
   * List API keys for current user
   *
   * @param token JWT access token
   * @returns List of API keys
   * @throws 401 if token invalid/expired
   */
  async listAPIKeys(token: string): Promise<APIKeyListResponse> {
    const response = await this.client.get<APIKeyListResponse>('/auth/api-keys', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  /**
   * Revoke API key
   *
   * @param token JWT access token
   * @param keyId API key ID to revoke
   * @throws 401 if token invalid/expired, 404 if key not found
   */
  async revokeAPIKey(token: string, keyId: number): Promise<void> {
    await this.client.delete(`/auth/api-keys/${keyId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  }

  // ========== Admin Endpoints (Role Check) ==========

  /**
   * List all users (admin only)
   *
   * @param token JWT access token (must be admin role)
   * @param skip Number of users to skip (pagination)
   * @param limit Maximum number of users to return
   * @param role Filter by role
   * @returns Paginated list of users
   * @throws 401 if token invalid/expired, 403 if not admin
   */
  async listUsers(
    token: string,
    skip: number = 0,
    limit: number = 50,
    role?: string
  ): Promise<UserListResponse> {
    const params: any = { skip, limit };
    if (role) {
      params.role = role;
    }

    const response = await this.client.get<UserListResponse>('/users', {
      params,
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  /**
   * Get user by ID (admin only)
   *
   * @param token JWT access token (must be admin role)
   * @param userId User ID
   * @returns User details
   * @throws 401 if token invalid/expired, 403 if not admin, 404 if user not found
   */
  async getUser(token: string, userId: number): Promise<UserResponse> {
    const response = await this.client.get<UserResponse>(`/users/${userId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  /**
   * Create user (admin only)
   *
   * Note: Uses /auth/register endpoint since there's no dedicated admin create endpoint.
   * Admins can create users with any role.
   *
   * @param token JWT access token (must be admin role)
   * @param request User creation details
   * @returns Created user details
   * @throws 401 if token invalid/expired, 403 if not admin, 400 if validation fails
   */
  async createUser(token: string, request: UserCreateRequest): Promise<UserResponse> {
    const response = await this.client.post<UserResponse>('/auth/register', request, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  /**
   * Update user (admin only)
   *
   * @param token JWT access token (must be admin role)
   * @param userId User ID to update
   * @param request Fields to update
   * @returns Updated user details
   * @throws 401 if token invalid/expired, 403 if not admin, 404 if user not found
   */
  async updateUser(
    token: string,
    userId: number,
    request: UserUpdateRequest
  ): Promise<UserResponse> {
    const response = await this.client.put<UserResponse>(
      `/users/${userId}`,
      request,
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    );

    return response.data;
  }

  /**
   * Delete user (admin only, cannot delete self)
   *
   * @param token JWT access token (must be admin role)
   * @param userId User ID to delete
   * @throws 401 if token invalid/expired, 403 if not admin, 404 if user not found
   * @throws 400 if trying to delete self
   */
  async deleteUser(token: string, userId: number): Promise<void> {
    await this.client.delete(`/users/${userId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  }
}
