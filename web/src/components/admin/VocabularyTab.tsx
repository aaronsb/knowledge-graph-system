/**
 * Vocabulary Tab — Vocabulary Consolidation Lifecycle Administration (ADR-701).
 *
 * The vocabulary-cycle cohort to the Ontology tab (ADR-703): the consolidation
 * loop, the pressure/zone read-out, read-only durable config, and the job-
 * dispatch actions. Present-information plus triggers — it surfaces state and
 * dispatches the four vocabulary worker operations as jobs (ADR-701 §1a),
 * mirroring the annealing "Run cycle". Per-proposal merge review is deferred.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  BookOpen,
  Activity,
  RefreshCw,
  Loader2,
  Settings,
  GitMerge,
  Sparkles,
  Layers,
  Play,
  History,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useAuthStore } from '../../store/authStore';
import { Section, InfoCard, formatDateTime } from './components';
import { VocabularyPressurePanel } from './VocabularyPressurePanel';
import type { VocabularyStatus, VocabularyConfig, VocabJobKind } from '../../types/vocabulary';
import type { JobStatus } from '../../types/jobs';

interface VocabularyTabProps {
  onError: (error: string) => void;
  onSuccess?: (message: string) => void;
}

interface VocabAction {
  kind: VocabJobKind;
  label: string;
  description: string;
  icon: React.ReactNode;
}

const ACTIONS: VocabAction[] = [
  {
    kind: 'consolidate',
    label: 'Consolidate',
    description: 'AITL merge of similar/redundant types',
    icon: <GitMerge className="w-4 h-4" />,
  },
  {
    kind: 'refresh',
    label: 'Refresh categories',
    description: 'Recompute category assignments from embeddings',
    icon: <RefreshCw className="w-4 h-4" />,
  },
  {
    kind: 'remeasure',
    label: 'Remeasure epistemic',
    description: 'Recompute grounding / epistemic status',
    icon: <Activity className="w-4 h-4" />,
  },
  {
    kind: 'embed',
    label: 'Generate embeddings',
    description: 'Backfill vocabulary type embeddings',
    icon: <Sparkles className="w-4 h-4" />,
  },
];

// The four vocabulary worker job_types, mapped to friendly labels. Mirrors the
// server-side VOCAB_JOB_KIND_TO_TYPE — used to filter the jobs feed into a
// "previous runs" log (reuses the ADR-100 jobs the Actions panel dispatches).
const VOCAB_JOB_LABELS: Record<string, string> = {
  vocab_consolidate: 'Consolidate',
  vocab_refresh: 'Refresh categories',
  epistemic_remeasurement: 'Remeasure epistemic',
  vocab_embedding: 'Generate embeddings',
};

const JOB_STATUS_STYLES: Record<string, string> = {
  completed: 'bg-status-active/20 text-status-active',
  processing: 'bg-status-info/20 text-status-info',
  approved: 'bg-status-info/20 text-status-info',
  pending: 'bg-muted text-muted-foreground',
  failed: 'bg-destructive/20 text-destructive',
  cancelled: 'bg-muted text-muted-foreground',
};

export const VocabularyTab: React.FC<VocabularyTabProps> = ({ onError, onSuccess }) => {
  const { hasPermission, isPlatformAdmin } = useAuthStore();
  const canManage = hasPermission('vocabulary', 'write');

  const [status, setStatus] = useState<VocabularyStatus | null>(null);
  const [config, setConfig] = useState<VocabularyConfig | null>(null);
  const [recentJobs, setRecentJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [dispatching, setDispatching] = useState<VocabJobKind | null>(null);
  // Consolidate executes merges (see handleActionClick); it gets a confirm step.
  const [confirmKind, setConfirmKind] = useState<VocabJobKind | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const statusRes = await apiClient.getVocabularyStatus();
      setStatus(statusRes);
      // Config is admin-only and non-essential for the loop view; tolerate failure.
      try {
        setConfig(await apiClient.getVocabularyConfig());
      } catch {
        setConfig(null);
      }
      // Previous-runs log: pull recent jobs and keep the vocabulary ones.
      try {
        const jobs = await apiClient.listJobs({ limit: 50 });
        setRecentJobs(jobs.filter((j) => j.job_type in VOCAB_JOB_LABELS).slice(0, 10));
      } catch {
        setRecentJobs([]);
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to load vocabulary status');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleActionClick = (action: VocabAction) => {
    // Consolidate executes merges (auto_mode below), so it gets a two-step
    // confirm like the ontology "Run cycle". The other three are idempotent
    // recomputations and fire immediately.
    if (action.kind === 'consolidate' && confirmKind !== 'consolidate') {
      setConfirmKind('consolidate');
      return;
    }
    setConfirmKind(null);
    void handleDispatch(action);
  };

  const handleDispatch = async (action: VocabAction) => {
    setDispatching(action.kind);
    try {
      // Without auto_mode the consolidate worker runs a dry-run no-op
      // (computes proposals, executes nothing). Opt into execution explicitly,
      // mirroring OntologyTab's triggerAnnealingCycle(false).
      const params = action.kind === 'consolidate' ? { auto_mode: true } : undefined;
      const res = await apiClient.dispatchVocabularyJob(action.kind, params);
      onSuccess?.(`${action.label} job dispatched (#${res.job_id}). Track it in Jobs.`);
      await loadData();
    } catch (err) {
      onError(err instanceof Error ? err.message : `Failed to dispatch ${action.label}`);
    } finally {
      setDispatching(null);
    }
  };

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Consolidation loop */}
      <Section
        title="Consolidation Loop"
        icon={<BookOpen className="w-5 h-5" />}
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
        {status && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <InfoCard
                icon={<Layers className="w-4 h-4" />}
                label="Vocabulary size"
                value={status.vocab_size}
                subValue={`min ${status.vocab_min} · max ${status.vocab_max}`}
              />
              <InfoCard
                icon={<BookOpen className="w-4 h-4" />}
                label="Custom types"
                value={status.custom_types}
                subValue={`${status.builtin_types} builtin`}
              />
              <InfoCard
                icon={<Layers className="w-4 h-4" />}
                label="Categories"
                value={status.categories}
              />
              <InfoCard
                icon={<Settings className="w-4 h-4" />}
                label="Pruning mode"
                value={config?.pruning_mode ?? '—'}
                subValue={`profile ${status.profile}`}
              />
            </div>
            {config?.updated_at && (
              <div className="mt-4 text-sm flex justify-between">
                <span className="text-muted-foreground">Config last updated</span>
                <span className="text-foreground">
                  {formatDateTime(config.updated_at)}
                  {config.updated_by ? ` by ${config.updated_by}` : ''}
                </span>
              </div>
            )}
          </>
        )}
      </Section>

      {/* Vocabulary pressure read-out */}
      <VocabularyPressurePanel onError={onError} />

      {/* Configuration (read-only) */}
      {config && (
        <Section title="Configuration" icon={<Settings className="w-5 h-5" />}>
          <p className="text-sm text-muted-foreground mb-3">
            Durable vocabulary configuration. Read-only here — adjust via the{' '}
            <code className="font-mono">kg vocab</code> CLI.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
            {Object.entries(config)
              .filter(([key]) => !['current_size', 'zone', 'aggressiveness'].includes(key))
              .filter(([, value]) => value !== null && value !== undefined)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([key, value]) => (
                <div key={key} className="flex justify-between border-b border-border/50 py-1">
                  <span className="text-muted-foreground">{key.replace(/_/g, ' ')}</span>
                  <span className="text-foreground font-mono text-xs">{String(value)}</span>
                </div>
              ))}
          </div>
        </Section>
      )}

      {/* Actions — job dispatch (ADR-701 §1a) */}
      <Section title="Actions" icon={<Play className="w-5 h-5" />}>
        <p className="text-sm text-muted-foreground mb-3">
          Dispatch a vocabulary maintenance operation as a background job, the
          same way ontology annealing dispatches a cycle. Each returns a job to
          track in Jobs.
          {!canManage && ' Requires the vocabulary:write permission.'}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {ACTIONS.map((action) => {
            const awaitingConfirm = confirmKind === action.kind;
            return (
              <button
                key={action.kind}
                onClick={() => handleActionClick(action)}
                disabled={!canManage || dispatching !== null}
                className={`flex items-start gap-3 p-3 text-left rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${
                  awaitingConfirm
                    ? 'bg-status-warning/15 ring-1 ring-status-warning/40 hover:bg-status-warning/20'
                    : 'bg-muted/40 hover:bg-muted'
                }`}
                title={canManage ? action.description : 'Requires vocabulary:write'}
              >
                <span className="mt-0.5 text-muted-foreground">
                  {dispatching === action.kind ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    action.icon
                  )}
                </span>
                <span>
                  <span className="block text-sm font-medium text-foreground">
                    {awaitingConfirm ? `Confirm — ${action.label} (executes merges)` : action.label}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {awaitingConfirm ? 'Click again to run, or pick another action to cancel.' : action.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </Section>

      {/* Recent runs — the previous-runs log, sourced from the jobs the Actions
          panel dispatches (analogous to the ontology proposals log, but for vocab
          the natural record is the job history).
          NOTE: GET /jobs is permission-scoped — non-admins see only their own
          jobs, and vocab_consolidate runs in the "system" lane (excluded for
          non-admins). So a non-admin's view here is partial; platform admins see
          the full history including the hysteresis/cron auto-runs. */}
      <Section title="Recent Runs" icon={<History className="w-5 h-5" />}>
        {recentJobs.length === 0 ? (
          <p className="text-sm text-muted-foreground py-2">
            No vocabulary jobs have run yet. Dispatch one from Actions above.
          </p>
        ) : (
          <div className="space-y-1.5">
            {recentJobs.map((job) => {
              const statusClass =
                JOB_STATUS_STYLES[job.status] ?? 'bg-muted text-muted-foreground';
              return (
                <div
                  key={job.job_id}
                  className="flex items-center justify-between gap-3 px-3 py-2 bg-muted/40 rounded text-sm"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-foreground">
                      {VOCAB_JOB_LABELS[job.job_type] ?? job.job_type}
                    </span>
                    <code className="font-mono text-xs text-muted-foreground truncate">
                      {job.job_id}
                    </code>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs text-muted-foreground">
                      {formatDateTime(job.completed_at ?? job.created_at ?? null)}
                    </span>
                    <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusClass}`}>
                      {job.status}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {recentJobs.length > 0 && !isPlatformAdmin && (
          <p className="mt-3 text-xs text-muted-foreground">
            Showing your jobs only. Platform admins see all vocabulary runs,
            including automatic consolidation cycles.
          </p>
        )}
      </Section>
    </div>
  );
};

export default VocabularyTab;
