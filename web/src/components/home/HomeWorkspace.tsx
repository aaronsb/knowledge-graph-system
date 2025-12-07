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

interface SystemStatus {
  database?: {
    concepts: number;
    relationships: number;
    sources: number;
  };
  health?: boolean;
}

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
      const health = await apiClient.healthCheck();
      const stats = await apiClient.getDatabaseStats();
      setStatus({
        health: health.status === 'ok',
        database: {
          concepts: stats.concepts || 0,
          relationships: stats.relationships || 0,
          sources: stats.sources || 0,
        },
      });
    } catch (err) {
      console.error('Failed to load status:', err);
      setStatus({ health: false });
    } finally {
      setLoading(false);
    }
  };

  // Quick action cards
  const quickActions = [
    {
      icon: Network,
      label: 'Explore Graph',
      description: 'Interactive 2D visualization',
      path: '/explore/2d',
      color: 'text-blue-500 dark:text-blue-400',
      bg: 'bg-blue-50 dark:bg-blue-900/20',
    },
    {
      icon: Upload,
      label: 'Ingest Content',
      description: 'Upload documents',
      path: '/ingest',
      color: 'text-green-500 dark:text-green-400',
      bg: 'bg-green-50 dark:bg-green-900/20',
    },
    {
      icon: ListTodo,
      label: 'View Jobs',
      description: 'Monitor extractions',
      path: '/jobs',
      color: 'text-amber-500 dark:text-amber-400',
      bg: 'bg-amber-50 dark:bg-amber-900/20',
    },
  ];

  // Not authenticated - show welcome and login
  if (!isAuthenticated) {
    return (
      <div className="h-full flex flex-col bg-background dark:bg-gray-950">
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="max-w-lg text-center">
            {/* Logo/Icon */}
            <div className="mb-8">
              <div className="w-24 h-24 mx-auto rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg">
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
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary dark:bg-blue-600 text-primary-foreground dark:text-white rounded-lg font-medium hover:bg-primary/90 dark:hover:bg-blue-700 transition-colors shadow-md"
            >
              <LogIn className="w-5 h-5" />
              Sign In to Continue
            </button>

            {/* Features */}
            <div className="mt-12 grid grid-cols-3 gap-4 text-sm">
              <div className="p-4 rounded-lg bg-card dark:bg-gray-900 border border-border dark:border-gray-800">
                <Database className="w-6 h-6 mx-auto mb-2 text-blue-500 dark:text-blue-400" />
                <div className="font-medium text-card-foreground dark:text-gray-200">Graph Database</div>
                <div className="text-xs text-muted-foreground dark:text-gray-500">Apache AGE</div>
              </div>
              <div className="p-4 rounded-lg bg-card dark:bg-gray-900 border border-border dark:border-gray-800">
                <Activity className="w-6 h-6 mx-auto mb-2 text-green-500 dark:text-green-400" />
                <div className="font-medium text-card-foreground dark:text-gray-200">LLM Extraction</div>
                <div className="text-xs text-muted-foreground dark:text-gray-500">GPT-4 / Claude</div>
              </div>
              <div className="p-4 rounded-lg bg-card dark:bg-gray-900 border border-border dark:border-gray-800">
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
    <div className="h-full flex flex-col bg-background dark:bg-gray-950">
      {/* Header */}
      <div className="flex-none p-6 border-b border-border dark:border-gray-800">
        <div className="flex items-center gap-3">
          <Home className="w-6 h-6 text-primary dark:text-blue-400" />
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
        <div className="max-w-4xl mx-auto space-y-8">
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
              <div className="grid grid-cols-4 gap-4">
                <div className="p-4 rounded-lg bg-card dark:bg-gray-900 border border-border dark:border-gray-800">
                  <div className="flex items-center gap-2 mb-2">
                    {status.health ? (
                      <CheckCircle2 className="w-5 h-5 text-green-500" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-500" />
                    )}
                    <span className="text-sm font-medium text-muted-foreground dark:text-gray-400">API</span>
                  </div>
                  <div className="text-2xl font-bold text-card-foreground dark:text-gray-200">
                    {status.health ? 'Online' : 'Offline'}
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-card dark:bg-gray-900 border border-border dark:border-gray-800">
                  <div className="text-sm font-medium text-muted-foreground dark:text-gray-400 mb-2">
                    Concepts
                  </div>
                  <div className="text-2xl font-bold text-card-foreground dark:text-gray-200">
                    {status.database?.concepts?.toLocaleString() || 0}
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-card dark:bg-gray-900 border border-border dark:border-gray-800">
                  <div className="text-sm font-medium text-muted-foreground dark:text-gray-400 mb-2">
                    Relationships
                  </div>
                  <div className="text-2xl font-bold text-card-foreground dark:text-gray-200">
                    {status.database?.relationships?.toLocaleString() || 0}
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-card dark:bg-gray-900 border border-border dark:border-gray-800">
                  <div className="text-sm font-medium text-muted-foreground dark:text-gray-400 mb-2">
                    Sources
                  </div>
                  <div className="text-2xl font-bold text-card-foreground dark:text-gray-200">
                    {status.database?.sources?.toLocaleString() || 0}
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
                      ${action.bg} hover:border-primary dark:hover:border-blue-500
                      transition-all text-left group
                    `}
                  >
                    <Icon className={`w-8 h-8 ${action.color} mb-3`} />
                    <div className="font-semibold text-card-foreground dark:text-gray-200 group-hover:text-primary dark:group-hover:text-blue-400">
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
        </div>
      </div>
    </div>
  );
};

export default HomeWorkspace;
