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
  Layers,
  Play,
  Trash2,
  TestTube,
  Eye,
  EyeOff,
} from 'lucide-react';
import { apiClient, API_BASE_URL } from '../../api/client';
import { Section, StatusBadge } from './components';
import type { SystemStatus, EmbeddingConfig, ExtractionConfig, ApiKeyInfo, SchedulerStatus, WorkerStatus } from './types';

interface SystemTabProps {
  onError: (error: string) => void;
}

// Sensible default endpoint for local providers (editable in the card —
// this is a placeholder, not hardcoded behaviour). Docker-network service
// name for llamacpp (ADR-800 networking finding); ollama's well-known port.
const LOCAL_DEFAULT_BASE_URL: Record<string, string> = {
  llamacpp: 'http://kg-llamacpp:8080/v1',
  ollama: 'http://localhost:11434',
};

// Sane KG default sampling temperature for extraction reasoning.
const DEFAULT_TEMPERATURE = '0.1';

export const SystemTab: React.FC<SystemTabProps> = ({ onError }) => {
  // Data states
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [dbStats, setDbStats] = useState<any>(null);
  const [dbCounters, setDbCounters] = useState<any>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [workerStatus, setWorkerStatus] = useState<WorkerStatus | null>(null);
  const [docsIngested, setDocsIngested] = useState<number>(0);
  const [graphEpoch, setGraphEpoch] = useState<number>(0);
  const [embeddingConfigs, setEmbeddingConfigs] = useState<EmbeddingConfig[]>([]);
  const [extractionConfig, setExtractionConfig] = useState<ExtractionConfig | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [catalog, setCatalog] = useState<Array<{
    id: number;
    provider: string;
    model_id: string;
    display_name: string | null;
    category: string;
    enabled: boolean;
    is_default: boolean;
    sort_order: number;
    upstream_provider: string | null;
  }>>([]);
  const [providers, setProviders] = useState<Array<{
    provider: string;
    requires_key: boolean;
    is_local: boolean;
  }>>([]);
  const [refreshingCatalog, setRefreshingCatalog] = useState<string | null>(null);
  // Per-provider editable draft (#8): base_url / model / reasoning params,
  // hydrated from each provider's saved DB row so the card round-trips what
  // is actually persisted. Same shape for every provider — uniform card.
  const [providerDrafts, setProviderDrafts] = useState<Record<string, {
    base_url: string;
    model: string;
    temperature: string;
    max_tokens: string;
  }>>({});
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshingCounters, setRefreshingCounters] = useState(false);

  // Interactive UI states
  const [activatingEmbedding, setActivatingEmbedding] = useState<number | null>(null);
  const [confirmActivate, setConfirmActivate] = useState<number | null>(null);
  const [settingExtraction, setSettingExtraction] = useState<string | null>(null);
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
      const [status, stats, counters, scheduler, workers, embeddings, extraction, keys, apiInfo, dbEpoch, modelCatalog, supportedProviders] = await Promise.all([
        apiClient.getSystemStatus().catch(() => null),
        apiClient.getDatabaseStats().catch(() => null),
        apiClient.getDatabaseCounters().catch(() => null),
        apiClient.getSchedulerStatus().catch(() => null),
        apiClient.getWorkerStatus().catch(() => null),
        apiClient.listEmbeddingConfigs().catch(() => []),
        apiClient.getExtractionConfig().catch(() => null),
        apiClient.listApiKeys().catch(() => []),
        apiClient.getApiInfo().catch(() => ({ epoch: 0, status: 'error' })),
        apiClient.getDatabaseEpoch().catch(() => 0),
        apiClient.getModelCatalog().then(r => r.models).catch(() => []),
        apiClient.getProviders().then(r => r.providers).catch(() => []),
      ]);
      setSystemStatus(status);
      setDbStats(stats);
      setDbCounters(counters);
      setSchedulerStatus(scheduler);
      setWorkerStatus(workers);
      setDocsIngested(apiInfo.epoch || 0);
      setGraphEpoch(dbEpoch);
      setEmbeddingConfigs(embeddings);
      setExtractionConfig(extraction);
      setApiKeys(keys);
      setCatalog(modelCatalog);
      setProviders(supportedProviders);

      // Hydrate each provider card's draft from its saved DB row so the
      // card shows what is actually persisted (two-way source of truth, #8).
      // Falls back to the local-provider default endpoint / sane temperature
      // when there is no saved row yet.
      const names = Array.from(new Set([
        ...supportedProviders.map(p => p.provider),
        ...(extraction?.provider ? [extraction.provider] : []),
      ]));
      const savedConfigs = await Promise.all(
        names.map(n =>
          apiClient.getProviderConfig(n)
            .then(r => [n, r.config] as const)
            .catch(() => [n, null] as const)
        )
      );
      const drafts: Record<string, { base_url: string; model: string; temperature: string; max_tokens: string }> = {};
      for (const [n, cfg] of savedConfigs) {
        drafts[n] = {
          base_url: cfg?.base_url ?? LOCAL_DEFAULT_BASE_URL[n] ?? '',
          model: cfg?.model_name ?? '',
          temperature: cfg?.temperature != null ? String(cfg.temperature) : DEFAULT_TEMPERATURE,
          max_tokens: cfg?.max_tokens != null ? String(cfg.max_tokens) : '',
        };
      }
      setProviderDrafts(drafts);
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

  // Provider/model options are derived from the runtime model catalog and the
  // configured-keys list — never hardcoded (ADR-800). Operators populate the
  // catalog via "Refresh" (or the CLI), and the UI reflects whatever is there.
  const extractionProviders = React.useMemo(() => {
    const byProvider = new Map<string, string[]>();
    for (const m of catalog) {
      if (m.category !== 'extraction') continue;
      if (!byProvider.has(m.provider)) byProvider.set(m.provider, []);
      byProvider.get(m.provider)!.push(m.model_id);
    }
    return Array.from(byProvider.entries()).map(([provider, models]) => ({ provider, models }));
  }, [catalog]);


  // The canonical /admin/providers list drives which cards render — one per
  // supported provider, local providers included even with an empty catalog
  // so they can be enumerated/activated. Fall back to the active provider so
  // a card always shows for whatever is currently in use.
  const providerNames = React.useMemo(
    () => Array.from(new Set([
      ...providers.map(p => p.provider),
      ...(extractionConfig?.provider ? [extractionConfig.provider] : []),
    ])).sort(),
    [providers, extractionConfig]
  );

  const providerMeta = React.useMemo(
    () => new Map(providers.map(p => [p.provider, p])),
    [providers]
  );

  // --- Uniform per-provider card handlers (#8) ------------------------------
  // Every provider — cloud or local — uses the same shape: edit a draft,
  // then Save / Get models / Set active. Only what each field means differs
  // (key vs base_url), driven by /admin/providers metadata, not branches.

  const blankDraft = { base_url: '', model: '', temperature: DEFAULT_TEMPERATURE, max_tokens: '' };

  const updateDraft = (
    provider: string,
    patch: Partial<{ base_url: string; model: string; temperature: string; max_tokens: string }>
  ) => {
    setProviderDrafts(d => ({
      ...d,
      [provider]: { ...(d[provider] ?? blankDraft), ...patch },
    }));
  };

  // Only send fields the user actually set — the backend COALESCEs omitted
  // ones against the stored row, so a partial save never wipes the rest.
  // base_url is only meaningful for local providers.
  const buildPayload = (provider: string) => {
    const d = providerDrafts[provider] ?? blankDraft;
    const isLocal = !!providerMeta.get(provider)?.is_local;
    const payload: { base_url?: string; model_name?: string; temperature?: number; max_tokens?: number } = {};
    if (isLocal && d.base_url.trim()) payload.base_url = d.base_url.trim();
    if (d.model) payload.model_name = d.model;
    const t = Number(d.temperature);
    if (d.temperature.trim() !== '' && !Number.isNaN(t)) payload.temperature = t;
    const mt = Number(d.max_tokens);
    if (d.max_tokens.trim() !== '' && Number.isInteger(mt) && mt > 0) payload.max_tokens = mt;
    return payload;
  };

  // Re-hydrate one provider's draft from its persisted row (normalises what
  // the server actually stored after a save).
  const rehydrateDraft = async (provider: string) => {
    try {
      const { config } = await apiClient.getProviderConfig(provider);
      setProviderDrafts(d => ({
        ...d,
        [provider]: {
          base_url: config?.base_url ?? LOCAL_DEFAULT_BASE_URL[provider] ?? '',
          model: config?.model_name ?? '',
          temperature: config?.temperature != null ? String(config.temperature) : DEFAULT_TEMPERATURE,
          max_tokens: config?.max_tokens != null ? String(config.max_tokens) : '',
        },
      }));
    } catch {
      /* non-fatal — keep the in-memory draft */
    }
  };

  const handleSaveProviderConfig = async (provider: string) => {
    setSavingProvider(provider);
    try {
      await apiClient.saveProviderConfig(provider, buildPayload(provider));
      await rehydrateDraft(provider);
      // Keep the active provider's read-only detail line in sync — it reads
      // from extractionConfig, which the save may have just changed.
      const extraction = await apiClient.getExtractionConfig();
      setExtractionConfig(extraction);
    } catch (err) {
      onError(err instanceof Error ? err.message : `Failed to save ${provider} config`);
    } finally {
      setSavingProvider(null);
    }
  };

  // "Get models" IS the connectivity test: persist the draft first (so the
  // connector enumerates against the saved base_url for local providers),
  // then refresh the catalog from the provider's API.
  const handleGetModels = async (provider: string) => {
    setRefreshingCatalog(provider);
    try {
      await apiClient.saveProviderConfig(provider, buildPayload(provider));
      await apiClient.refreshModelCatalog(provider);
      const { models } = await apiClient.getModelCatalog();
      setCatalog(models);
      await rehydrateDraft(provider);
      // Active provider's detail line reads extractionConfig — refresh it in
      // case the refreshed catalog changed what its active model resolves to.
      const extraction = await apiClient.getExtractionConfig();
      setExtractionConfig(extraction);
    } catch (err) {
      onError(err instanceof Error ? err.message : `Failed to get models for ${provider}`);
    } finally {
      setRefreshingCatalog(null);
    }
  };

  // Persist the draft, then flip the active pointer to this provider+model.
  // COALESCE on the backend means activation preserves the base_url /
  // reasoning params just saved.
  const handleActivate = async (provider: string) => {
    const model = providerDrafts[provider]?.model;
    if (!model) return;
    setSettingExtraction(provider);
    try {
      await apiClient.saveProviderConfig(provider, buildPayload(provider));
      await apiClient.updateExtractionConfig({ provider, model, updated_by: 'web-admin' });
      const extraction = await apiClient.getExtractionConfig();
      setExtractionConfig(extraction);
    } catch (err) {
      onError(err instanceof Error ? err.message : `Failed to set ${provider} active`);
    } finally {
      setSettingExtraction(null);
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
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
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
            <div className="p-4 bg-muted/50 rounded-lg">
              <div className="text-2xl font-bold text-foreground">
                {docsIngested.toLocaleString()}
              </div>
              <div className="text-sm text-muted-foreground">Docs Ingested</div>
            </div>
            <div className="p-4 bg-muted/50 rounded-lg">
              <div className="text-2xl font-bold text-foreground">
                {graphEpoch.toLocaleString()}
              </div>
              <div className="text-sm text-muted-foreground">Graph Epoch</div>
            </div>
          </div>
        ) : (
          <p className="text-muted-foreground text-center py-8">
            Unable to load job queue status.
          </p>
        )}
      </Section>

      <Section
        title="Workers"
        icon={<Layers className="w-5 h-5" />}
      >
        {workerStatus ? (
          <>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="p-4 bg-status-info/20 rounded-lg">
                <div className="text-2xl font-bold text-status-info">
                  {workerStatus.slots_in_use}/{workerStatus.total_slots}
                </div>
                <div className="text-sm text-status-info">Slots In Use</div>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg">
                <div className="text-2xl font-bold text-foreground">
                  {workerStatus.running_count}
                </div>
                <div className="text-sm text-muted-foreground">Running Jobs</div>
              </div>
              <div className="p-4 bg-status-warning/10 rounded-lg">
                <div className="text-2xl font-bold text-status-warning">
                  {workerStatus.total_queued}
                </div>
                <div className="text-sm text-status-warning">Queued</div>
              </div>
            </div>

            <div className="space-y-2 mb-4">
              <div className="text-sm font-medium text-foreground">Lanes</div>
              {workerStatus.lanes.map((lane) => (
                <div
                  key={lane.name}
                  className={`flex items-center justify-between p-2 rounded-lg border ${
                    lane.enabled
                      ? 'bg-status-active/10 border-status-active/30'
                      : 'bg-muted/50 border-border opacity-60'
                  }`}
                >
                  <span className="text-sm font-medium text-foreground">{lane.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {lane.enabled ? `${lane.max_slots} slots` : 'disabled'}
                  </span>
                </div>
              ))}
            </div>

            {workerStatus.running_jobs.length > 0 && (
              <div className="space-y-1 mb-4">
                <div className="text-sm font-medium text-foreground">Active Jobs</div>
                {workerStatus.running_jobs.map((job) => {
                  const startedAt = job.started_at ? new Date(job.started_at.endsWith('Z') ? job.started_at : job.started_at + 'Z') : null;
                  const durationSeconds = startedAt
                    ? Math.floor((Date.now() - startedAt.getTime()) / 1000)
                    : null;
                  const durationLabel = durationSeconds !== null
                    ? durationSeconds < 60 ? `${durationSeconds}s`
                      : durationSeconds < 3600 ? `${Math.floor(durationSeconds / 60)}m ${durationSeconds % 60}s`
                        : `${Math.floor(durationSeconds / 3600)}h ${Math.floor((durationSeconds % 3600) / 60)}m`
                    : null;
                  return (
                    <div key={job.job_id} className="flex items-center justify-between p-2 bg-muted/30 rounded text-sm">
                      <span className="font-mono text-xs text-muted-foreground">
                        {job.job_id.substring(0, 8)}...
                      </span>
                      <span className="text-foreground">{job.job_type}</span>
                      {durationLabel && (
                        <span className="text-xs text-muted-foreground">{durationLabel}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          <p className="text-muted-foreground text-center py-8">
            Unable to load worker status.
          </p>
        )}
        <p className="text-xs text-muted-foreground mt-3">
          Use <code className="bg-muted px-1 rounded">kg admin workers</code> for CLI view
        </p>
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
                      {config.name || `Config ${config.id}`}
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
                    <span className="ml-1 text-foreground">{config.text_provider}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Model:</span>
                    <span className="ml-1 text-foreground font-mono text-xs">{config.text_model_name}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Dims:</span>
                    <span className="ml-1 text-foreground">{config.text_dimensions}</span>
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

      {/* AI Providers Section — unified per-provider cards (key + models +
          active extraction selection). A key belongs to a provider, so key
          management lives on the provider card rather than a separate section. */}
      <Section
        title="AI Providers"
        icon={<BrainCircuit className="w-5 h-5" />}
      >
        <p className="text-sm text-muted-foreground mb-4">
          One card per provider. Each card holds its API key (encrypted at rest,
          validated on save), its catalog models, and whether it is the active
          provider for concept extraction. Provider and model options are
          derived from the model catalog — nothing is hardcoded.
        </p>

        {providerNames.length === 0 ? (
          <p className="text-muted-foreground text-center py-4">
            No providers configured yet. Add an API key via the CLI, or once a
            cloud provider key is set its models appear here after a refresh.
          </p>
        ) : (
          <div className="space-y-3">
            {providerNames.map((name) => {
              const keyInfo = apiKeys.find(k => k.provider === name);
              const meta = providerMeta.get(name);
              // Authoritative from /admin/providers; fall back to key presence
              // only if metadata is somehow missing (e.g. active legacy provider).
              const requiresKey = meta?.requires_key ?? (keyInfo !== undefined);
              const models = extractionProviders.find(p => p.provider === name)?.models ?? [];
              const isActive = extractionConfig?.provider === name;
              const editingKey = apiKeyForm?.provider === name;
              const keyUsable = !requiresKey || (!!keyInfo?.configured && keyInfo?.validation_status === 'valid');
              const isLocal = !!meta?.is_local;
              const draft = providerDrafts[name] ?? blankDraft;
              // Activation is gated until the provider is genuinely usable:
              // a valid key (if it needs one) AND an explicitly-picked model
              // that exists in the catalog (i.e. "Get models" succeeded).
              const modelChosen = !!draft.model && models.includes(draft.model);
              const activatable = keyUsable && modelChosen;
              const activateBlockReason = !keyUsable
                ? 'Add a valid API key first'
                : models.length === 0
                  ? 'Get models first (tests connectivity & enumerates)'
                  : !draft.model
                    ? 'Pick a model first'
                    : !models.includes(draft.model)
                      ? 'Selected model is not in the catalog — Get models'
                      : isActive
                        ? `Re-apply ${name} config`
                        : `Use ${name} for extraction`;

              return (
                <div
                  key={name}
                  className={`p-4 rounded-lg border ${isActive ? 'border-status-active bg-status-active/5' : 'border-border bg-muted/50'}`}
                >
                  {/* Header: provider + active state */}
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium text-foreground capitalize">{name}</span>
                    {isActive && (
                      <span className="flex items-center gap-1 text-status-active text-xs font-medium">
                        <CheckCircle className="w-4 h-4" />
                        Active for extraction
                      </span>
                    )}
                  </div>

                  {/* Key row — only for providers that require a key */}
                  {requiresKey && (
                  <>
                  <div className="flex items-center justify-between gap-3 text-sm mb-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <Key className="w-4 h-4 text-muted-foreground shrink-0" />
                      {keyInfo?.configured ? (
                        <>
                          {keyInfo?.validation_status === 'valid' ? (
                            <span className="flex items-center gap-1 text-status-active">
                              <CheckCircle className="w-4 h-4" /> Valid
                            </span>
                          ) : (
                            <span className="flex items-center gap-1 text-status-warning">
                              <AlertCircle className="w-4 h-4" /> {keyInfo?.validation_status ?? 'Unknown'}
                            </span>
                          )}
                          {keyInfo?.masked_key && (
                            <span className="text-xs text-muted-foreground font-mono truncate">
                              {keyInfo?.masked_key}
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="text-muted-foreground">No key configured</span>
                      )}
                    </div>
                    {!editingKey && (
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => setApiKeyForm({ provider: name, key: '' })}
                          className="px-2 py-1 text-xs bg-muted text-muted-foreground rounded hover:bg-muted/80"
                        >
                          {keyInfo?.configured ? 'Replace key' : 'Add key'}
                        </button>
                        {keyInfo?.configured && (
                          <button
                            onClick={() => handleDeleteApiKey(name)}
                            disabled={deletingApiKey === name}
                            className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded disabled:opacity-50"
                            title="Delete API key"
                          >
                            {deletingApiKey === name ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Inline key form for this provider */}
                  {editingKey && (
                    <div className="mb-3 p-3 bg-background rounded border border-border space-y-3">
                      <div className="relative">
                        <input
                          type={showApiKey === name ? 'text' : 'password'}
                          value={apiKeyForm!.key}
                          onChange={(e) => setApiKeyForm({ provider: name, key: e.target.value })}
                          placeholder="sk-..."
                          autoComplete="new-password"
                          className="w-full px-3 py-2 pr-10 bg-background border border-border rounded text-foreground text-sm font-mono"
                        />
                        <button
                          type="button"
                          onClick={() => setShowApiKey(showApiKey === name ? null : name)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground"
                        >
                          {showApiKey === name ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
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
                          disabled={savingApiKey || !apiKeyForm!.key}
                          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/80 disabled:opacity-50"
                        >
                          {savingApiKey ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <><TestTube className="w-4 h-4" /> Test &amp; Save</>
                          )}
                        </button>
                      </div>
                    </div>
                  )}
                  </>
                  )}

                  {/* Endpoint row — local providers only. Uniform card: this
                      is the same slot the key occupies for cloud providers. */}
                  {isLocal && (
                    <div className="flex items-center gap-3 text-sm mb-3">
                      <Server className="w-4 h-4 text-muted-foreground shrink-0" />
                      <label className="text-muted-foreground shrink-0">Endpoint</label>
                      <input
                        type="text"
                        value={draft.base_url}
                        onChange={(e) => updateDraft(name, { base_url: e.target.value })}
                        placeholder={LOCAL_DEFAULT_BASE_URL[name] ?? 'http://host:port/v1'}
                        autoComplete="off"
                        className="flex-1 px-3 py-1.5 bg-background border border-border rounded text-foreground text-sm font-mono"
                      />
                    </div>
                  )}

                  {/* Model + reasoning controls — identical for every provider */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                    <div className="sm:col-span-3 flex items-center gap-2">
                      <label className="text-sm text-muted-foreground shrink-0 w-24">Model</label>
                      <select
                        value={draft.model}
                        onChange={(e) => updateDraft(name, { model: e.target.value })}
                        className="flex-1 px-3 py-1.5 bg-background border border-border rounded text-foreground text-sm"
                      >
                        <option value="">
                          {models.length === 0 ? 'No models — Get models first' : 'Select a model…'}
                        </option>
                        {draft.model && !models.includes(draft.model) && (
                          <option value={draft.model}>{draft.model} (saved)</option>
                        )}
                        {models.map(m => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="text-sm text-muted-foreground shrink-0 w-24">Temp</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="2"
                        value={draft.temperature}
                        onChange={(e) => updateDraft(name, { temperature: e.target.value })}
                        autoComplete="off"
                        className="w-full px-2 py-1.5 bg-background border border-border rounded text-foreground text-sm"
                      />
                    </div>
                    <div className="flex items-center gap-2 sm:col-span-2">
                      <label className="text-sm text-muted-foreground shrink-0 w-24">Max tokens</label>
                      <input
                        type="number"
                        min="1"
                        step="1"
                        value={draft.max_tokens}
                        onChange={(e) => updateDraft(name, { max_tokens: e.target.value })}
                        placeholder="model default"
                        autoComplete="off"
                        className="w-full px-2 py-1.5 bg-background border border-border rounded text-foreground text-sm"
                      />
                    </div>
                  </div>

                  {/* Actions — Save / Get models / Set active, side by side.
                      "Get models" IS the connectivity test (it enumerates).
                      "Set active" is gated until tested-valid + model picked. */}
                  <div className="flex items-center justify-between gap-3 pt-3 border-t border-border">
                    <span className="text-muted-foreground text-xs">
                      {models.length} model{models.length === 1 ? '' : 's'} in catalog
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleSaveProviderConfig(name)}
                        disabled={savingProvider !== null}
                        title="Persist this provider's config without activating it"
                        className="flex items-center gap-1 px-2.5 py-1 text-xs bg-muted text-muted-foreground rounded hover:bg-muted/80 disabled:opacity-50"
                      >
                        {savingProvider === name && <Loader2 className="w-3 h-3 animate-spin" />}
                        Save
                      </button>
                      <button
                        onClick={() => handleGetModels(name)}
                        disabled={refreshingCatalog !== null}
                        title="Save config, test connectivity, and enumerate models"
                        className="flex items-center gap-1 px-2.5 py-1 text-xs bg-muted text-muted-foreground rounded hover:bg-muted/80 disabled:opacity-50"
                      >
                        {refreshingCatalog === name ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <RefreshCw className="w-3 h-3" />
                        )}
                        Get models
                      </button>
                      <button
                        onClick={() => handleActivate(name)}
                        disabled={settingExtraction !== null || !activatable}
                        title={activateBlockReason}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/80 disabled:opacity-50"
                      >
                        {settingExtraction === name ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Play className="w-3 h-3" />
                        )}
                        {isActive ? 'Re-apply' : 'Set active'}
                      </button>
                    </div>
                  </div>

                  {/* Active provider: persisted capability detail (read-only) */}
                  {isActive && extractionConfig && (
                    <div className="mt-3 pt-3 border-t border-border flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span>Max tokens: {extractionConfig.max_tokens?.toLocaleString() ?? '—'}</span>
                      <span>Vision: {extractionConfig.supports_vision ? 'Yes' : 'No'}</span>
                      <span>JSON mode: {extractionConfig.supports_json_mode ? 'Yes' : 'No'}</span>
                      {extractionConfig.rate_limit_config && (
                        <span>
                          Concurrency: {extractionConfig.rate_limit_config.max_concurrent_requests} / {extractionConfig.rate_limit_config.max_retries} retries
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Section>
    </>
  );
};

export default SystemTab;
