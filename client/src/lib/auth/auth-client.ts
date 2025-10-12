/**
 * Authentication Client
 *
 * HTTP client for authentication endpoints.
 * Wraps REST API calls to /auth/* endpoints.
 */

import axios, { AxiosInstance } from 'axios';

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

    const response = await this.client.get<UserListResponse>('/auth/admin/users', {
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
    const response = await this.client.get<UserResponse>(`/auth/admin/users/${userId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    return response.data;
  }

  /**
   * Create user (admin only)
   *
   * @param token JWT access token (must be admin role)
   * @param request User creation details
   * @returns Created user details
   * @throws 401 if token invalid/expired, 403 if not admin, 400 if validation fails
   */
  async createUser(token: string, request: UserCreateRequest): Promise<UserResponse> {
    const response = await this.client.post<UserResponse>('/auth/admin/users', request, {
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
      `/auth/admin/users/${userId}`,
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
    await this.client.delete(`/auth/admin/users/${userId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  }
}
