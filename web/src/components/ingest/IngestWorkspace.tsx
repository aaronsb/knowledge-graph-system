/**
 * Ingest Workspace
 *
 * Queue-based multi-ontology ingestion interface.
 * Users drag files into specific ontology zones (existing or new).
 * Files queue up per ontology before batch ingestion.
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  Upload,
  FileText,
  Image,
  FolderOpen,
  ChevronDown,
  ChevronUp,
  Settings,
  Play,
  Loader2,
  AlertCircle,
  CheckCircle2,
  X,
  Plus,
  RefreshCw,
  PencilLine,
  Trash2,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import type {
  IngestFileRequest,
  IngestResponse,
  OntologyItem,
} from '../../types/ingest';
import { isDuplicateResponse, isImageFile, isSupportedFile, MAX_FILE_SIZE_MB } from '../../types/ingest';
import type { JobStatus } from '../../types/jobs';
import { StatusBadge, CostDisplay, ProgressIndicator } from '../workspaces/common';
import { usePreferencesStore } from '../../store/preferencesStore';

// File queue entry
interface QueuedFile {
  id: string;
  file: File;
}

// Queue per ontology
interface OntologyQueue {
  ontology: string;
  isNew: boolean;
  files: QueuedFile[];
}

// Job tracking for batch submission
interface SubmittedJob {
  ontology: string;
  filename: string;
  jobId?: string;
  status: 'pending' | 'uploading' | 'submitted' | 'failed';
  error?: string;
}

type IngestState = 'idle' | 'submitting' | 'completed';

export const IngestWorkspace: React.FC = () => {
  // Get ingest defaults from preferences store
  const { ingest: ingestDefaults } = usePreferencesStore();

  // Ontology state
  const [ontologies, setOntologies] = useState<OntologyItem[]>([]);
  const [loadingOntologies, setLoadingOntologies] = useState(false);

  // New ontology being created (in the "Create New" zone)
  const [pendingNewOntologyName, setPendingNewOntologyName] = useState<string>('');
  const [editingPendingOntology, setEditingPendingOntology] = useState(false);

  // Track which new ontology names are being edited
  const [editingOntologyName, setEditingOntologyName] = useState<string | null>(null);

  // File queues - map from ontology name to queue
  const [queues, setQueues] = useState<Map<string, OntologyQueue>>(new Map());

  // Drag state - track which zone is being hovered
  const [dragOverZone, setDragOverZone] = useState<string | null>(null);

  // Options state
  const [showOptions, setShowOptions] = useState(false);
  const [targetWords, setTargetWords] = useState(ingestDefaults.defaultChunkSize);
  const [overlapWords, setOverlapWords] = useState(200);
  const [processingMode, setProcessingMode] = useState<'serial' | 'parallel'>(ingestDefaults.defaultProcessingMode);
  const [autoApprove, setAutoApprove] = useState(ingestDefaults.autoApprove);
  const [force, setForce] = useState(false);

  // Submission state
  const [ingestState, setIngestState] = useState<IngestState>('idle');
  const [submittedJobs, setSubmittedJobs] = useState<SubmittedJob[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Load ontologies on mount
  useEffect(() => {
    loadOntologies();
  }, []);

  const loadOntologies = async () => {
    setLoadingOntologies(true);
    try {
      const response = await apiClient.listOntologies();
      setOntologies(response.ontologies);
    } catch (err) {
      console.error('Failed to load ontologies:', err);
    } finally {
      setLoadingOntologies(false);
    }
  };

  // Generate unique ID for queued files
  const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  // Validate file
  const validateFile = (file: File): string | null => {
    if (!isSupportedFile(file.name)) {
      return `Unsupported file type: ${file.name}`;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      return `File too large: ${file.name} (max ${MAX_FILE_SIZE_MB}MB)`;
    }
    return null;
  };

  // Add files to an ontology queue
  const addFilesToQueue = (ontologyName: string, files: File[], isNew: boolean) => {
    const validFiles: QueuedFile[] = [];
    const errors: string[] = [];

    for (const file of files) {
      const error = validateFile(file);
      if (error) {
        errors.push(error);
      } else {
        validFiles.push({ id: generateId(), file });
      }
    }

    if (errors.length > 0) {
      setSubmitError(errors.join('\n'));
    }

    if (validFiles.length > 0) {
      setQueues(prev => {
        const newQueues = new Map(prev);
        const existing = newQueues.get(ontologyName);
        if (existing) {
          newQueues.set(ontologyName, {
            ...existing,
            files: [...existing.files, ...validFiles],
          });
        } else {
          newQueues.set(ontologyName, {
            ontology: ontologyName,
            isNew,
            files: validFiles,
          });
        }
        return newQueues;
      });
    }
  };

  // Remove file from queue
  const removeFileFromQueue = (ontologyName: string, fileId: string) => {
    setQueues(prev => {
      const newQueues = new Map(prev);
      const queue = newQueues.get(ontologyName);
      if (queue) {
        const newFiles = queue.files.filter(f => f.id !== fileId);
        if (newFiles.length === 0) {
          newQueues.delete(ontologyName);
        } else {
          newQueues.set(ontologyName, { ...queue, files: newFiles });
        }
      }
      return newQueues;
    });
  };

  // Clear entire queue for an ontology
  const clearQueue = (ontologyName: string) => {
    setQueues(prev => {
      const newQueues = new Map(prev);
      newQueues.delete(ontologyName);
      return newQueues;
    });
  };

  // Clear all queues
  const clearAllQueues = () => {
    setQueues(new Map());
    setPendingNewOntologyName('');
    setEditingPendingOntology(false);
    setSubmitError(null);
  };

  // Handle drop on ontology zone
  const handleDrop = (e: React.DragEvent, ontologyName: string, isNew: boolean) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverZone(null);
    setSubmitError(null);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      // For the "Create New" placeholder zone, prompt for name
      if (ontologyName === '__PENDING_NEW__') {
        setEditingPendingOntology(true);
        // Store files temporarily - they'll be added when name is confirmed
        const validFiles = files.filter(f => !validateFile(f));
        if (validFiles.length > 0) {
          addFilesToQueue('__PENDING_NEW__', validFiles, true);
        }
      } else {
        addFilesToQueue(ontologyName, files, isNew);
      }
    }
  };

  // Confirm pending new ontology name - creates it and clears the pending zone
  const confirmPendingOntology = () => {
    if (!pendingNewOntologyName.trim()) return;

    const newName = pendingNewOntologyName.trim();

    // Move any files from placeholder to the real name
    setQueues(prev => {
      const newQueues = new Map(prev);
      const placeholder = newQueues.get('__PENDING_NEW__');
      if (placeholder) {
        newQueues.delete('__PENDING_NEW__');
        const existing = newQueues.get(newName);
        if (existing) {
          newQueues.set(newName, {
            ...existing,
            files: [...existing.files, ...placeholder.files],
          });
        } else {
          newQueues.set(newName, {
            ontology: newName,
            isNew: true,
            files: placeholder.files,
          });
        }
      }
      return newQueues;
    });

    // Reset the pending zone for another new ontology
    setPendingNewOntologyName('');
    setEditingPendingOntology(false);
  };

  // Rename an existing new ontology
  const renameNewOntology = (oldName: string, newName: string) => {
    if (!newName.trim() || oldName === newName.trim()) {
      setEditingOntologyName(null);
      return;
    }

    setQueues(prev => {
      const newQueues = new Map(prev);
      const queue = newQueues.get(oldName);
      if (queue) {
        newQueues.delete(oldName);
        newQueues.set(newName.trim(), {
          ...queue,
          ontology: newName.trim(),
        });
      }
      return newQueues;
    });
    setEditingOntologyName(null);
  };

  // Get total file count
  const getTotalFileCount = (): number => {
    let count = 0;
    queues.forEach(q => {
      count += q.files.length;
    });
    return count;
  };

  // Check if we can submit (no pending unnamed ontology)
  const canSubmit = getTotalFileCount() > 0 && !queues.has('__PENDING_NEW__');

  // Submit all queued files
  const handleSubmit = async () => {
    if (!canSubmit) return;

    setIngestState('submitting');
    setSubmitError(null);

    const jobs: SubmittedJob[] = [];

    // Build job list
    queues.forEach((queue, ontologyName) => {
      queue.files.forEach(qf => {
        jobs.push({
          ontology: ontologyName,
          filename: qf.file.name,
          status: 'pending',
        });
      });
    });

    setSubmittedJobs(jobs);

    // Submit each file
    let jobIndex = 0;
    for (const [ontologyName, queue] of queues) {
      for (const qf of queue.files) {
        // Update status to uploading
        setSubmittedJobs(prev => {
          const updated = [...prev];
          updated[jobIndex] = { ...updated[jobIndex], status: 'uploading' };
          return updated;
        });

        try {
          const request: IngestFileRequest = {
            ontology: ontologyName,
            filename: qf.file.name,
            force,
            auto_approve: autoApprove,
            processing_mode: processingMode,
            chunking: {
              target_words: targetWords,
              overlap_words: overlapWords,
            },
          };

          const response = await apiClient.ingestFile(qf.file, request);

          // Update status to submitted
          setSubmittedJobs(prev => {
            const updated = [...prev];
            updated[jobIndex] = {
              ...updated[jobIndex],
              status: 'submitted',
              jobId: response.job_id,
            };
            return updated;
          });
        } catch (err: any) {
          // Update status to failed
          setSubmittedJobs(prev => {
            const updated = [...prev];
            updated[jobIndex] = {
              ...updated[jobIndex],
              status: 'failed',
              error: err.response?.data?.detail || err.message || 'Upload failed',
            };
            return updated;
          });
        }

        jobIndex++;
      }
    }

    setIngestState('completed');
  };

  // Reset after completion
  const resetWorkspace = () => {
    clearAllQueues();
    setIngestState('idle');
    setSubmittedJobs([]);
    loadOntologies(); // Refresh ontology list
  };

  // Get file icon
  const getFileIcon = (filename: string) => {
    if (isImageFile(filename)) {
      return <Image className="w-4 h-4 text-purple-500" />;
    }
    return <FileText className="w-4 h-4 text-blue-500" />;
  };

  // Format file size
  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Render drop zone for an existing ontology
  const renderExistingOntologyDropZone = (ontologyName: string, conceptCount: number) => {
    const queue = queues.get(ontologyName);
    const isDragOver = dragOverZone === ontologyName;
    const hasFiles = queue && queue.files.length > 0;

    return (
      <div
        key={ontologyName}
        onDragEnter={(e) => { e.preventDefault(); setDragOverZone(ontologyName); }}
        onDragOver={(e) => { e.preventDefault(); setDragOverZone(ontologyName); }}
        onDragLeave={(e) => { e.preventDefault(); if (e.currentTarget === e.target) setDragOverZone(null); }}
        onDrop={(e) => handleDrop(e, ontologyName, false)}
        className={`
          p-4 rounded-lg border-2 transition-all min-h-[120px]
          ${isDragOver
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 border-solid'
            : hasFiles
              ? 'border-blue-300 dark:border-blue-700 bg-blue-50/50 dark:bg-blue-900/10 border-solid'
              : 'border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50 border-dashed'
          }
        `}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-blue-500" />
            <span className="font-medium text-card-foreground dark:text-gray-200">
              {ontologyName}
            </span>
            <span className="text-xs text-muted-foreground dark:text-gray-400">
              ({conceptCount} concepts)
            </span>
          </div>
          {hasFiles && (
            <button
              onClick={() => clearQueue(ontologyName)}
              className="text-gray-400 hover:text-red-500 transition-colors"
              title="Clear all files"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>

        {hasFiles ? (
          <div className="space-y-1">
            {queue.files.map((qf) => (
              <div
                key={qf.id}
                className="flex items-center justify-between py-1 px-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {getFileIcon(qf.file.name)}
                  <span className="text-sm text-card-foreground dark:text-gray-200 truncate">
                    {qf.file.name}
                  </span>
                  <span className="text-xs text-muted-foreground dark:text-gray-400 flex-shrink-0">
                    {formatSize(qf.file.size)}
                  </span>
                </div>
                <button
                  onClick={() => removeFileFromQueue(ontologyName, qf.id)}
                  className="text-gray-400 hover:text-red-500 transition-colors p-1"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
            {/* Embedded summary for this ontology */}
            <div className="mt-2 pt-2 border-t border-blue-200 dark:border-blue-700 text-xs text-blue-600 dark:text-blue-400">
              {queue.files.length} file{queue.files.length !== 1 ? 's' : ''} ready to add
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-12 text-sm text-muted-foreground dark:text-gray-400">
            <Upload className="w-4 h-4 mr-2" />
            Drop files here
          </div>
        )}
      </div>
    );
  };

  // Render drop zone for a proposed new ontology
  const renderProposedOntologyDropZone = (ontologyName: string, queue: OntologyQueue) => {
    const isDragOver = dragOverZone === ontologyName;
    const isEditing = editingOntologyName === ontologyName;

    return (
      <div
        key={ontologyName}
        onDragEnter={(e) => { e.preventDefault(); setDragOverZone(ontologyName); }}
        onDragOver={(e) => { e.preventDefault(); setDragOverZone(ontologyName); }}
        onDragLeave={(e) => { e.preventDefault(); if (e.currentTarget === e.target) setDragOverZone(null); }}
        onDrop={(e) => handleDrop(e, ontologyName, true)}
        className={`
          p-4 rounded-lg border-2 border-dashed transition-all
          ${isDragOver
            ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
            : 'border-green-400 dark:border-green-600 bg-green-50/50 dark:bg-green-900/10'
          }
        `}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 flex-1">
            <Plus className="w-4 h-4 text-green-500 flex-shrink-0" />
            {isEditing ? (
              <input
                type="text"
                defaultValue={ontologyName}
                onBlur={(e) => renameNewOntology(ontologyName, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') renameNewOntology(ontologyName, (e.target as HTMLInputElement).value);
                  if (e.key === 'Escape') setEditingOntologyName(null);
                }}
                className="flex-1 px-2 py-1 text-sm bg-white dark:bg-gray-800 border border-green-300 dark:border-green-600 rounded focus:outline-none focus:ring-2 focus:ring-green-500"
                autoFocus
              />
            ) : (
              <>
                <span className="font-medium text-card-foreground dark:text-gray-200">
                  {ontologyName}
                </span>
                <span className="text-xs text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30 px-2 py-0.5 rounded">
                  will be created
                </span>
                <button
                  onClick={() => setEditingOntologyName(ontologyName)}
                  className="text-gray-400 hover:text-green-600 transition-colors p-1"
                  title="Edit name"
                >
                  <PencilLine className="w-3 h-3" />
                </button>
              </>
            )}
          </div>
          <button
            onClick={() => clearQueue(ontologyName)}
            className="text-gray-400 hover:text-red-500 transition-colors"
            title="Remove this ontology"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        {/* File list */}
        <div className="space-y-1 mb-3">
          {queue.files.map((qf) => (
            <div
              key={qf.id}
              className="flex items-center justify-between py-1 px-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700"
            >
              <div className="flex items-center gap-2 min-w-0">
                {getFileIcon(qf.file.name)}
                <span className="text-sm text-card-foreground dark:text-gray-200 truncate">
                  {qf.file.name}
                </span>
                <span className="text-xs text-muted-foreground dark:text-gray-400 flex-shrink-0">
                  {formatSize(qf.file.size)}
                </span>
              </div>
              <button
                onClick={() => removeFileFromQueue(ontologyName, qf.id)}
                className="text-gray-400 hover:text-red-500 transition-colors p-1"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>

        {/* Embedded summary */}
        <div className="pt-2 border-t border-green-200 dark:border-green-700 text-xs text-green-600 dark:text-green-400">
          Ready: Create "{ontologyName}" with {queue.files.length} file{queue.files.length !== 1 ? 's' : ''}
        </div>
      </div>
    );
  };

  // Render the "Create New Ontology" placeholder zone (always visible)
  const renderCreateNewZone = () => {
    const pendingQueue = queues.get('__PENDING_NEW__');
    const hasPendingFiles = pendingQueue && pendingQueue.files.length > 0;
    const isDragOver = dragOverZone === '__PENDING_NEW__';

    return (
      <div
        onDragEnter={(e) => { e.preventDefault(); setDragOverZone('__PENDING_NEW__'); }}
        onDragOver={(e) => { e.preventDefault(); setDragOverZone('__PENDING_NEW__'); }}
        onDragLeave={(e) => { e.preventDefault(); if (e.currentTarget === e.target) setDragOverZone(null); }}
        onDrop={(e) => handleDrop(e, '__PENDING_NEW__', true)}
        className={`
          p-4 rounded-lg border-2 border-dashed transition-all min-h-[100px]
          ${isDragOver
            ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
            : 'border-green-400 dark:border-green-600 bg-gray-50 dark:bg-gray-800/50'
          }
        `}
      >
        {editingPendingOntology || hasPendingFiles ? (
          <div className="space-y-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={pendingNewOntologyName}
                onChange={(e) => setPendingNewOntologyName(e.target.value)}
                placeholder="Enter new ontology name"
                className="flex-1 px-3 py-2 bg-white dark:bg-gray-800 border border-green-300 dark:border-green-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && pendingNewOntologyName.trim()) {
                    confirmPendingOntology();
                  }
                  if (e.key === 'Escape') {
                    setEditingPendingOntology(false);
                    setPendingNewOntologyName('');
                    clearQueue('__PENDING_NEW__');
                  }
                }}
              />
              <button
                onClick={confirmPendingOntology}
                disabled={!pendingNewOntologyName.trim()}
                className="px-4 py-2 bg-green-500 hover:bg-green-600 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white rounded-lg transition-colors"
              >
                Create
              </button>
              <button
                onClick={() => {
                  setEditingPendingOntology(false);
                  setPendingNewOntologyName('');
                  clearQueue('__PENDING_NEW__');
                }}
                className="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
            {hasPendingFiles && (
              <div className="space-y-1">
                <div className="text-xs text-amber-600 dark:text-amber-400">
                  Name this ontology to continue:
                </div>
                {pendingQueue.files.map((qf) => (
                  <div
                    key={qf.id}
                    className="flex items-center gap-2 py-1 px-2 bg-amber-50 dark:bg-amber-900/20 rounded border border-amber-200 dark:border-amber-700"
                  >
                    {getFileIcon(qf.file.name)}
                    <span className="text-sm truncate">{qf.file.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground dark:text-gray-400">
            <Plus className="w-6 h-6 mb-2 text-green-500" />
            <div className="text-sm font-medium text-green-600 dark:text-green-400">Create New Ontology</div>
            <div className="text-xs">Drop files to start</div>
          </div>
        )}
      </div>
    );
  };

  // Get all proposed (new) ontologies from queues
  const getProposedOntologies = (): [string, OntologyQueue][] => {
    const proposed: [string, OntologyQueue][] = [];
    queues.forEach((queue, name) => {
      if (queue.isNew && name !== '__PENDING_NEW__') {
        proposed.push([name, queue]);
      }
    });
    return proposed;
  };

  // Render global summary section (simple totals)
  const renderGlobalSummary = () => {
    let existingCount = 0;
    let newCount = 0;
    let existingOntologies = 0;
    let newOntologies = 0;

    queues.forEach((queue, ontologyName) => {
      if (ontologyName === '__PENDING_NEW__') return;
      if (queue.isNew) {
        newCount += queue.files.length;
        newOntologies++;
      } else {
        existingCount += queue.files.length;
        existingOntologies++;
      }
    });

    const total = existingCount + newCount;
    if (total === 0) return null;

    return (
      <div className="p-4 bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
        <div className="text-sm font-medium text-foreground dark:text-gray-200 mb-2">
          Summary
        </div>
        <div className="text-sm text-muted-foreground dark:text-gray-400 space-y-1">
          {existingCount > 0 && (
            <div>
              {existingCount} file{existingCount !== 1 ? 's' : ''} → {existingOntologies} existing ontolog{existingOntologies !== 1 ? 'ies' : 'y'}
            </div>
          )}
          {newCount > 0 && (
            <div className="text-green-600 dark:text-green-400">
              {newCount} file{newCount !== 1 ? 's' : ''} → {newOntologies} new ontolog{newOntologies !== 1 ? 'ies' : 'y'} (will be created)
            </div>
          )}
          <div className="pt-1 border-t border-gray-200 dark:border-gray-600 font-medium text-foreground dark:text-gray-200">
            Total: {total} file{total !== 1 ? 's' : ''} ready
          </div>
        </div>
      </div>
    );
  };

  // Render submission progress
  const renderSubmissionProgress = () => {
    return (
      <div className="space-y-4">
        <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <div className="flex items-center gap-2 mb-4">
            {ingestState === 'submitting' ? (
              <>
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                <span className="font-medium text-blue-800 dark:text-blue-200">Submitting files...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-5 h-5 text-green-500" />
                <span className="font-medium text-green-800 dark:text-green-200">Submission complete</span>
              </>
            )}
          </div>

          <div className="space-y-2">
            {submittedJobs.map((job, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2 px-3 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {job.status === 'uploading' && <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />}
                  {job.status === 'submitted' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                  {job.status === 'failed' && <AlertCircle className="w-4 h-4 text-red-500" />}
                  {job.status === 'pending' && <div className="w-4 h-4 rounded-full border-2 border-gray-300" />}
                  <span className="text-sm truncate">{job.filename}</span>
                  <span className="text-xs text-muted-foreground">→ {job.ontology}</span>
                </div>
                {job.status === 'failed' && (
                  <span className="text-xs text-red-500">{job.error}</span>
                )}
              </div>
            ))}
          </div>
        </div>

        {ingestState === 'completed' && (
          <div className="flex gap-2">
            <button
              onClick={resetWorkspace}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors"
            >
              <Plus className="w-5 h-5" />
              Ingest More
            </button>
            <button
              onClick={() => window.location.href = '/jobs'}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-card-foreground dark:text-gray-200 rounded-lg font-medium transition-colors"
            >
              View Jobs
            </button>
          </div>
        )}
      </div>
    );
  };

  // Main render
  if (ingestState === 'submitting' || ingestState === 'completed') {
    return (
      <div className="h-full flex flex-col bg-background dark:bg-gray-950">
        <div className="flex-none p-6 border-b border-border dark:border-gray-800">
          <div className="flex items-center gap-3">
            <Upload className="w-6 h-6 text-primary dark:text-blue-400" />
            <div>
              <h1 className="text-xl font-semibold text-foreground dark:text-gray-100">
                Ingest Content
              </h1>
              <p className="text-sm text-muted-foreground dark:text-gray-400">
                {ingestState === 'submitting' ? 'Uploading files...' : 'Files submitted'}
              </p>
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            {renderSubmissionProgress()}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background dark:bg-gray-950">
      {/* Header */}
      <div className="flex-none p-6 border-b border-border dark:border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Upload className="w-6 h-6 text-primary dark:text-blue-400" />
            <div>
              <h1 className="text-xl font-semibold text-foreground dark:text-gray-100">
                Ingest Content
              </h1>
              <p className="text-sm text-muted-foreground dark:text-gray-400">
                Drag files into ontology zones to queue for ingestion
              </p>
            </div>
          </div>
          <button
            onClick={loadOntologies}
            className="p-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
            title="Refresh ontologies"
            disabled={loadingOntologies}
          >
            <RefreshCw className={`w-5 h-5 ${loadingOntologies ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Error display */}
          {submitError && (
            <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="text-sm whitespace-pre-line">{submitError}</div>
              <button onClick={() => setSubmitError(null)} className="ml-auto">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Existing Ontologies */}
          {ontologies.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-sm font-medium text-muted-foreground dark:text-gray-400 uppercase tracking-wide">
                Existing Ontologies
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {ontologies.map((ont) => renderExistingOntologyDropZone(ont.ontology, ont.concept_count))}
              </div>
            </div>
          )}

          {/* Proposed New Ontologies */}
          {getProposedOntologies().length > 0 && (
            <div className="space-y-3">
              <h2 className="text-sm font-medium text-green-600 dark:text-green-400 uppercase tracking-wide">
                New Ontologies (will be created)
              </h2>
              <div className="space-y-4">
                {getProposedOntologies().map(([name, queue]) => renderProposedOntologyDropZone(name, queue))}
              </div>
            </div>
          )}

          {/* Create New Ontology Zone - Always visible */}
          <div className="space-y-3">
            <h2 className="text-sm font-medium text-muted-foreground dark:text-gray-400 uppercase tracking-wide">
              {ontologies.length > 0 || getProposedOntologies().length > 0 ? 'Add Another Ontology' : 'Create Ontology'}
            </h2>
            {renderCreateNewZone()}
          </div>

          {/* Global Summary */}
          {renderGlobalSummary()}

          {/* Options */}
          {getTotalFileCount() > 0 && (
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
              <button
                onClick={() => setShowOptions(!showOptions)}
                className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Settings className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-medium text-card-foreground dark:text-gray-200">
                    Ingestion Options
                  </span>
                </div>
                {showOptions ? (
                  <ChevronUp className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                )}
              </button>

              {showOptions && (
                <div className="p-4 space-y-4 border-t border-gray-200 dark:border-gray-700">
                  {/* Chunking settings */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-muted-foreground dark:text-gray-400 mb-2">
                        Target Words per Chunk
                      </label>
                      <input
                        type="number"
                        value={targetWords}
                        onChange={(e) => setTargetWords(parseInt(e.target.value) || 1000)}
                        className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg"
                        min={100}
                        max={5000}
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-muted-foreground dark:text-gray-400 mb-2">
                        Overlap Words
                      </label>
                      <input
                        type="number"
                        value={overlapWords}
                        onChange={(e) => setOverlapWords(parseInt(e.target.value) || 200)}
                        className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg"
                        min={0}
                        max={500}
                      />
                    </div>
                  </div>

                  {/* Processing mode */}
                  <div>
                    <label className="block text-sm text-muted-foreground dark:text-gray-400 mb-2">
                      Processing Mode
                    </label>
                    <div className="flex gap-4">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={processingMode === 'serial'}
                          onChange={() => setProcessingMode('serial')}
                          className="text-blue-500"
                        />
                        <span className="text-sm">Serial (better quality)</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={processingMode === 'parallel'}
                          onChange={() => setProcessingMode('parallel')}
                          className="text-blue-500"
                        />
                        <span className="text-sm">Parallel (faster)</span>
                      </label>
                    </div>
                  </div>

                  {/* Checkboxes */}
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={autoApprove}
                        onChange={(e) => setAutoApprove(e.target.checked)}
                        className="rounded text-blue-500"
                      />
                      <span className="text-sm">Auto-approve (start immediately)</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={force}
                        onChange={(e) => setForce(e.target.checked)}
                        className="rounded text-blue-500"
                      />
                      <span className="text-sm">Force re-ingestion (skip duplicate check)</span>
                    </label>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Submit Button */}
          {getTotalFileCount() > 0 && (
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className={`
                w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors
                ${canSubmit
                  ? 'bg-blue-500 hover:bg-blue-600 text-white'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
                }
              `}
            >
              <Play className="w-5 h-5" />
              Start Ingestion ({getTotalFileCount()} file{getTotalFileCount() !== 1 ? 's' : ''})
            </button>
          )}

          {/* Clear all button */}
          {getTotalFileCount() > 0 && (
            <button
              onClick={clearAllQueues}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              Clear all queued files
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default IngestWorkspace;
