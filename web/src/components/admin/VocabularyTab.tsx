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
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useAuthStore } from '../../store/authStore';
import { Section, InfoCard, formatDateTime } from './components';
import { VocabularyPressurePanel } from './VocabularyPressurePanel';
import type { VocabularyStatus, VocabularyConfig, VocabJobKind } from '../../types/vocabulary';

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

export const VocabularyTab: React.FC<VocabularyTabProps> = ({ onError, onSuccess }) => {
  const { hasPermission } = useAuthStore();
  const canManage = hasPermission('vocabulary', 'write');

  const [status, setStatus] = useState<VocabularyStatus | null>(null);
  const [config, setConfig] = useState<VocabularyConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [dispatching, setDispatching] = useState<VocabJobKind | null>(null);

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
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to load vocabulary status');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDispatch = async (action: VocabAction) => {
    setDispatching(action.kind);
    try {
      const res = await apiClient.dispatchVocabularyJob(action.kind);
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
          {ACTIONS.map((action) => (
            <button
              key={action.kind}
              onClick={() => handleDispatch(action)}
              disabled={!canManage || dispatching !== null}
              className="flex items-start gap-3 p-3 text-left bg-muted/40 rounded-lg hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
                <span className="block text-sm font-medium text-foreground">{action.label}</span>
                <span className="block text-xs text-muted-foreground">{action.description}</span>
              </span>
            </button>
          ))}
        </div>
      </Section>
    </div>
  );
};

export default VocabularyTab;
