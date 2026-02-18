/**
 * System Tab Component
 *
 * System status, AI configuration, and API documentation.
 */

import React, { useState, useEffect } from 'react';
import {
  Server,
  Database,
  Activity,
  FileText,
  Key,
  Cpu,
  BrainCircuit,
  RefreshCw,
  Loader2,
  ExternalLink,
  Lock,
  Shield,
  CheckCircle,
  AlertCircle,
  BarChart3,
  Play,
  Save,
  Trash2,
  TestTube,
  Eye,
  EyeOff,
  ChevronDown,
} from 'lucide-react';
import { apiClient, API_BASE_URL } from '../../api/client';
import { Section, StatusBadge } from './components';
import type { SystemStatus, EmbeddingConfig, ExtractionConfig, ApiKeyInfo, SchedulerStatus } from './types';

interface SystemTabProps {
  onError: (error: string) => void;
}

export const SystemTab: React.FC<SystemTabProps> = ({ onError }) => {
  // Data states
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [dbStats, setDbStats] = useState<any>(null);
  const [dbCounters, setDbCounters] = useState<any>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [embeddingConfigs, setEmbeddingConfigs] = useState<EmbeddingConfig[]>([]);
  const [extractionConfig, setExtractionConfig] = useState<ExtractionConfig | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshingCounters, setRefreshingCounters] = useState(false);

  // Interactive UI states
  const [activatingEmbedding, setActivatingEmbedding] = useState<number | null>(null);
  const [confirmActivate, setConfirmActivate] = useState<number | null>(null);
  const [savingExtraction, setSavingExtraction] = useState(false);
  const [extractionForm, setExtractionForm] = useState<{ provider: string; model: string } | null>(null);
  const [apiKeyForm, setApiKeyForm] = useState<{ provider: string; key: string } | null>(null);
  const [savingApiKey, setSavingApiKey] = useState(false);
  const [showApiKey, setShowApiKey] = useState<string | null>(null);
  const [deletingApiKey, setDeletingApiKey] = useState<string | null>(null);

  // Load data
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [status, stats, counters, scheduler, embeddings, extraction, keys] = await Promise.all([
        apiClient.getSystemStatus().catch(() => null),
        apiClient.getDatabaseStats().catch(() => null),
        apiClient.getDatabaseCounters().catch(() => null),
        apiClient.getSchedulerStatus().catch(() => null),
        apiClient.listEmbeddingConfigs().catch(() => []),
        apiClient.getExtractionConfig().catch(() => null),
        apiClient.listApiKeys().catch(() => []),
      ]);
      setSystemStatus(status);
      setDbStats(stats);
      setDbCounters(counters);
      setSchedulerStatus(scheduler);
      setEmbeddingConfigs(embeddings);
      setExtractionConfig(extraction);
      setApiKeys(keys);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to load system data');
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshCounters = async () => {
    setRefreshingCounters(true);
    try {
      await apiClient.refreshDatabaseCounters();
      // Reload counters after refresh
      const counters = await apiClient.getDatabaseCounters();
      setDbCounters(counters);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to refresh counters');
    } finally {
      setRefreshingCounters(false);
    }
  };

  // Embedding activation handler
  const handleActivateEmbedding = async (configId: number) => {
    setActivatingEmbedding(configId);
    setConfirmActivate(null);
    try {
      await apiClient.activateEmbeddingConfig(configId, true);
      // Reload embedding configs
      const embeddings = await apiClient.listEmbeddingConfigs();
      setEmbeddingConfigs(embeddings);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to activate embedding profile');
    } finally {
      setActivatingEmbedding(null);
    }
  };

  // Extraction config handler
  const handleSaveExtraction = async () => {
    if (!extractionForm) return;
    setSavingExtraction(true);
    try {
      await apiClient.updateExtractionConfig({
        provider: extractionForm.provider,
        model: extractionForm.model,
        updated_by: 'web-admin',
      });
      // Reload extraction config
      const extraction = await apiClient.getExtractionConfig();
      setExtractionConfig(extraction);
      setExtractionForm(null);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to save extraction config');
    } finally {
      setSavingExtraction(false);
    }
  };

  // API key handlers
  const handleSaveApiKey = async () => {
    if (!apiKeyForm) return;
    setSavingApiKey(true);
    try {
      await apiClient.setApiKey(apiKeyForm.provider, apiKeyForm.key);
      // Reload API keys
      const keys = await apiClient.listApiKeys();
      setApiKeys(keys);
      setApiKeyForm(null);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to save API key');
    } finally {
      setSavingApiKey(false);
    }
  };

  const handleDeleteApiKey = async (provider: string) => {
    setDeletingApiKey(provider);
    try {
      await apiClient.deleteApiKey(provider);
      // Reload API keys
      const keys = await apiClient.listApiKeys();
      setApiKeys(keys);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to delete API key');
    } finally {
      setDeletingApiKey(null);
    }
  };

  // Provider/model options
  const extractionProviders = [
    { provider: 'openai', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'] },
    { provider: 'anthropic', models: ['claude-sonnet-4-20250514', 'claude-3-5-sonnet-20241022', 'claude-3-haiku-20240307'] },
    { provider: 'ollama', models: ['mistral', 'llama3.2', 'qwen2.5'] },
    { provider: 'openrouter', models: ['(placeholder - not yet implemented)'] },
    { provider: 'llama.cpp', models: ['(placeholder - not yet implemented)'] },
  ];

  const apiKeyProviders = ['openai', 'anthropic', 'openrouter'];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <>
      <Section
        title="System Config"
        icon={<Server className="w-5 h-5" />}
        action={
          <button
            onClick={loadData}
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        }
      >
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <StatusBadge
            connected={systemStatus?.database_connection?.connected ?? false}
            label={systemStatus?.database_connection?.connected ? 'Database Connected' : 'Database Offline'}
          />
          <StatusBadge
            connected={systemStatus?.docker?.running ?? false}
            label={systemStatus?.docker?.running ? 'Container Running' : 'Container Offline'}
          />
        </div>

        {systemStatus && (
          <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
            {systemStatus.python_env?.python_version && (
              <div>
                <span className="text-muted-foreground">Python:</span>
                <span className="ml-2 font-mono text-foreground">
                  {systemStatus.python_env.python_version}
                </span>
              </div>
            )}
            {systemStatus.docker?.status && (
              <div>
                <span className="text-muted-foreground">Docker:</span>
                <span className="ml-2 font-mono text-foreground">
                  {systemStatus.docker.status}
                </span>
              </div>
            )}
            {systemStatus.configuration && (
              <>
                <div>
                  <span className="text-muted-foreground">OpenAI Key:</span>
                  <span className={`ml-2 font-mono ${systemStatus.configuration.openai_key_configured ? 'text-status-active' : 'text-destructive'}`}>
                    {systemStatus.configuration.openai_key_configured ? 'Configured' : 'Not Set'}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">Anthropic Key:</span>
                  <span className={`ml-2 font-mono ${systemStatus.configuration.anthropic_key_configured ? 'text-status-active' : 'text-destructive'}`}>
                    {systemStatus.configuration.anthropic_key_configured ? 'Configured' : 'Not Set'}
                  </span>
                </div>
              </>
            )}
          </div>
        )}
      </Section>

      <Section
        title="Database Statistics"
        icon={<Database className="w-5 h-5" />}
      >
        {dbStats ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-muted/50 rounded-lg">
              <div className="text-2xl font-bold text-foreground">
                {(dbStats.nodes?.concepts ?? 0).toLocaleString()}
              </div>
              <div className="text-sm text-muted-foreground">Concepts</div>
            </div>
            <div className="p-4 bg-muted/50 rounded-lg">
              <div className="text-2xl font-bold text-foreground">
                {(dbStats.nodes?.sources ?? 0).toLocaleString()}
              </div>
              <div className="text-sm text-muted-foreground">Sources</div>
            </div>
            <div className="p-4 bg-muted/50 rounded-lg">
              <div className="text-2xl font-bold text-foreground">
                {(dbStats.nodes?.instances ?? 0).toLocaleString()}
              </div>
              <div className="text-sm text-muted-foreground">Instances</div>
            </div>
            <div className="p-4 bg-muted/50 rounded-lg">
              <div className="text-2xl font-bold text-foreground">
                {(dbStats.relationships?.total ?? 0).toLocaleString()}
              </div>
              <div className="text-sm text-muted-foreground">Relationships</div>
            </div>
          </div>
        ) : (
          <p className="text-muted-foreground text-center py-8">
            Unable to load database statistics.
          </p>
        )}
      </Section>

      <Section
        title="Graph Metrics"
        icon={<BarChart3 className="w-5 h-5" />}
        action={
          <button
            onClick={handleRefreshCounters}
            disabled={refreshingCounters}
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors disabled:opacity-50"
            title="Refresh counters from graph state"
          >
            {refreshingCounters ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
          </button>
        }
      >
        <p className="text-sm text-muted-foreground mb-4">
          Counters for tracking graph changes and cache invalidation (ADR-079).
        </p>
        {dbCounters?.current_snapshot ? (
          <>
            {/* Current Snapshot */}
            <div className="mb-4">
              <div className="text-sm font-medium text-foreground mb-2">Current Snapshot</div>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                <div className="p-3 bg-muted/50 rounded-lg text-center">
                  <div className="text-lg font-bold text-foreground">
                    {dbCounters.current_snapshot.concepts.toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground">Concepts</div>
                </div>
                <div className="p-3 bg-muted/50 rounded-lg text-center">
                  <div className="text-lg font-bold text-foreground">
                    {dbCounters.current_snapshot.edges.toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground">Edges</div>
                </div>
                <div className="p-3 bg-muted/50 rounded-lg text-center">
                  <div className="text-lg font-bold text-foreground">
                    {dbCounters.current_snapshot.sources.toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground">Sources</div>
                </div>
                <div className="p-3 bg-muted/50 rounded-lg text-center">
                  <div className="text-lg font-bold text-foreground">
                    {dbCounters.current_snapshot.vocab_types.toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground">Vocab Types</div>
                </div>
                <div className="p-3 bg-muted/50 rounded-lg text-center">
                  <div className="text-lg font-bold text-foreground">
                    {dbCounters.current_snapshot.total_objects.toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground">Total</div>
                </div>
              </div>
            </div>

            {/* Snapshot Counters */}
            {dbCounters.counters?.snapshot?.length > 0 && (
              <div className="mb-4">
                <div className="text-sm font-medium text-foreground mb-2">Snapshot Counters</div>
                <div className="space-y-1">
                  {dbCounters.counters.snapshot.map((c: any) => (
                    <div key={c.name} className="flex items-center justify-between p-2 bg-muted/30 rounded text-sm">
                      <span className="text-muted-foreground font-mono text-xs">{c.name}</span>
                      <span className="flex items-center gap-2">
                        <span className="text-foreground font-medium">{c.value.toLocaleString()}</span>
                        {c.delta !== 0 && (
                          <span className={`text-xs ${c.delta > 0 ? 'text-status-active' : 'text-status-warning'}`}>
                            ({c.delta > 0 ? '+' : ''}{c.delta})
                          </span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Activity Counters */}
            {dbCounters.counters?.activity?.length > 0 && (
              <div className="mb-4">
                <div className="text-sm font-medium text-foreground mb-2">Activity Counters</div>
                <div className="space-y-1">
                  {dbCounters.counters.activity.map((c: any) => (
                    <div key={c.name} className="flex items-center justify-between p-2 bg-muted/30 rounded text-sm">
                      <span className="text-muted-foreground font-mono text-xs">{c.name}</span>
                      <span className="flex items-center gap-2">
                        <span className="text-foreground font-medium">{c.value.toLocaleString()}</span>
                        {c.delta !== 0 && (
                          <span className={`text-xs ${c.delta > 0 ? 'text-status-active' : 'text-status-warning'}`}>
                            ({c.delta > 0 ? '+' : ''}{c.delta})
                          </span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="text-muted-foreground text-center py-4">
            Unable to load graph metrics.
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Use <code className="bg-muted px-1 rounded">kg database counters</code> for detailed CLI view
        </p>
      </Section>

      <Section
        title="Job Queue"
        icon={<Activity className="w-5 h-5" />}
      >
        {schedulerStatus?.jobs_by_status ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-status-warning/10 rounded-lg">
              <div className="text-2xl font-bold text-status-warning">
                {(schedulerStatus.jobs_by_status.pending ?? 0) + (schedulerStatus.jobs_by_status.awaiting_approval ?? 0)}
              </div>
              <div className="text-sm text-status-warning">Pending</div>
            </div>
            <div className="p-4 bg-status-info/20 rounded-lg">
              <div className="text-2xl font-bold text-status-info">
                {(schedulerStatus.jobs_by_status.processing ?? 0) + (schedulerStatus.jobs_by_status.running ?? 0)}
              </div>
              <div className="text-sm text-status-info">Running</div>
            </div>
            <div className="p-4 bg-status-active/10 rounded-lg">
              <div className="text-2xl font-bold text-status-active">
                {schedulerStatus.jobs_by_status.completed ?? 0}
              </div>
              <div className="text-sm text-status-active">Completed</div>
            </div>
            <div className="p-4 bg-destructive/10 rounded-lg">
              <div className="text-2xl font-bold text-destructive">
                {schedulerStatus.jobs_by_status.failed ?? 0}
              </div>
              <div className="text-sm text-destructive">Failed</div>
            </div>
          </div>
        ) : (
          <p className="text-muted-foreground text-center py-8">
            Unable to load job queue status.
          </p>
        )}
      </Section>

      <Section
        title="API Documentation"
        icon={<FileText className="w-5 h-5" />}
      >
        <p className="text-sm text-muted-foreground mb-4">
          Interactive API documentation for developers and integrations.
        </p>
        <div className="flex flex-wrap gap-3">
          <a
            href={`${API_BASE_URL}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg transition-colors text-foreground"
          >
            <FileText className="w-4 h-4" />
            Swagger UI
            <ExternalLink className="w-3 h-3 text-muted-foreground" />
          </a>
          <a
            href={`${API_BASE_URL}/redoc`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg transition-colors text-foreground"
          >
            <FileText className="w-4 h-4" />
            ReDoc
            <ExternalLink className="w-3 h-3 text-muted-foreground" />
          </a>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          API: {API_BASE_URL}
        </p>
      </Section>

      {/* Embedding Profiles Section */}
      <Section
        title="Embedding Profiles"
        icon={<Cpu className="w-5 h-5" />}
      >
        <p className="text-sm text-muted-foreground mb-4">
          Vector embedding model configurations for semantic search. Activating a different profile will re-embed all content.
        </p>
        {embeddingConfigs.length > 0 ? (
          <div className="space-y-3">
            {embeddingConfigs.map((config) => (
              <div
                key={config.id}
                className={`p-4 rounded-lg border ${
                  config.active
                    ? 'bg-status-active/10 border-status-active/30'
                    : 'bg-muted/50 border-border'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {config.active ? (
                      <span className="px-2 py-0.5 bg-status-active/20 text-status-active text-xs font-medium rounded">
                        ACTIVE
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 bg-muted text-muted-foreground text-xs font-medium rounded">
                        Inactive
                      </span>
                    )}
                    <span className="font-medium text-foreground">
                      Config {config.id}
                    </span>
                    {config.delete_protected && (
                      <span title="Delete protected">
                        <Lock className="w-3 h-3 text-status-warning" />
                      </span>
                    )}
                    {config.change_protected && (
                      <span title="Change protected">
                        <Shield className="w-3 h-3 text-status-info" />
                      </span>
                    )}
                  </div>
                  {/* Activate button for inactive profiles */}
                  {!config.active && (
                    <div className="flex items-center gap-2">
                      {confirmActivate === config.id ? (
                        <>
                          <span className="text-xs text-status-warning">Re-embed all content?</span>
                          <button
                            onClick={() => handleActivateEmbedding(config.id)}
                            disabled={activatingEmbedding !== null}
                            className="px-2 py-1 text-xs bg-status-warning text-white rounded hover:bg-status-warning/80 disabled:opacity-50"
                          >
                            {activatingEmbedding === config.id ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              'Confirm'
                            )}
                          </button>
                          <button
                            onClick={() => setConfirmActivate(null)}
                            className="px-2 py-1 text-xs bg-muted text-muted-foreground rounded hover:bg-muted/80"
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => setConfirmActivate(config.id)}
                          disabled={activatingEmbedding !== null}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/80 disabled:opacity-50"
                        >
                          <Play className="w-3 h-3" />
                          Activate
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Provider:</span>
                    <span className="ml-1 text-foreground">{config.provider}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Model:</span>
                    <span className="ml-1 text-foreground font-mono text-xs">{config.model_name}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Dims:</span>
                    <span className="ml-1 text-foreground">{config.embedding_dimensions}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Device:</span>
                    <span className="ml-1 text-foreground">{config.device ?? 'cloud'}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground text-center py-4">
            No embedding configurations found.
          </p>
        )}
      </Section>

      {/* Extraction Config Section */}
      <Section
        title="AI Extraction"
        icon={<BrainCircuit className="w-5 h-5" />}
      >
        <p className="text-sm text-muted-foreground mb-4">
          LLM provider for concept extraction from documents.
        </p>

        {/* Edit Form */}
        {extractionForm ? (
          <div className="p-4 bg-muted/50 rounded-lg border border-border mb-4">
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">Provider</label>
                  <select
                    value={extractionForm.provider}
                    onChange={(e) => {
                      const provider = e.target.value;
                      const models = extractionProviders.find(p => p.provider === provider)?.models || [];
                      setExtractionForm({ provider, model: models[0] || '' });
                    }}
                    className="w-full px-3 py-2 bg-background border border-border rounded text-foreground text-sm"
                  >
                    {extractionProviders.map(p => (
                      <option key={p.provider} value={p.provider}>
                        {p.provider}
                        {(p.provider === 'openrouter' || p.provider === 'llama.cpp') && ' (placeholder)'}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">Model</label>
                  <select
                    value={extractionForm.model}
                    onChange={(e) => setExtractionForm({ ...extractionForm, model: e.target.value })}
                    className="w-full px-3 py-2 bg-background border border-border rounded text-foreground text-sm"
                    disabled={extractionForm.provider === 'openrouter' || extractionForm.provider === 'llama.cpp'}
                  >
                    {extractionProviders.find(p => p.provider === extractionForm.provider)?.models.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
              </div>
              {(extractionForm.provider === 'openrouter' || extractionForm.provider === 'llama.cpp') && (
                <p className="text-xs text-status-warning">
                  {extractionForm.provider} support is not yet implemented. This is a placeholder for future development.
                </p>
              )}
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setExtractionForm(null)}
                  className="px-3 py-1.5 text-sm bg-muted text-muted-foreground rounded hover:bg-muted/80"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveExtraction}
                  disabled={savingExtraction || extractionForm.provider === 'openrouter' || extractionForm.provider === 'llama.cpp'}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/80 disabled:opacity-50"
                >
                  {savingExtraction ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  Save
                </button>
              </div>
            </div>
          </div>
        ) : extractionConfig ? (
          <div className="p-4 bg-muted/50 rounded-lg border border-border">
            <div className="flex items-start justify-between">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm flex-1">
                <div>
                  <span className="text-muted-foreground">Provider:</span>
                  <span className="ml-2 font-medium text-foreground capitalize">{extractionConfig.provider}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Model:</span>
                  <span className="ml-2 font-mono text-foreground">{extractionConfig.model}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Max Tokens:</span>
                  <span className="ml-2 text-foreground">{extractionConfig.max_tokens?.toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Vision:</span>
                  <span className={`ml-2 ${extractionConfig.supports_vision ? 'text-status-active' : 'text-muted-foreground'}`}>
                    {extractionConfig.supports_vision ? 'Yes' : 'No'}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">JSON Mode:</span>
                  <span className={`ml-2 ${extractionConfig.supports_json_mode ? 'text-status-active' : 'text-muted-foreground'}`}>
                    {extractionConfig.supports_json_mode ? 'Yes' : 'No'}
                  </span>
                </div>
                {extractionConfig.rate_limit_config && (
                  <div>
                    <span className="text-muted-foreground">Concurrency:</span>
                    <span className="ml-2 text-foreground">
                      {extractionConfig.rate_limit_config.max_concurrent_requests} / {extractionConfig.rate_limit_config.max_retries} retries
                    </span>
                  </div>
                )}
              </div>
              <button
                onClick={() => setExtractionForm({
                  provider: extractionConfig.provider,
                  model: extractionConfig.model,
                })}
                className="ml-4 p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                title="Edit extraction config"
              >
                <ChevronDown className="w-4 h-4" />
              </button>
            </div>
          </div>
        ) : (
          <div className="p-4 bg-muted/50 rounded-lg border border-border">
            <p className="text-muted-foreground text-center py-2">
              No extraction configuration found.
            </p>
            <div className="flex justify-center mt-2">
              <button
                onClick={() => setExtractionForm({ provider: 'openai', model: 'gpt-4o' })}
                className="px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/80"
              >
                Configure
              </button>
            </div>
          </div>
        )}
      </Section>

      {/* API Keys Section */}
      <Section
        title="API Keys"
        icon={<Key className="w-5 h-5" />}
      >
        <p className="text-sm text-muted-foreground mb-4">
          API keys for AI providers (encrypted at rest). Keys are validated on save.
        </p>

        {/* Add Key Form */}
        {apiKeyForm ? (
          <div className="p-4 bg-muted/50 rounded-lg border border-border mb-4">
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">Provider</label>
                  <select
                    value={apiKeyForm.provider}
                    onChange={(e) => setApiKeyForm({ ...apiKeyForm, provider: e.target.value })}
                    className="w-full px-3 py-2 bg-background border border-border rounded text-foreground text-sm"
                  >
                    {apiKeyProviders.map(p => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm text-muted-foreground mb-1">API Key</label>
                  <div className="relative">
                    <input
                      type={showApiKey === 'form' ? 'text' : 'password'}
                      value={apiKeyForm.key}
                      onChange={(e) => setApiKeyForm({ ...apiKeyForm, key: e.target.value })}
                      placeholder="sk-..."
                      className="w-full px-3 py-2 pr-10 bg-background border border-border rounded text-foreground text-sm font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(showApiKey === 'form' ? null : 'form')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground"
                    >
                      {showApiKey === 'form' ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setApiKeyForm(null)}
                  className="px-3 py-1.5 text-sm bg-muted text-muted-foreground rounded hover:bg-muted/80"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveApiKey}
                  disabled={savingApiKey || !apiKeyForm.key}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/80 disabled:opacity-50"
                >
                  {savingApiKey ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <TestTube className="w-4 h-4" />
                      Test & Save
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="mb-4">
            <button
              onClick={() => setApiKeyForm({ provider: 'openai', key: '' })}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/80"
            >
              <Key className="w-4 h-4" />
              Add API Key
            </button>
          </div>
        )}

        {/* Existing Keys */}
        {apiKeys.length > 0 ? (
          <div className="space-y-2">
            {apiKeys.map((key) => (
              <div
                key={key.provider}
                className="flex items-center justify-between p-3 bg-muted/50 rounded-lg border border-border"
              >
                <div className="flex items-center gap-3">
                  <span className="font-medium text-foreground capitalize w-24">
                    {key.provider}
                  </span>
                  {key.configured ? (
                    <>
                      {key.validation_status === 'valid' ? (
                        <span className="flex items-center gap-1 text-status-active text-sm">
                          <CheckCircle className="w-4 h-4" />
                          Valid
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-status-warning text-sm">
                          <AlertCircle className="w-4 h-4" />
                          {key.validation_status ?? 'Unknown'}
                        </span>
                      )}
                      {key.masked_key && (
                        <span className="text-xs text-muted-foreground font-mono">
                          {key.masked_key}
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="text-muted-foreground text-sm">
                      Not configured
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {key.last_validated_at && (
                    <span className="text-xs text-muted-foreground">
                      {new Date(key.last_validated_at).toLocaleDateString()}
                    </span>
                  )}
                  {key.configured && (
                    <button
                      onClick={() => handleDeleteApiKey(key.provider)}
                      disabled={deletingApiKey === key.provider}
                      className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded transition-colors disabled:opacity-50"
                      title="Delete API key"
                    >
                      {deletingApiKey === key.provider ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground text-center py-4">
            No API keys configured.
          </p>
        )}
      </Section>
    </>
  );
};

export default SystemTab;
