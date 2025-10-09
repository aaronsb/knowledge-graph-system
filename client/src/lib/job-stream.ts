/**
 * Server-Sent Events (SSE) job progress streaming (ADR-018 Phase 1)
 *
 * Provides real-time job progress updates via EventSource API.
 * Gracefully falls back to polling if SSE fails.
 */

import type { JobProgress, JobResult } from '../types';

// Dynamic import of eventsource for Node.js
// Use require() to get the default export correctly
const EventSource = require('eventsource');

export interface JobProgressCallbacks {
  onProgress?: (progress: JobProgress) => void;
  onCompleted?: (result: JobResult) => void;
  onFailed?: (error: string) => void;
  onCancelled?: (message: string) => void;
  onError?: (error: Error) => void;
}

export class JobProgressStream {
  private eventSource: any = null;
  private closed = false;

  constructor(
    private baseUrl: string,
    private jobId: string,
    private callbacks: JobProgressCallbacks
  ) {}

  /**
   * Start streaming job progress events.
   *
   * Opens SSE connection to /jobs/{job_id}/stream endpoint.
   * Auto-closes on terminal events (completed/failed/cancelled).
   */
  start(): void {
    if (this.eventSource) {
      throw new Error('Stream already started');
    }

    const url = `${this.baseUrl}/jobs/${this.jobId}/stream`;
    this.eventSource = new EventSource(url);

    // Progress event: Job state changed
    this.eventSource.addEventListener('progress', (event: any) => {
      try {
        const progress = JSON.parse(event.data);
        this.callbacks.onProgress?.(progress);
      } catch (error) {
        console.error('Failed to parse progress event:', error);
      }
    });

    // Completed event: Job finished successfully
    this.eventSource.addEventListener('completed', (event: any) => {
      try {
        const result = JSON.parse(event.data);
        this.callbacks.onCompleted?.(result);
        this.close();
      } catch (error) {
        console.error('Failed to parse completed event:', error);
      }
    });

    // Failed event: Job failed with error
    this.eventSource.addEventListener('failed', (event: any) => {
      try {
        const data = JSON.parse(event.data);
        this.callbacks.onFailed?.(data.error);
        this.close();
      } catch (error) {
        console.error('Failed to parse failed event:', error);
      }
    });

    // Cancelled event: Job was cancelled
    this.eventSource.addEventListener('cancelled', (event: any) => {
      try {
        const data = JSON.parse(event.data);
        this.callbacks.onCancelled?.(data.message);
        this.close();
      } catch (error) {
        console.error('Failed to parse cancelled event:', error);
      }
    });

    // Error event: Job not found or connection error
    this.eventSource.addEventListener('error', (event: any) => {
      try {
        // Check if error contains data (job not found)
        if (event.data) {
          const data = JSON.parse(event.data);
          this.callbacks.onError?.(new Error(data.error));
          this.close();
        } else {
          // Connection error - EventSource will auto-reconnect
          // Only call onError if we haven't closed explicitly
          if (!this.closed) {
            this.callbacks.onError?.(new Error('Connection error - retrying...'));
          }
        }
      } catch (error) {
        console.error('Error event:', error);
      }
    });

    // Keepalive events (no action needed, just keep connection alive)
    this.eventSource.addEventListener('keepalive', () => {
      // No-op: Just prevents timeout
    });
  }

  /**
   * Close the SSE connection.
   *
   * Safe to call multiple times.
   */
  close(): void {
    if (this.eventSource && !this.closed) {
      this.eventSource.close();
      this.eventSource = null;
      this.closed = true;
    }
  }

  /**
   * Check if stream is currently active.
   */
  isActive(): boolean {
    return this.eventSource !== null && !this.closed;
  }
}

/**
 * Track job progress with automatic SSE fallback to polling.
 *
 * Tries SSE first for real-time updates. If SSE fails or is unavailable,
 * gracefully falls back to polling-based tracking.
 *
 * @param baseUrl - API base URL (e.g., http://localhost:8000)
 * @param jobId - Job ID to track
 * @param callbacks - Progress callbacks
 * @param useSSE - Whether to try SSE (default: true)
 * @returns JobProgressStream instance or null if using polling
 */
export async function trackJobProgress(
  baseUrl: string,
  jobId: string,
  callbacks: JobProgressCallbacks,
  useSSE: boolean = true
): Promise<JobProgressStream | null> {
  if (!useSSE) {
    // Explicitly disabled - use polling fallback
    return null;
  }

  try {
    // Try SSE first
    const stream = new JobProgressStream(baseUrl, jobId, callbacks);
    stream.start();
    return stream;
  } catch (error) {
    // SSE failed - fall back to polling
    console.warn('SSE streaming unavailable, falling back to polling:', error);
    return null;
  }
}
