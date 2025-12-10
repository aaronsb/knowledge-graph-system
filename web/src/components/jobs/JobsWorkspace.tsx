/**
 * JobsWorkspace
 *
 * Job queue visibility and management with real-time updates.
 * Displays job list with filtering, detail view, and approve/cancel actions.
 * Follows ADR-014 job lifecycle.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  ListTodo,
  RefreshCw,
  ChevronDown,
  FileText,
  Clock,
  CheckCircle2,
  XCircle,
  PlayCircle,
  Trash2,
  ExternalLink,
  Info,
  AlertTriangle,
  ChevronLeft,
  Loader2,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import type {
  JobStatus,
  JobStatusValue,
  JobListFilters,
} from '../../types/jobs';
import {
  StatusBadge,
  CostDisplay,
  ProgressIndicator,
} from '../workspaces/common';

// Status filter options
const STATUS_FILTERS: { value: JobStatusValue | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'awaiting_approval', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
];

// Helper: format relative time
const formatRelativeTime = (dateStr: string): string => {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
};

// Helper: format duration
const formatDuration = (startStr: string, endStr: string): string => {
  const start = new Date(startStr).getTime();
  const end = new Date(endStr).getTime();
  const diffSec = Math.floor((end - start) / 1000);

  if (diffSec < 60) return `${diffSec}s`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ${diffSec % 60}s`;
  return `${Math.floor(diffSec / 3600)}h ${Math.floor((diffSec % 3600) / 60)}m`;
};

export const JobsWorkspace: React.FC = () => {
  // Job list state
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<JobStatusValue | 'all'>('all');
  const [refreshing, setRefreshing] = useState(false);

  // Selected job state
  const [selectedJob, setSelectedJob] = useState<JobStatus | null>(null);
  const [selectedJobLoading, setSelectedJobLoading] = useState(false);

  // Action state
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Auto-refresh for active jobs
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch jobs list
  const fetchJobs = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    try {
      const filters: JobListFilters = { limit: 100 };
      if (statusFilter !== 'all') {
        filters.status = statusFilter;
      }
      const data = await apiClient.listJobs(filters);
      setJobs(data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch jobs');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter]);

  // Fetch single job details
  const fetchJobDetails = useCallback(async (jobId: string) => {
    setSelectedJobLoading(true);
    try {
      const data = await apiClient.getJob(jobId);
      setSelectedJob(data);
    } catch (err: any) {
      console.error('Failed to fetch job details:', err);
    } finally {
      setSelectedJobLoading(false);
    }
  }, []);

  // Initial fetch and filter changes
  useEffect(() => {
    setLoading(true);
    fetchJobs();
  }, [statusFilter, fetchJobs]);

  // Auto-refresh when there are active jobs
  useEffect(() => {
    const hasActiveJobs = jobs.some(j =>
      ['pending', 'awaiting_approval', 'approved', 'queued', 'processing'].includes(j.status)
    );

    if (hasActiveJobs) {
      refreshIntervalRef.current = setInterval(() => {
        fetchJobs();
        // Also refresh selected job if it's active
        if (selectedJob && ['pending', 'awaiting_approval', 'approved', 'queued', 'processing'].includes(selectedJob.status)) {
          fetchJobDetails(selectedJob.job_id);
        }
      }, 3000);
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [jobs, selectedJob, fetchJobs, fetchJobDetails]);

  // Approve job
  const handleApprove = async (jobId: string) => {
    setActionLoading(jobId);
    try {
      await apiClient.approveJob(jobId);
      await fetchJobs();
      if (selectedJob?.job_id === jobId) {
        await fetchJobDetails(jobId);
      }
    } catch (err: any) {
      alert(`Failed to approve job: ${err.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Cancel job
  const handleCancel = async (jobId: string) => {
    if (!confirm('Are you sure you want to cancel this job?')) return;

    setActionLoading(jobId);
    try {
      await apiClient.cancelJob(jobId);
      await fetchJobs();
      if (selectedJob?.job_id === jobId) {
        await fetchJobDetails(jobId);
      }
    } catch (err: any) {
      alert(`Failed to cancel job: ${err.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Select job
  const handleSelectJob = (job: JobStatus) => {
    setSelectedJob(job);
    fetchJobDetails(job.job_id);
  };

  // Back to list
  const handleBackToList = () => {
    setSelectedJob(null);
  };

  // Render job row
  const renderJobRow = (job: JobStatus) => {
    const isSelected = selectedJob?.job_id === job.job_id;
    const isActionable = ['awaiting_approval', 'approved', 'queued', 'processing'].includes(job.status);

    return (
      <div
        key={job.job_id}
        onClick={() => handleSelectJob(job)}
        className={`
          p-3 border-b border-border
          hover:bg-accent
          cursor-pointer transition-colors
          ${isSelected ? 'bg-status-info/20 border-l-2 border-l-primary' : ''}
        `}
      >
        <div className="flex items-center justify-between gap-3">
          {/* Status and source */}
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <StatusBadge status={job.status} size="sm" showLabel={false} />
            <div className="min-w-0 flex-1">
              <div className="font-medium text-card-foreground truncate">
                {job.source_path || job.filename || 'Unknown source'}
              </div>
              <div className="text-xs text-muted-foreground truncate">
                {job.ontology || 'No ontology'} • {job.job_id.substring(0, 12)}...
              </div>
            </div>
          </div>

          {/* Progress (for processing jobs) */}
          {job.status === 'processing' && job.progress?.percent !== undefined && (
            <div className="hidden sm:flex items-center gap-2 text-sm text-muted-foreground">
              <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-status-info transition-all duration-300"
                  style={{ width: `${job.progress.percent}%` }}
                />
              </div>
              <span className="w-10 text-right">{job.progress.percent}%</span>
            </div>
          )}

          {/* Time */}
          <div className="text-xs text-muted-foreground whitespace-nowrap">
            {formatRelativeTime(job.created_at)}
          </div>

          {/* Quick actions */}
          {isActionable && (
            <div className="flex items-center gap-1">
              {job.status === 'awaiting_approval' && (
                <button
                  onClick={(e) => { e.stopPropagation(); handleApprove(job.job_id); }}
                  disabled={actionLoading === job.job_id}
                  className="p-1 text-status-active hover:bg-status-active/20 rounded transition-colors disabled:opacity-50"
                  title="Approve"
                >
                  {actionLoading === job.job_id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <PlayCircle className="w-4 h-4" />
                  )}
                </button>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); handleCancel(job.job_id); }}
                disabled={actionLoading === job.job_id}
                className="p-1 text-destructive hover:bg-destructive/20 rounded transition-colors disabled:opacity-50"
                title="Cancel"
              >
                <XCircle className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Render job detail panel
  const renderJobDetail = () => {
    if (!selectedJob) return null;

    const job = selectedJob;
    const isActionable = ['awaiting_approval', 'approved', 'queued', 'processing'].includes(job.status);

    return (
      <div className="h-full flex flex-col bg-card">
        {/* Header */}
        <div className="p-4 border-b border-border">
          <button
            onClick={handleBackToList}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-card-foreground mb-3"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to list
          </button>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-semibold text-card-foreground truncate">
                {job.source_path || job.filename || 'Unknown source'}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <StatusBadge status={job.status} size="sm" />
                {job.ontology && (
                  <span className="text-sm text-muted-foreground">
                    {job.ontology}
                  </span>
                )}
              </div>
            </div>
            {selectedJobLoading && (
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Metadata */}
          <div className="bg-muted rounded-lg p-3 space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <Info className="w-4 h-4 text-muted-foreground" />
              <span className="font-medium text-card-foreground">Details</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="text-muted-foreground">Job ID:</div>
              <div className="text-card-foreground font-mono text-xs break-all">
                {job.job_id}
              </div>
              <div className="text-muted-foreground">Type:</div>
              <div className="text-card-foreground">{job.job_type}</div>
              <div className="text-muted-foreground">Created:</div>
              <div className="text-card-foreground">
                {new Date(job.created_at).toLocaleString()}
              </div>
              {job.started_at && (
                <>
                  <div className="text-muted-foreground">Started:</div>
                  <div className="text-card-foreground">
                    {new Date(job.started_at).toLocaleString()}
                  </div>
                </>
              )}
              {job.completed_at && (
                <>
                  <div className="text-muted-foreground">Completed:</div>
                  <div className="text-card-foreground">
                    {new Date(job.completed_at).toLocaleString()}
                  </div>
                  <div className="text-muted-foreground">Duration:</div>
                  <div className="text-card-foreground">
                    {formatDuration(job.created_at, job.completed_at)}
                  </div>
                </>
              )}
              {job.username && (
                <>
                  <div className="text-muted-foreground">User:</div>
                  <div className="text-card-foreground">{job.username}</div>
                </>
              )}
            </div>
          </div>

          {/* Analysis (for awaiting_approval) */}
          {job.analysis && (
            <div className="bg-status-warning/20 rounded-lg p-3 space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <FileText className="w-4 h-4 text-status-warning" />
                <span className="font-medium text-foreground">
                  Pre-Ingestion Analysis
                </span>
              </div>

              {job.analysis.file_stats && (
                <div className="text-sm space-y-1">
                  <div className="text-foreground">
                    {job.analysis.file_stats.filename} ({job.analysis.file_stats.size_human})
                  </div>
                  <div className="text-muted-foreground">
                    {job.analysis.file_stats.word_count.toLocaleString()} words •
                    ~{job.analysis.file_stats.estimated_chunks} chunks
                  </div>
                </div>
              )}

              {job.analysis.cost_estimate && (
                <CostDisplay estimate={job.analysis.cost_estimate} />
              )}

              {job.analysis.warnings && job.analysis.warnings.length > 0 && (
                <div className="pt-2 border-t border-status-warning/30">
                  <div className="flex items-center gap-1 text-sm text-status-warning mb-1">
                    <AlertTriangle className="w-3 h-3" />
                    Warnings
                  </div>
                  <ul className="text-sm text-muted-foreground list-disc list-inside">
                    {job.analysis.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Progress */}
          {job.progress && job.status === 'processing' && (
            <div className="bg-status-info/20 rounded-lg p-3">
              <ProgressIndicator progress={job.progress} variant="detailed" />
            </div>
          )}

          {/* Results */}
          {job.result && job.status === 'completed' && (
            <div className="bg-status-active/10 rounded-lg p-3 space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="w-4 h-4 text-status-active" />
                <span className="font-medium text-status-active">Results</span>
              </div>

              {job.result.stats && (
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="text-muted-foreground">Chunks processed:</div>
                  <div className="text-foreground">{job.result.stats.chunks_processed}</div>
                  <div className="text-muted-foreground">Concepts created:</div>
                  <div className="text-foreground">{job.result.stats.concepts_created}</div>
                  <div className="text-muted-foreground">Concepts linked:</div>
                  <div className="text-foreground">{job.result.stats.concepts_linked}</div>
                  <div className="text-muted-foreground">Sources created:</div>
                  <div className="text-foreground">{job.result.stats.sources_created}</div>
                  <div className="text-muted-foreground">Relationships:</div>
                  <div className="text-foreground">{job.result.stats.relationships_created}</div>
                </div>
              )}

              {job.result.cost && (
                <div className="pt-2 border-t border-status-active/30">
                  <CostDisplay actual={job.result.cost} />
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {job.error && (
            <div className="bg-destructive/20 rounded-lg p-3">
              <div className="flex items-center gap-2 text-sm mb-2">
                <XCircle className="w-4 h-4 text-destructive" />
                <span className="font-medium text-destructive">Error</span>
              </div>
              <div className="text-sm text-foreground font-mono break-words">
                {job.error}
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        {isActionable && (
          <div className="p-4 border-t border-border flex gap-2">
            {job.status === 'awaiting_approval' && (
              <button
                onClick={() => handleApprove(job.job_id)}
                disabled={actionLoading === job.job_id}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-status-active hover:bg-status-active/80 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {actionLoading === job.job_id ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <PlayCircle className="w-4 h-4" />
                )}
                Approve
              </button>
            )}
            <button
              onClick={() => handleCancel(job.job_id)}
              disabled={actionLoading === job.job_id}
              className={`
                flex items-center justify-center gap-2 px-4 py-2
                ${job.status === 'awaiting_approval'
                  ? 'border border-destructive/50 text-destructive hover:bg-destructive/20'
                  : 'flex-1 bg-destructive hover:bg-destructive/80 text-white'
                }
                rounded-lg transition-colors disabled:opacity-50
              `}
            >
              <XCircle className="w-4 h-4" />
              Cancel
            </button>
          </div>
        )}
      </div>
    );
  };

  // Main render
  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="flex-none p-4 border-b border-border">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <ListTodo className="w-5 h-5 text-primary" />
            <h1 className="text-lg font-semibold text-foreground">
              Jobs
            </h1>
            {!loading && (
              <span className="text-sm text-muted-foreground">
                ({jobs.length})
              </span>
            )}
          </div>

          <button
            onClick={() => fetchJobs(true)}
            disabled={refreshing}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded-lg transition-colors disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Status filter tabs */}
        <div className="flex gap-1 mt-3 overflow-x-auto pb-1">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.value}
              onClick={() => setStatusFilter(filter.value)}
              className={`
                px-3 py-1.5 text-sm rounded-lg whitespace-nowrap transition-colors
                ${statusFilter === filter.value
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                }
              `}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 flex min-h-0">
        {/* Job list (or full screen if no selection) */}
        <div className={`
          ${selectedJob ? 'hidden md:block md:w-1/2 lg:w-2/5 border-r border-border' : 'w-full'}
          overflow-y-auto
        `}>
          {loading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="p-4 text-center">
              <div className="text-destructive mb-2">{error}</div>
              <button
                onClick={() => fetchJobs()}
                className="text-sm text-primary hover:underline"
              >
                Try again
              </button>
            </div>
          ) : jobs.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <ListTodo className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <div className="font-medium mb-1">No jobs found</div>
              <div className="text-sm">
                {statusFilter !== 'all'
                  ? `No ${STATUS_FILTERS.find(f => f.value === statusFilter)?.label.toLowerCase()} jobs`
                  : 'Ingest a document to create your first job'
                }
              </div>
            </div>
          ) : (
            <div>
              {jobs.map(renderJobRow)}
            </div>
          )}
        </div>

        {/* Job detail panel */}
        {selectedJob && (
          <div className="flex-1 min-w-0">
            {renderJobDetail()}
          </div>
        )}
      </div>
    </div>
  );
};

export default JobsWorkspace;
