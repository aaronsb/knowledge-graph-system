/**
 * Artifact Store - Zustand State Management (ADR-083)
 *
 * Manages artifact metadata for persistent storage of computed results.
 * Payloads are cached separately in localStorage with LRU eviction.
 *
 * Key design decisions:
 * - Store holds metadata only (not payloads) to keep memory footprint small
 * - Payloads fetched on-demand and cached in localStorage
 * - Freshness tracked via graph_epoch comparison
 * - Automatic stale detection when graph changes
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiClient } from '../api/client';
import type {
  ArtifactMetadata,
  ArtifactWithPayload,
  ArtifactCreateRequest,
  ArtifactType,
  Representation,
} from '../types/artifacts';

// Cache configuration
const PAYLOAD_CACHE_KEY = 'kg-artifact-payloads';
const MAX_CACHE_SIZE_BYTES = 50 * 1024 * 1024; // 50MB limit

/**
 * Cached payload entry with LRU tracking
 */
interface CachedPayload {
  artifact_id: number;
  graph_epoch: number;
  payload: Record<string, unknown>;
  cached_at: number;
  size_bytes: number;
}

/**
 * Artifact store state
 */
interface ArtifactStoreState {
  // Artifact metadata (keyed by ID for O(1) lookup)
  artifacts: Record<number, ArtifactMetadata>;

  // List of artifact IDs in display order (most recent first)
  artifactIds: number[];

  // Loading state
  isLoading: boolean;
  error: string | null;

  // Current graph epoch (for freshness comparison)
  currentGraphEpoch: number | null;

  // Last fetch timestamp
  lastFetchedAt: string | null;

  // Pagination info
  total: number;
  hasMore: boolean;
}

interface ArtifactStoreActions {
  // Load artifacts from API
  loadArtifacts: (params?: {
    artifact_type?: ArtifactType;
    representation?: Representation;
    ontology?: string;
    refresh?: boolean;
    limit?: number;
    offset?: number;
  }) => Promise<void>;

  // Create and persist a new artifact
  persistArtifact: (artifact: ArtifactCreateRequest) => Promise<ArtifactMetadata | null>;

  // Delete an artifact
  deleteArtifact: (artifactId: number) => Promise<boolean>;

  // Regenerate an artifact
  regenerateArtifact: (artifactId: number) => Promise<string | null>;

  // Get artifact payload (with localStorage caching)
  fetchArtifactPayload: (artifactId: number) => Promise<Record<string, unknown> | null>;

  // Check if an artifact is fresh
  isArtifactFresh: (artifactId: number) => boolean;

  // Update current graph epoch
  setGraphEpoch: (epoch: number) => void;

  // Mark specific artifact as stale
  markStale: (artifactId: number) => void;

  // Get artifact by ID
  getArtifact: (artifactId: number) => ArtifactMetadata | null;

  // Clear all artifacts (local state only)
  clearArtifacts: () => void;

  // Clear error state
  clearError: () => void;
}

type ArtifactStore = ArtifactStoreState & ArtifactStoreActions;

// ============================================================
// LOCALSTORAGE PAYLOAD CACHE (LRU)
// ============================================================

/**
 * Get cached payloads from localStorage
 */
function getPayloadCache(): Map<number, CachedPayload> {
  try {
    const raw = localStorage.getItem(PAYLOAD_CACHE_KEY);
    if (!raw) return new Map();
    const entries: [number, CachedPayload][] = JSON.parse(raw);
    return new Map(entries);
  } catch {
    return new Map();
  }
}

/**
 * Save payload cache to localStorage
 */
function savePayloadCache(cache: Map<number, CachedPayload>): void {
  try {
    const entries = Array.from(cache.entries());
    localStorage.setItem(PAYLOAD_CACHE_KEY, JSON.stringify(entries));
  } catch (e) {
    console.warn('Failed to save payload cache:', e);
  }
}

/**
 * Calculate approximate size of payload in bytes
 */
function estimateSize(payload: Record<string, unknown>): number {
  return new Blob([JSON.stringify(payload)]).size;
}

/**
 * Get current cache size in bytes
 */
function getCacheSize(cache: Map<number, CachedPayload>): number {
  let size = 0;
  for (const entry of cache.values()) {
    size += entry.size_bytes;
  }
  return size;
}

/**
 * Evict oldest entries until under size limit
 */
function evictLRU(cache: Map<number, CachedPayload>, targetBytes: number): void {
  // Sort entries by cached_at (oldest first)
  const entries = Array.from(cache.entries()).sort(
    (a, b) => a[1].cached_at - b[1].cached_at
  );

  let currentSize = getCacheSize(cache);

  for (const [id] of entries) {
    if (currentSize <= targetBytes) break;
    const entry = cache.get(id);
    if (entry) {
      currentSize -= entry.size_bytes;
      cache.delete(id);
    }
  }
}

/**
 * Cache a payload with LRU eviction
 */
function cachePayload(
  artifactId: number,
  graphEpoch: number,
  payload: Record<string, unknown>
): void {
  const cache = getPayloadCache();
  const sizeBytes = estimateSize(payload);

  // Check if we need to evict
  const currentSize = getCacheSize(cache);
  const newTotalSize = currentSize + sizeBytes;

  if (newTotalSize > MAX_CACHE_SIZE_BYTES) {
    // Evict until we have room (with 10% buffer)
    evictLRU(cache, MAX_CACHE_SIZE_BYTES * 0.9 - sizeBytes);
  }

  // Add new entry
  cache.set(artifactId, {
    artifact_id: artifactId,
    graph_epoch: graphEpoch,
    payload,
    cached_at: Date.now(),
    size_bytes: sizeBytes,
  });

  savePayloadCache(cache);
}

/**
 * Get cached payload if valid (not stale)
 */
function getCachedPayload(
  artifactId: number,
  currentEpoch: number | null
): Record<string, unknown> | null {
  const cache = getPayloadCache();
  const entry = cache.get(artifactId);

  if (!entry) return null;

  // Check freshness - if current epoch is known and cached epoch matches
  if (currentEpoch !== null && entry.graph_epoch !== currentEpoch) {
    // Stale cache entry - remove it
    cache.delete(artifactId);
    savePayloadCache(cache);
    return null;
  }

  // Update access time for LRU
  entry.cached_at = Date.now();
  cache.set(artifactId, entry);
  savePayloadCache(cache);

  return entry.payload;
}

/**
 * Remove a payload from cache
 */
function removeCachedPayload(artifactId: number): void {
  const cache = getPayloadCache();
  cache.delete(artifactId);
  savePayloadCache(cache);
}

// ============================================================
// ZUSTAND STORE
// ============================================================

export const useArtifactStore = create<ArtifactStore>()(
  persist(
    (set, get) => ({
      // Initial state
      artifacts: {},
      artifactIds: [],
      isLoading: false,
      error: null,
      currentGraphEpoch: null,
      lastFetchedAt: null,
      total: 0,
      hasMore: false,

      // Load artifacts from API
      loadArtifacts: async (params) => {
        const { refresh = false, limit = 50, offset = 0, ...filters } = params || {};

        set({ isLoading: true, error: null });

        try {
          const response = await apiClient.listArtifacts({
            ...filters,
            limit,
            offset,
          });

          // Extract current epoch from first artifact if available
          let currentEpoch = get().currentGraphEpoch;
          if (response.artifacts.length > 0 && response.artifacts[0].is_fresh) {
            currentEpoch = response.artifacts[0].graph_epoch;
          }

          // Build artifacts map
          const newArtifacts: Record<number, ArtifactMetadata> = {};
          const newIds: number[] = [];

          for (const artifact of response.artifacts) {
            newArtifacts[artifact.id] = artifact;
            newIds.push(artifact.id);
          }

          if (refresh || offset === 0) {
            // Replace artifacts
            set({
              artifacts: newArtifacts,
              artifactIds: newIds,
              total: response.total,
              hasMore: offset + response.artifacts.length < response.total,
              currentGraphEpoch: currentEpoch,
              lastFetchedAt: new Date().toISOString(),
              isLoading: false,
            });
          } else {
            // Append for pagination
            const existing = get().artifacts;
            const existingIds = get().artifactIds;
            set({
              artifacts: { ...existing, ...newArtifacts },
              artifactIds: [...existingIds, ...newIds],
              total: response.total,
              hasMore: offset + response.artifacts.length < response.total,
              isLoading: false,
            });
          }
        } catch (e: unknown) {
          const message = e instanceof Error ? e.message : 'Failed to load artifacts';
          set({ isLoading: false, error: message });
        }
      },

      // Create and persist artifact
      persistArtifact: async (artifact) => {
        set({ isLoading: true, error: null });

        try {
          const response = await apiClient.createArtifact(artifact);

          // Build metadata from response
          const metadata: ArtifactMetadata = {
            id: response.id,
            artifact_type: response.artifact_type,
            representation: response.representation,
            name: response.name,
            owner_id: null, // Will be current user
            graph_epoch: response.graph_epoch,
            is_fresh: true,
            created_at: response.created_at,
            expires_at: null,
            parameters: artifact.parameters,
            metadata: artifact.metadata || null,
            ontology: artifact.ontology || null,
            concept_ids: artifact.concept_ids || null,
            query_definition_id: artifact.query_definition_id || null,
            has_inline_result: response.storage_location === 'inline',
            garage_key: response.garage_key,
          };

          // Add to store (prepend to show newest first)
          const existing = get().artifacts;
          const existingIds = get().artifactIds;

          set({
            artifacts: { ...existing, [response.id]: metadata },
            artifactIds: [response.id, ...existingIds],
            total: get().total + 1,
            currentGraphEpoch: response.graph_epoch,
            isLoading: false,
          });

          // Cache the payload
          cachePayload(response.id, response.graph_epoch, artifact.payload);

          return metadata;
        } catch (e: unknown) {
          const message = e instanceof Error ? e.message : 'Failed to persist artifact';
          set({ isLoading: false, error: message });
          return null;
        }
      },

      // Delete artifact
      deleteArtifact: async (artifactId) => {
        try {
          await apiClient.deleteArtifact(artifactId);

          // Remove from store
          const { [artifactId]: _, ...remaining } = get().artifacts;
          const filteredIds = get().artifactIds.filter((id) => id !== artifactId);

          set({
            artifacts: remaining,
            artifactIds: filteredIds,
            total: get().total - 1,
          });

          // Remove from cache
          removeCachedPayload(artifactId);

          return true;
        } catch (e) {
          console.error('Failed to delete artifact:', e);
          return false;
        }
      },

      // Regenerate artifact
      regenerateArtifact: async (artifactId) => {
        try {
          const response = await apiClient.regenerateArtifact(artifactId);
          return response.job_id;
        } catch (e) {
          console.error('Failed to regenerate artifact:', e);
          return null;
        }
      },

      // Fetch payload with caching
      fetchArtifactPayload: async (artifactId) => {
        const currentEpoch = get().currentGraphEpoch;

        // Check cache first
        const cached = getCachedPayload(artifactId, currentEpoch);
        if (cached) {
          return cached;
        }

        // Fetch from API
        try {
          const response = await apiClient.getArtifactPayload(artifactId);

          // Update artifact metadata in store
          const existing = get().artifacts[artifactId];
          if (existing) {
            set({
              artifacts: {
                ...get().artifacts,
                [artifactId]: {
                  ...existing,
                  is_fresh: response.is_fresh,
                },
              },
            });
          }

          // Cache the payload
          cachePayload(artifactId, response.graph_epoch, response.payload);

          return response.payload;
        } catch (e) {
          console.error('Failed to fetch artifact payload:', e);
          return null;
        }
      },

      // Check freshness
      isArtifactFresh: (artifactId) => {
        const artifact = get().artifacts[artifactId];
        if (!artifact) return false;

        const currentEpoch = get().currentGraphEpoch;
        if (currentEpoch === null) return artifact.is_fresh;

        return artifact.graph_epoch === currentEpoch;
      },

      // Set graph epoch
      setGraphEpoch: (epoch) => {
        const current = get().currentGraphEpoch;
        if (current !== epoch) {
          // Mark all artifacts with different epoch as stale
          const artifacts = get().artifacts;
          const updated: Record<number, ArtifactMetadata> = {};

          for (const [id, artifact] of Object.entries(artifacts)) {
            updated[parseInt(id)] = {
              ...artifact,
              is_fresh: artifact.graph_epoch === epoch,
            };
          }

          set({
            artifacts: updated,
            currentGraphEpoch: epoch,
          });
        }
      },

      // Mark specific artifact stale
      markStale: (artifactId) => {
        const artifact = get().artifacts[artifactId];
        if (artifact) {
          set({
            artifacts: {
              ...get().artifacts,
              [artifactId]: { ...artifact, is_fresh: false },
            },
          });

          // Remove from cache
          removeCachedPayload(artifactId);
        }
      },

      // Get artifact by ID
      getArtifact: (artifactId) => {
        return get().artifacts[artifactId] || null;
      },

      // Clear all artifacts (local state only)
      clearArtifacts: () => {
        set({
          artifacts: {},
          artifactIds: [],
          total: 0,
          hasMore: false,
          lastFetchedAt: null,
        });
      },

      // Clear error
      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'kg-artifacts-storage',
      // Only persist metadata, not loading state
      partialize: (state) => ({
        artifacts: state.artifacts,
        artifactIds: state.artifactIds,
        currentGraphEpoch: state.currentGraphEpoch,
        lastFetchedAt: state.lastFetchedAt,
        total: state.total,
      }),
    }
  )
);
