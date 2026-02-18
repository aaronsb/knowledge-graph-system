/**
 * HomeWorkspace
 *
 * Welcome page and system overview.
 * Shows login prompt when not authenticated.
 * Shows system status and quick actions when authenticated.
 */

import React, { useState, useEffect } from 'react';
import {
  Home,
  LogIn,
  Network,
  Upload,
  ListTodo,
  Database,
  Activity,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { LoginModal } from '../auth/LoginModal';
import { apiClient } from '../../api/client';
import { GraphAnimation } from './GraphAnimation';
import { NavigationGraph } from './NavigationGraph';

interface SystemStatus {
  database?: {
    concepts: number;
    relationships: number;
    sources: number;
    ontologies: number;
  };
  health?: boolean;
  epoch?: number;
}

/** Welcome page showing login prompt (unauthenticated) or system status dashboard
 *  with quick actions and NavigationGraph workstation guide (authenticated).
 *  @verified b38d816f */
export const HomeWorkspace: React.FC = () => {
  const { isAuthenticated, user } = useAuthStore();
  const navigate = useNavigate();
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(false);

  // Load system status when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      loadStatus();
    }
  }, [isAuthenticated]);

  const loadStatus = async () => {
    setLoading(true);
    try {
      // Load health, stats, ontologies, and API info in parallel
      const [health, stats, ontologies, apiInfo] = await Promise.all([
        apiClient.healthCheck().catch(err => {
          console.error('Health check failed:', err);
          return { status: 'error' };
        }),
        apiClient.getDatabaseStats().catch(err => {
          console.error('Database stats failed:', err);
          return null;
        }),
        apiClient.listOntologies().catch(err => {
          console.error('Ontologies fetch failed:', err);
          return { ontologies: [], count: 0 };
        }),
        apiClient.getApiInfo().catch(err => {
          console.error('API info failed:', err);
          return { epoch: 0, status: 'error' };
        }),
      ]);

      // Parse stats response: { nodes: { concepts: X, sources: Y }, relationships: { total: N } }
      const concepts = stats?.nodes?.concepts || 0;
      const sources = stats?.nodes?.sources || 0;
      const relationships = stats?.relationships?.total || 0;
      const ontologyCount = ontologies?.count || 0;

      // Accept both 'healthy' and 'degraded' as online
      // 'degraded' means API works but non-critical component (like Garage) is down
      const isOnline = health.status === 'healthy' || health.status === 'degraded';

      setStatus({
        health: isOnline,
        epoch: apiInfo.epoch || 0,
        database: {
          concepts,
          relationships,
          sources,
          ontologies: ontologyCount,
        },
      });
    } catch (err) {
      console.error('Failed to load status:', err);
      setStatus({ health: false });
    } finally {
      setLoading(false);
    }
  };

  // Quick action cards - using semantic theme colors
  const quickActions = [
    {
      icon: Network,
      label: 'Explore Graph',
      description: 'Interactive 2D visualization',
      path: '/explore/2d',
      color: 'text-primary',
      bg: 'bg-primary/10',
    },
    {
      icon: Upload,
      label: 'Ingest Content',
      description: 'Upload documents',
      path: '/ingest',
      color: 'text-status-active',
      bg: 'bg-status-active/10',
    },
    {
      icon: ListTodo,
      label: 'View Jobs',
      description: 'Monitor extractions',
      path: '/jobs',
      color: 'text-status-warning',
      bg: 'bg-status-warning/10',
    },
  ];

  // Not authenticated - show welcome and login
  if (!isAuthenticated) {
    return (
      <div className="h-full flex flex-col bg-background relative overflow-hidden">
        {/* Animated Graph Background - positioned behind everything */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="opacity-20 dark:opacity-30">
            <GraphAnimation width={600} height={600} />
          </div>
        </div>

        <div className="flex-1 flex items-center justify-center p-8 relative z-10">
          <div className="max-w-lg text-center">
            {/* Logo/Icon */}
            <div className="mb-8">
              <div className="w-24 h-24 mx-auto rounded-2xl bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center shadow-lg backdrop-blur-sm">
                <Network className="w-12 h-12 text-white" />
              </div>
            </div>

            {/* Welcome Text */}
            <h1 className="text-3xl font-bold text-foreground dark:text-gray-100 mb-4">
              Knowledge Graph System
            </h1>
            <p className="text-lg text-muted-foreground dark:text-gray-400 mb-8">
              Transform documents into interconnected concept graphs.
              Explore semantic relationships beyond sequential reading.
            </p>

            {/* Login Button */}
            <button
              onClick={() => setShowLoginModal(true)}
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors shadow-md"
            >
              <LogIn className="w-5 h-5" />
              Sign In to Continue
            </button>

            {/* Features */}
            <div className="mt-12 grid grid-cols-3 gap-4 text-sm">
              <div className="p-4 rounded-lg bg-card border border-border dark:border-gray-800">
                <Database className="w-6 h-6 mx-auto mb-2 text-status-info" />
                <div className="font-medium text-card-foreground dark:text-gray-200">Graph Database</div>
                <div className="text-xs text-muted-foreground dark:text-gray-500">Apache AGE</div>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border dark:border-gray-800">
                <Activity className="w-6 h-6 mx-auto mb-2 text-status-active" />
                <div className="font-medium text-card-foreground dark:text-gray-200">LLM Extraction</div>
                <div className="text-xs text-muted-foreground dark:text-gray-500">GPT-4 / Claude</div>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border dark:border-gray-800">
                <Network className="w-6 h-6 mx-auto mb-2 text-purple-500 dark:text-purple-400" />
                <div className="font-medium text-card-foreground dark:text-gray-200">Vector Search</div>
                <div className="text-xs text-muted-foreground dark:text-gray-500">Semantic similarity</div>
              </div>
            </div>
          </div>
        </div>

        <LoginModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} />
      </div>
    );
  }

  // Authenticated - show dashboard
  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="flex-none p-6 border-b border-border dark:border-gray-800">
        <div className="flex items-center gap-3">
          <Home className="w-6 h-6 text-primary" />
          <div>
            <h1 className="text-xl font-semibold text-foreground dark:text-gray-100">
              Welcome back, {user?.username || 'User'}
            </h1>
            <p className="text-sm text-muted-foreground dark:text-gray-400">
              Knowledge Graph Workstation
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto space-y-8">
          {/* System Status */}
          <section>
            <h2 className="text-lg font-semibold text-foreground dark:text-gray-200 mb-4">
              System Status
            </h2>
            {loading ? (
              <div className="flex items-center gap-2 text-muted-foreground dark:text-gray-400">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading status...
              </div>
            ) : status ? (
              <div className="grid grid-cols-6 gap-4">
                <div className="p-4 rounded-lg bg-card border border-border dark:border-gray-800">
                  <div className="flex items-center gap-2 mb-2">
                    {status.health ? (
                      <CheckCircle2 className="w-5 h-5 text-status-active" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-500" />
                    )}
                    <span className="text-sm font-medium text-muted-foreground dark:text-gray-400">API</span>
                  </div>
                  <div className="text-2xl font-bold text-card-foreground dark:text-gray-200">
                    {status.health ? 'Online' : 'Offline'}
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-card border border-border dark:border-gray-800">
                  <div className="text-sm font-medium text-muted-foreground dark:text-gray-400 mb-2">
                    Ontologies
                  </div>
                  <div className="text-2xl font-bold text-card-foreground dark:text-gray-200">
                    {status.database?.ontologies?.toLocaleString() || 0}
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-card border border-border dark:border-gray-800">
                  <div className="text-sm font-medium text-muted-foreground dark:text-gray-400 mb-2">
                    Concepts
                  </div>
                  <div className="text-2xl font-bold text-card-foreground dark:text-gray-200">
                    {status.database?.concepts?.toLocaleString() || 0}
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-card border border-border dark:border-gray-800">
                  <div className="text-sm font-medium text-muted-foreground dark:text-gray-400 mb-2">
                    Relationships
                  </div>
                  <div className="text-2xl font-bold text-card-foreground dark:text-gray-200">
                    {status.database?.relationships?.toLocaleString() || 0}
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-card border border-border dark:border-gray-800">
                  <div className="text-sm font-medium text-muted-foreground dark:text-gray-400 mb-2">
                    Sources
                  </div>
                  <div className="text-2xl font-bold text-card-foreground dark:text-gray-200">
                    {status.database?.sources?.toLocaleString() || 0}
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-card border border-border dark:border-gray-800">
                  <div className="text-sm font-medium text-muted-foreground dark:text-gray-400 mb-2">
                    Epoch
                  </div>
                  <div className="text-2xl font-bold text-card-foreground dark:text-gray-200">
                    {status.epoch?.toLocaleString() || 0}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground dark:text-gray-400">
                Unable to load status
              </div>
            )}
          </section>

          {/* Quick Actions */}
          <section>
            <h2 className="text-lg font-semibold text-foreground dark:text-gray-200 mb-4">
              Quick Actions
            </h2>
            <div className="grid grid-cols-3 gap-4">
              {quickActions.map((action) => {
                const Icon = action.icon;
                return (
                  <button
                    key={action.path}
                    onClick={() => navigate(action.path)}
                    className={`
                      p-6 rounded-lg border border-border dark:border-gray-800
                      ${action.bg} hover:border-primary
                      transition-all text-left group
                    `}
                  >
                    <Icon className={`w-8 h-8 ${action.color} mb-3`} />
                    <div className="font-semibold text-card-foreground group-hover:text-primary">
                      {action.label}
                    </div>
                    <div className="text-sm text-muted-foreground dark:text-gray-400">
                      {action.description}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Workstation Guide - the platform explaining itself as a graph */}
          <section>
            <h2 className="text-lg font-semibold text-foreground dark:text-gray-200 mb-2">
              Workstation Guide
            </h2>
            <p className="text-sm text-muted-foreground dark:text-gray-400 mb-4">
              Click any node to navigate. This is how your knowledge graph works.
            </p>
            <div className="p-4 rounded-lg bg-card border border-border dark:border-gray-800">
              <NavigationGraph />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default HomeWorkspace;
