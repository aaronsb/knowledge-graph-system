/**
 * Account Tab Component
 *
 * OAuth client management for the current user.
 */

import React, { useState, useEffect } from 'react';
import {
  Key,
  Plus,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { Section, OAuthClientCard, NewClientCredentialsDisplay } from './components';
import type { OAuthClient, NewClientCredentials } from './types';

interface AccountTabProps {
  onError: (error: string) => void;
}

export const AccountTab: React.FC<AccountTabProps> = ({ onError }) => {
  const [myClients, setMyClients] = useState<OAuthClient[]>([]);
  const [loading, setLoading] = useState(true);
  const [creatingClient, setCreatingClient] = useState(false);
  const [newClientName, setNewClientName] = useState('');
  const [newCredentials, setNewCredentials] = useState<NewClientCredentials | null>(null);
  const [deletingClientId, setDeletingClientId] = useState<string | null>(null);
  const [rotatingClientId, setRotatingClientId] = useState<string | null>(null);

  // Load my OAuth clients
  useEffect(() => {
    loadClients();
  }, []);

  const loadClients = async () => {
    setLoading(true);
    try {
      const clients = await apiClient.getMyOAuthClients();
      setMyClients(clients);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to load clients');
    } finally {
      setLoading(false);
    }
  };

  // Create new client
  const handleCreateClient = async () => {
    if (!newClientName.trim()) return;

    setCreatingClient(true);
    try {
      const result = await apiClient.createPersonalOAuthClient({
        client_name: newClientName.trim(),
      });
      setNewCredentials(result);
      setNewClientName('');
      // Refresh list
      const clients = await apiClient.getMyOAuthClients();
      setMyClients(clients);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to create client');
    } finally {
      setCreatingClient(false);
    }
  };

  // Delete client
  const handleDeleteClient = async (clientId: string) => {
    setDeletingClientId(clientId);
    try {
      await apiClient.deletePersonalOAuthClient(clientId);
      setMyClients(prev => prev.filter(c => c.client_id !== clientId));
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to delete client');
    } finally {
      setDeletingClientId(null);
    }
  };

  // Rotate client secret
  const handleRotateSecret = async (clientId: string) => {
    setRotatingClientId(clientId);
    try {
      const result = await apiClient.rotatePersonalOAuthClientSecret(clientId);
      setNewCredentials({
        client_id: result.client_id,
        client_name: result.client_name || clientId,
        client_secret: result.client_secret,
      });
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to rotate secret');
    } finally {
      setRotatingClientId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <>
      {/* New credentials display */}
      {newCredentials && (
        <NewClientCredentialsDisplay
          credentials={newCredentials}
          onDismiss={() => setNewCredentials(null)}
        />
      )}

      {/* Create new client */}
      <Section
        title="Create OAuth Client"
        icon={<Plus className="w-5 h-5" />}
      >
        <p className="text-sm text-muted-foreground mb-4">
          Create a personal OAuth client for CLI tools, scripts, or other applications.
          Each client gets its own credentials for secure API access.
        </p>
        <div className="flex gap-3">
          <input
            type="text"
            value={newClientName}
            onChange={(e) => setNewClientName(e.target.value)}
            placeholder="Client name (e.g., 'My Laptop CLI')"
            className="flex-1 px-3 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            onKeyDown={(e) => e.key === 'Enter' && handleCreateClient()}
          />
          <button
            onClick={handleCreateClient}
            disabled={creatingClient || !newClientName.trim()}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {creatingClient ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            Create
          </button>
        </div>
      </Section>

      {/* My clients */}
      <Section
        title="My OAuth Clients"
        icon={<Key className="w-5 h-5" />}
        action={
          <button
            onClick={loadClients}
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        }
      >
        {myClients.length === 0 ? (
          <p className="text-muted-foreground text-center py-8">
            No OAuth clients yet. Create one above to get started.
          </p>
        ) : (
          <div className="space-y-3">
            {myClients.map((client) => (
              <OAuthClientCard
                key={client.client_id}
                client={client}
                onDelete={handleDeleteClient}
                onRotate={handleRotateSecret}
                isDeleting={deletingClientId === client.client_id}
                isRotating={rotatingClientId === client.client_id}
              />
            ))}
          </div>
        )}
      </Section>
    </>
  );
};

export default AccountTab;
