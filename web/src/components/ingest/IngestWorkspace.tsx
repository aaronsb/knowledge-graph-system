/**
 * Ingest Workspace
 *
 * Web-based content ingestion interface.
 * Supports drag-drop file upload with ontology selection and job monitoring.
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

type IngestState = 'idle' | 'uploading' | 'submitted' | 'processing' | 'completed' | 'failed';

export const IngestWorkspace: React.FC = () => {
  // Get ingest defaults from preferences store
  const { ingest: ingestDefaults } = usePreferencesStore();

  // File state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  // Ontology state
  const [ontologies, setOntologies] = useState<OntologyItem[]>([]);
  const [selectedOntology, setSelectedOntology] = useState<string>(ingestDefaults.defaultOntology);
  const [newOntologyName, setNewOntologyName] = useState<string>('');
  const [showNewOntology, setShowNewOntology] = useState(false);
  const [loadingOntologies, setLoadingOntologies] = useState(false);

  // Options state (initialized from preferences)
  const [showOptions, setShowOptions] = useState(false);
  const [targetWords, setTargetWords] = useState(ingestDefaults.defaultChunkSize);
  const [overlapWords, setOverlapWords] = useState(200);
  const [processingMode, setProcessingMode] = useState<'serial' | 'parallel'>(ingestDefaults.defaultProcessingMode);
  const [autoApprove, setAutoApprove] = useState(ingestDefaults.autoApprove);
  const [force, setForce] = useState(false);

  // Job state
  const [ingestState, setIngestState] = useState<IngestState>('idle');
  const [currentJob, setCurrentJob] = useState<JobStatus | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [duplicateInfo, setDuplicateInfo] = useState<{ jobId: string; message: string } | null>(null);

  // Load ontologies on mount
  useEffect(() => {
    loadOntologies();
  }, []);

  const loadOntologies = async () => {
    setLoadingOntologies(true);
    try {
      const response = await apiClient.listOntologies();
      setOntologies(response.ontologies);
      // Use preference default if set, otherwise select first ontology
      if (!selectedOntology) {
        if (ingestDefaults.defaultOntology && response.ontologies.some(o => o.ontology === ingestDefaults.defaultOntology)) {
          setSelectedOntology(ingestDefaults.defaultOntology);
        } else if (response.ontologies.length > 0) {
          setSelectedOntology(response.ontologies[0].ontology);
        }
      }
    } catch (err) {
      console.error('Failed to load ontologies:', err);
    } finally {
      setLoadingOntologies(false);
    }
  };

  // File drop handlers
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const validateFile = (file: File): string | null => {
    if (!isSupportedFile(file.name)) {
      return `Unsupported file type. Supported: .txt, .md, .rst, .pdf, .png, .jpg, .jpeg, .gif, .webp, .bmp`;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      return `File too large. Maximum size: ${MAX_FILE_SIZE_MB}MB`;
    }
    return null;
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    setFileError(null);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      const error = validateFile(file);
      if (error) {
        setFileError(error);
      } else {
        setSelectedFile(file);
        setDuplicateInfo(null);
      }
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError(null);
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      const error = validateFile(file);
      if (error) {
        setFileError(error);
      } else {
        setSelectedFile(file);
        setDuplicateInfo(null);
      }
    }
  }, []);

  const clearFile = () => {
    setSelectedFile(null);
    setFileError(null);
    setDuplicateInfo(null);
    setIngestState('idle');
    setCurrentJob(null);
    setSubmitError(null);
  };

  // Get effective ontology name
  const getOntologyName = (): string => {
    if (showNewOntology && newOntologyName.trim()) {
      return newOntologyName.trim();
    }
    return selectedOntology;
  };

  // Submit ingestion
  const handleSubmit = async () => {
    if (!selectedFile) return;

    const ontologyName = getOntologyName();
    if (!ontologyName) {
      setSubmitError('Please select or create an ontology');
      return;
    }

    setIngestState('uploading');
    setSubmitError(null);
    setDuplicateInfo(null);

    try {
      const request: IngestFileRequest = {
        ontology: ontologyName,
        filename: selectedFile.name,
        force,
        auto_approve: autoApprove,
        processing_mode: processingMode,
        source_type: 'web',
        options: {
          target_words: targetWords,
          overlap_words: overlapWords,
        },
      };

      const response = await apiClient.ingestFile(selectedFile, request);

      if (isDuplicateResponse(response)) {
        setDuplicateInfo({
          jobId: response.existing_job_id,
          message: response.message,
        });
        setIngestState('idle');
        return;
      }

      // Job submitted successfully
      setIngestState('submitted');

      // Start monitoring the job
      monitorJob(response.job_id);

    } catch (err: any) {
      setSubmitError(err.response?.data?.detail || err.message || 'Upload failed');
      setIngestState('failed');
    }
  };

  // Monitor job progress
  const monitorJob = async (jobId: string) => {
    // First, try SSE streaming
    const cleanup = apiClient.streamJobProgress(jobId, {
      onProgress: (event) => {
        setCurrentJob(prev => prev ? {
          ...prev,
          status: 'processing',
          progress: {
            stage: event.stage,
            percent: event.percent,
            chunks_processed: event.chunks_processed,
            chunks_total: event.chunks_total,
            concepts_created: event.concepts_created,
            concepts_linked: event.concepts_linked,
            relationships_created: event.relationships_created,
          },
        } : null);
        setIngestState('processing');
      },
      onCompleted: (event) => {
        setCurrentJob(prev => prev ? {
          ...prev,
          status: 'completed',
          result: {
            status: event.status,
            stats: event.stats,
            cost: event.cost,
          },
        } : null);
        setIngestState('completed');
        // Refresh ontologies to show updated counts
        loadOntologies();
      },
      onFailed: (event) => {
        setCurrentJob(prev => prev ? {
          ...prev,
          status: 'failed',
          error: event.error,
        } : null);
        setIngestState('failed');
      },
      onError: async () => {
        // SSE failed, fall back to polling
        console.log('SSE failed, falling back to polling');
        try {
          const finalJob = await apiClient.pollJobUntilComplete(jobId, {
            onProgress: (job) => {
              setCurrentJob(job);
              if (job.status === 'processing') {
                setIngestState('processing');
              }
            },
          });
          setCurrentJob(finalJob);
          setIngestState(finalJob.status === 'completed' ? 'completed' : 'failed');
          if (finalJob.status === 'completed') {
            loadOntologies();
          }
        } catch (pollErr) {
          console.error('Polling failed:', pollErr);
          setIngestState('failed');
        }
      },
    });

    // Get initial job status
    try {
      const job = await apiClient.getJob(jobId);
      setCurrentJob(job);
      if (job.status === 'completed') {
        setIngestState('completed');
        cleanup();
      } else if (job.status === 'failed' || job.status === 'cancelled') {
        setIngestState('failed');
        cleanup();
      }
    } catch (err) {
      console.error('Failed to get initial job status:', err);
    }
  };

  // Render file info
  const renderFileInfo = () => {
    if (!selectedFile) return null;

    const isImage = isImageFile(selectedFile.name);
    const Icon = isImage ? Image : FileText;
    const sizeKB = (selectedFile.size / 1024).toFixed(1);

    return (
      <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
        <Icon className="w-8 h-8 text-blue-500 dark:text-blue-400" />
        <div className="flex-1 min-w-0">
          <div className="font-medium text-card-foreground dark:text-gray-200 truncate">
            {selectedFile.name}
          </div>
          <div className="text-sm text-muted-foreground dark:text-gray-400">
            {sizeKB} KB • {isImage ? 'Image' : 'Document'}
          </div>
        </div>
        <button
          onClick={clearFile}
          className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
          title="Remove file"
        >
          <X className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>
    );
  };

  // Can submit?
  const canSubmit = selectedFile && getOntologyName() && ingestState === 'idle';

  return (
    <div className="h-full flex flex-col bg-background dark:bg-gray-900">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-border dark:border-gray-700">
        <div className="flex items-center gap-3">
          <Upload className="w-6 h-6 text-blue-500" />
          <div>
            <h1 className="text-xl font-semibold text-card-foreground dark:text-gray-100">
              Ingest Documents
            </h1>
            <p className="text-sm text-muted-foreground dark:text-gray-400">
              Upload documents for knowledge extraction
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">

          {/* Drop Zone */}
          {!selectedFile && ingestState === 'idle' && (
            <div
              className={`
                relative border-2 border-dashed rounded-xl p-8 text-center transition-colors
                ${dragActive
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                  : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                }
              `}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                type="file"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={handleFileSelect}
                accept=".txt,.md,.rst,.pdf,.png,.jpg,.jpeg,.gif,.webp,.bmp"
              />
              <FolderOpen className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-4" />
              <p className="text-lg font-medium text-card-foreground dark:text-gray-200 mb-2">
                Drop file here or click to browse
              </p>
              <p className="text-sm text-muted-foreground dark:text-gray-400">
                Supports text (.txt, .md, .rst, .pdf) and images (.png, .jpg, .gif, .webp)
              </p>
              <p className="text-xs text-muted-foreground dark:text-gray-500 mt-2">
                Max {MAX_FILE_SIZE_MB}MB
              </p>
            </div>
          )}

          {/* File Error */}
          {fileError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{fileError}</span>
            </div>
          )}

          {/* Selected File */}
          {selectedFile && renderFileInfo()}

          {/* Duplicate Warning */}
          {duplicateInfo && (
            <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-amber-800 dark:text-amber-200">
                    Duplicate Detected
                  </p>
                  <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                    {duplicateInfo.message}
                  </p>
                  <p className="text-sm text-amber-600 dark:text-amber-400 mt-2">
                    Job ID: <code className="bg-amber-100 dark:bg-amber-900/50 px-1 rounded">{duplicateInfo.jobId}</code>
                  </p>
                  <button
                    onClick={() => setForce(true)}
                    className="mt-3 text-sm font-medium text-amber-700 dark:text-amber-300 hover:underline"
                  >
                    Force re-ingest anyway →
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Ontology Selector */}
          {selectedFile && ingestState === 'idle' && (
            <div className="space-y-3">
              <label className="block text-sm font-medium text-card-foreground dark:text-gray-200">
                Target Ontology
              </label>

              {!showNewOntology ? (
                <div className="flex gap-2">
                  <div className="flex-1 relative">
                    <select
                      value={selectedOntology}
                      onChange={(e) => setSelectedOntology(e.target.value)}
                      className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-card-foreground dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      disabled={loadingOntologies}
                    >
                      {loadingOntologies ? (
                        <option>Loading...</option>
                      ) : ontologies.length === 0 ? (
                        <option value="">No ontologies - create new</option>
                      ) : (
                        ontologies.map((ont) => (
                          <option key={ont.ontology} value={ont.ontology}>
                            {ont.ontology} ({ont.concept_count} concepts)
                          </option>
                        ))
                      )}
                    </select>
                  </div>
                  <button
                    onClick={() => setShowNewOntology(true)}
                    className="px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg text-card-foreground dark:text-gray-200 transition-colors"
                    title="Create new ontology"
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                  <button
                    onClick={loadOntologies}
                    className="px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg text-card-foreground dark:text-gray-200 transition-colors"
                    title="Refresh ontologies"
                    disabled={loadingOntologies}
                  >
                    <RefreshCw className={`w-5 h-5 ${loadingOntologies ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newOntologyName}
                    onChange={(e) => setNewOntologyName(e.target.value)}
                    placeholder="New ontology name"
                    className="flex-1 px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-card-foreground dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    autoFocus
                  />
                  <button
                    onClick={() => {
                      setShowNewOntology(false);
                      setNewOntologyName('');
                    }}
                    className="px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg text-card-foreground dark:text-gray-200 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Options */}
          {selectedFile && ingestState === 'idle' && (
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
              <button
                onClick={() => setShowOptions(!showOptions)}
                className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Settings className="w-4 h-4 text-muted-foreground" />
                  <span className="font-medium text-card-foreground dark:text-gray-200">
                    Advanced Options
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
                  {/* Chunking options */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-muted-foreground dark:text-gray-400 mb-1">
                        Target words per chunk
                      </label>
                      <input
                        type="number"
                        value={targetWords}
                        onChange={(e) => setTargetWords(Number(e.target.value))}
                        min={500}
                        max={2000}
                        className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded text-card-foreground dark:text-gray-200"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-muted-foreground dark:text-gray-400 mb-1">
                        Overlap words
                      </label>
                      <input
                        type="number"
                        value={overlapWords}
                        onChange={(e) => setOverlapWords(Number(e.target.value))}
                        min={0}
                        max={500}
                        className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded text-card-foreground dark:text-gray-200"
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
                          name="processingMode"
                          checked={processingMode === 'serial'}
                          onChange={() => setProcessingMode('serial')}
                          className="text-blue-500"
                        />
                        <span className="text-sm text-card-foreground dark:text-gray-200">
                          Serial (better quality)
                        </span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          name="processingMode"
                          checked={processingMode === 'parallel'}
                          onChange={() => setProcessingMode('parallel')}
                          className="text-blue-500"
                        />
                        <span className="text-sm text-card-foreground dark:text-gray-200">
                          Parallel (faster)
                        </span>
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
                      <span className="text-sm text-card-foreground dark:text-gray-200">
                        Auto-approve (start immediately)
                      </span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={force}
                        onChange={(e) => setForce(e.target.checked)}
                        className="rounded text-blue-500"
                      />
                      <span className="text-sm text-card-foreground dark:text-gray-200">
                        Force re-ingest (bypass duplicate detection)
                      </span>
                    </label>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Submit Button */}
          {selectedFile && ingestState === 'idle' && (
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
              Start Ingestion
            </button>
          )}

          {/* Submit Error */}
          {submitError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          {/* Progress */}
          {(ingestState === 'uploading' || ingestState === 'submitted' || ingestState === 'processing') && (
            <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <div className="flex items-center gap-3 mb-4">
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                <span className="font-medium text-blue-800 dark:text-blue-200">
                  {ingestState === 'uploading' && 'Uploading...'}
                  {ingestState === 'submitted' && 'Job submitted, waiting for processing...'}
                  {ingestState === 'processing' && 'Processing...'}
                </span>
              </div>

              {currentJob && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={currentJob.status} size="sm" />
                    {currentJob.job_id && (
                      <span className="text-xs text-muted-foreground dark:text-gray-400 font-mono">
                        {currentJob.job_id.substring(0, 12)}...
                      </span>
                    )}
                  </div>

                  {currentJob.progress && (
                    <ProgressIndicator progress={currentJob.progress} variant="bar" />
                  )}

                  {currentJob.analysis && (
                    <CostDisplay estimate={currentJob.analysis.cost_estimate} compact />
                  )}
                </div>
              )}
            </div>
          )}

          {/* Completed */}
          {ingestState === 'completed' && currentJob && (
            <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
              <div className="flex items-center gap-3 mb-4">
                <CheckCircle2 className="w-5 h-5 text-green-500" />
                <span className="font-medium text-green-800 dark:text-green-200">
                  Ingestion Complete!
                </span>
              </div>

              {currentJob.result && (
                <div className="space-y-3">
                  {currentJob.result.stats && (
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="text-muted-foreground dark:text-gray-400">Concepts created:</div>
                      <div className="text-card-foreground dark:text-gray-200">{currentJob.result.stats.concepts_created}</div>
                      <div className="text-muted-foreground dark:text-gray-400">Relationships:</div>
                      <div className="text-card-foreground dark:text-gray-200">{currentJob.result.stats.relationships_created}</div>
                      <div className="text-muted-foreground dark:text-gray-400">Chunks processed:</div>
                      <div className="text-card-foreground dark:text-gray-200">{currentJob.result.stats.chunks_processed}</div>
                    </div>
                  )}

                  {currentJob.result.cost && (
                    <CostDisplay actual={currentJob.result.cost} compact />
                  )}
                </div>
              )}

              <button
                onClick={clearFile}
                className="mt-4 w-full px-4 py-2 bg-green-100 dark:bg-green-900/30 hover:bg-green-200 dark:hover:bg-green-900/50 text-green-700 dark:text-green-300 rounded-lg font-medium transition-colors"
              >
                Ingest Another Document
              </button>
            </div>
          )}

          {/* Failed */}
          {ingestState === 'failed' && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <div className="flex items-center gap-3 mb-2">
                <AlertCircle className="w-5 h-5 text-red-500" />
                <span className="font-medium text-red-800 dark:text-red-200">
                  Ingestion Failed
                </span>
              </div>
              {currentJob?.error && (
                <p className="text-sm text-red-700 dark:text-red-300 mt-2">
                  {currentJob.error}
                </p>
              )}
              <button
                onClick={clearFile}
                className="mt-4 w-full px-4 py-2 bg-red-100 dark:bg-red-900/30 hover:bg-red-200 dark:hover:bg-red-900/50 text-red-700 dark:text-red-300 rounded-lg font-medium transition-colors"
              >
                Try Again
              </button>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};
