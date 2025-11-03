/**
 * OAuth Callback Handler
 *
 * Handles the OAuth 2.0 authorization code callback:
 * 1. Extracts code and state from URL params
 * 2. Exchanges code for access token (via authStore)
 * 3. Redirects to main app view
 */

import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

export const OAuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { handleCallback } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const processCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const errorParam = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');

      // Check for OAuth error response
      if (errorParam) {
        setError(errorDescription || errorParam);
        setTimeout(() => navigate('/'), 3000);
        return;
      }

      // Exchange code for token
      if (code) {
        try {
          await handleCallback(code, state || undefined);
          // Redirect to main app
          navigate('/');
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Authentication failed');
          setTimeout(() => navigate('/'), 3000);
        }
      } else {
        setError('No authorization code received');
        setTimeout(() => navigate('/'), 3000);
      }
    };

    processCallback();
  }, [searchParams, handleCallback, navigate]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="text-center max-w-md">
          <div className="text-destructive text-5xl mb-4">⚠️</div>
          <h2 className="text-2xl font-semibold mb-2">Authentication Failed</h2>
          <p className="text-muted-foreground mb-4">{error}</p>
          <p className="text-sm text-muted-foreground">Redirecting to main page...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center h-screen bg-background">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
        <h2 className="text-xl font-semibold mb-2">Completing Login</h2>
        <p className="text-muted-foreground">Exchanging authorization code for access token...</p>
      </div>
    </div>
  );
};
