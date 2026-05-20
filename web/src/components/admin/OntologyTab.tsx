/**
 * Ontology Tab — Annealing Lifecycle Administration (ADR-703)
 *
 * Insight surface and basic controls for the ontology annealing loop:
 * loop health/configuration, the proposal queue, and proposal review.
 * The annealing loop runs autonomously by default — this makes its state
 * visible without dropping to the CLI.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  RefreshCw,
  Play,
  Loader2,
  Settings,
  ListChecks,
  CheckCircle,
  XCircle,
  ArrowUpCircle,
  ArrowDownCircle,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useAuthStore } from '../../store/authStore';
import { Section, InfoCard, formatDateTime } from './components';
import type { AnnealingStatus, AnnealingProposal } from '../../types/annealing';

interface OntologyTabProps {
  onError: (error: string) => void;
  onSuccess?: (message: string) => void;
}

const AUTOMATION_STYLES: Record<string, string> = {
  autonomous: 'bg-status-warning/20 text-status-warning',
  aitl: 'bg-status-info/20 text-status-info',
  hitl: 'bg-status-active/20 text-status-active',
};

const PROPOSAL_STATUS_STYLES: Record<string, string> = {
  pending: 'bg-status-warning/20 text-status-warning',
  approved: 'bg-status-info/20 text-status-info',
  executing: 'bg-status-info/20 text-status-info',
  executed: 'bg-status-active/20 text-status-active',
  rejected: 'bg-muted text-muted-foreground',
  failed: 'bg-destructive/20 text-destructive',
  expired: 'bg-muted text-muted-foreground',
};

const Pill: React.FC<{ className?: string; children: React.ReactNode }> = ({
  className,
  children,
}) => (
  <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${className ?? 'bg-muted text-muted-foreground'}`}>
    {children}
  </span>
);

const fmtScore = (v?: number | null): string =>
  v === null || v === undefined ? '—' : v.toFixed(2);

export const OntologyTab: React.FC<OntologyTabProps> = ({ onError, onSuccess }) => {
  const { hasPermission } = useAuthStore();
  const canManage = hasPermission('ontologies', 'write');

  const [status, setStatus] = useState<AnnealingStatus | null>(null);
  const [proposals, setProposals] = useState<AnnealingProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [triggering, setTriggering] = useState(false);
  const [confirmRun, setConfirmRun] = useState(false);
  const [reviewingId, setReviewingId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statusRes, proposalsRes] = await Promise.all([
        apiClient.getAnnealingStatus(),
        apiClient.listAnnealingProposals(
          statusFilter === 'all' ? { limit: 50 } : { status: statusFilter, limit: 50 },
        ),
      ]);
      setStatus(statusRes);
      setProposals(proposalsRes.proposals);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to load annealing status');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, onError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleTrigger = async () => {
    setConfirmRun(false);
    setTriggering(true);
    try {
      const result = await apiClient.triggerAnnealingCycle(false);
      onSuccess?.(
        `Annealing cycle complete — ${result.proposals_generated} proposal(s) generated, ` +
          `${result.scores_updated} ontology score(s) updated.`,
      );
      await loadData();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to trigger annealing cycle');
    } finally {
      setTriggering(false);
    }
  };

  const handleReview = async (id: number, decision: 'approved' | 'rejected') => {
    setReviewingId(id);
    try {
      await apiClient.reviewAnnealingProposal(id, decision);
      onSuccess?.(`Proposal #${id} ${decision}.`);
      await loadData();
    } catch (err) {
      onError(err instanceof Error ? err.message : `Failed to ${decision} proposal`);
    } finally {
      setReviewingId(null);
    }
  };

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  const epochsSince = status ? status.current_epoch - status.last_annealing_epoch : 0;
  const eligible = status ? epochsSince >= status.epoch_interval : false;
  const pendingCount = status?.proposals_by_status?.pending ?? 0;

  return (
    <>
      {/* Loop health */}
      <Section
        title="Annealing Loop"
        icon={<Activity className="w-5 h-5" />}
        action={
          <div className="flex items-center gap-2">
            {canManage && (
              confirmRun ? (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setConfirmRun(false)}
                    className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleTrigger}
                    className="px-2 py-1 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90"
                  >
                    Confirm run
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmRun(true)}
                  disabled={triggering}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
                  title="Run an annealing cycle now"
                >
                  {triggering ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  Run cycle
                </button>
              )
            )}
            <button
              onClick={loadData}
              className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        }
      >
        {status && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-4 bg-muted/50 rounded-lg">
                <div className="text-sm text-muted-foreground mb-1">Automation</div>
                <Pill className={AUTOMATION_STYLES[status.automation_level] ?? undefined}>
                  {status.automation_level}
                </Pill>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg">
                <div className="text-sm text-muted-foreground mb-1">Loop status</div>
                <Pill
                  className={
                    status.enabled
                      ? 'bg-status-active/20 text-status-active'
                      : 'bg-destructive/20 text-destructive'
                  }
                >
                  {status.enabled ? 'enabled' : 'disabled'}
                </Pill>
              </div>
              <InfoCard
                icon={<ListChecks className="w-4 h-4" />}
                label="Pending proposals"
                value={pendingCount}
              />
              <InfoCard
                icon={<Activity className="w-4 h-4" />}
                label="Ontologies"
                value={status.ontology_count}
              />
            </div>

            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Last cycle ran</span>
                <span className="text-foreground">{formatDateTime(status.last_run ?? null)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Next scheduled</span>
                <span className="text-foreground">{formatDateTime(status.next_run ?? null)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Schedule (cron)</span>
                <span className="text-foreground font-mono text-xs">
                  {status.schedule_cron ?? '—'}
                  {status.schedule_cron && !status.schedule_enabled ? ' (paused)' : ''}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Epoch gate</span>
                <span className="text-foreground">
                  {epochsSince}/{status.epoch_interval} epochs since last cycle{' '}
                  <span className={eligible ? 'text-status-active' : 'text-muted-foreground'}>
                    ({eligible ? 'eligible' : 'waiting'})
                  </span>
                </span>
              </div>
            </div>
          </>
        )}
      </Section>

      {/* Configuration (read-only) */}
      {status && (
        <Section title="Configuration" icon={<Settings className="w-5 h-5" />}>
          <p className="text-sm text-muted-foreground mb-3">
            Durable annealing configuration (<code className="font-mono">annealing_options</code>).
            Read-only here — adjust via the <code className="font-mono">kg ontology</code> CLI.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
            {Object.entries(status.options)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([key, value]) => (
                <div key={key} className="flex justify-between border-b border-border/50 py-1">
                  <span className="text-muted-foreground">{key.replace(/_/g, ' ')}</span>
                  <span className="text-foreground font-mono text-xs">{value}</span>
                </div>
              ))}
          </div>
        </Section>
      )}

      {/* Proposals */}
      <Section
        title="Proposals"
        icon={<ListChecks className="w-5 h-5" />}
        action={
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-2 py-1 text-sm bg-muted border border-border rounded text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="all">All active</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="executed">Executed</option>
            <option value="rejected">Rejected</option>
            <option value="failed">Failed</option>
          </select>
        }
      >
        {proposals.length === 0 ? (
          <p className="text-muted-foreground text-center py-8">
            No proposals{statusFilter === 'all' ? '' : ` with status "${statusFilter}"`}.
          </p>
        ) : (
          <div className="space-y-3">
            {proposals.map((p) => (
              <div key={p.id} className="p-4 bg-muted/50 rounded-lg border border-border">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      {p.proposal_type === 'promotion' ? (
                        <ArrowUpCircle className="w-4 h-4 text-status-active" />
                      ) : (
                        <ArrowDownCircle className="w-4 h-4 text-status-warning" />
                      )}
                      <span className="font-medium text-foreground">
                        {p.proposal_type === 'promotion' ? 'Promote' : 'Demote'}
                      </span>
                      <span className="text-foreground">
                        {p.suggested_name || p.ontology_name}
                      </span>
                      {p.target_ontology && (
                        <span className="text-sm text-muted-foreground">
                          → {p.target_ontology}
                        </span>
                      )}
                      <Pill className={PROPOSAL_STATUS_STYLES[p.status] ?? undefined}>
                        {p.status}
                      </Pill>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{p.reasoning}</p>
                    <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
                      <span>mass {fmtScore(p.mass_score)}</span>
                      <span>coherence {fmtScore(p.coherence_score)}</span>
                      <span>protection {fmtScore(p.protection_score)}</span>
                      <span>epoch {p.created_at_epoch}</span>
                      <span>{formatDateTime(p.created_at)}</span>
                      {p.reviewed_by && <span>reviewed by {p.reviewed_by}</span>}
                    </div>
                  </div>
                  {canManage && p.status === 'pending' && (
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={() => handleReview(p.id, 'approved')}
                        disabled={reviewingId === p.id}
                        className="p-1.5 text-muted-foreground hover:text-status-active hover:bg-status-active/10 rounded transition-colors disabled:opacity-50"
                        title="Approve"
                      >
                        {reviewingId === p.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <CheckCircle className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => handleReview(p.id, 'rejected')}
                        disabled={reviewingId === p.id}
                        className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded transition-colors disabled:opacity-50"
                        title="Reject"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </>
  );
};

export default OntologyTab;
