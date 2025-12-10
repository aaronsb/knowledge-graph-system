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
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [embeddingConfigs, setEmbeddingConfigs] = useState<EmbeddingConfig[]>([]);
  const [extractionConfig, setExtractionConfig] = useState<ExtractionConfig | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);

  // Load data
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [status, stats, scheduler, embeddings, extraction, keys] = await Promise.all([
        apiClient.getSystemStatus().catch(() => null),
        apiClient.getDatabaseStats().catch(() => null),
        apiClient.getSchedulerStatus().catch(() => null),
        apiClient.listEmbeddingConfigs().catch(() => []),
        apiClient.getExtractionConfig().catch(() => null),
        apiClient.listApiKeys().catch(() => []),
      ]);
      setSystemStatus(status);
      setDbStats(stats);
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
                {schedulerStatus.jobs_by_status.processing ?? 0}
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
          Vector embedding model configurations for semantic search.
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
        <p className="mt-3 text-xs text-muted-foreground">
          Use <code className="bg-muted px-1 rounded">kg admin embedding</code> to manage profiles
        </p>
      </Section>

      {/* Extraction Config Section */}
      <Section
        title="AI Extraction"
        icon={<BrainCircuit className="w-5 h-5" />}
      >
        <p className="text-sm text-muted-foreground mb-4">
          LLM provider for concept extraction from documents.
        </p>
        {extractionConfig ? (
          <div className="p-4 bg-muted/50 rounded-lg border border-border">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
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
          </div>
        ) : (
          <p className="text-muted-foreground text-center py-4">
            No extraction configuration found.
          </p>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          Use <code className="bg-muted px-1 rounded">kg admin extraction</code> to configure
        </p>
      </Section>

      {/* API Keys Section */}
      <Section
        title="API Keys"
        icon={<Key className="w-5 h-5" />}
      >
        <p className="text-sm text-muted-foreground mb-4">
          API keys for AI providers (encrypted at rest).
        </p>
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
                {key.last_validated_at && (
                  <span className="text-xs text-muted-foreground">
                    Validated: {new Date(key.last_validated_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground text-center py-4">
            No API keys configured.
          </p>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          Use <code className="bg-muted px-1 rounded">kg admin keys</code> to manage keys
        </p>
      </Section>
    </>
  );
};

export default SystemTab;
