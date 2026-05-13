/**
 * useExplorationActions — ledger invariants
 *
 * The hub is the single writer for graph-mutating actions. The tests below
 * pin its contract: exactly one step per call, the `clean` rule resets the
 * session, depth defaults are honored, and subtractive operations get the
 * `-` operator. They run against the real Zustand store (no store mocking)
 * because the invariants ARE about how the store mutates — mocking the
 * store would tautologize the assertions.
 *
 * `apiClient` is mocked so the tests don't need a running API. We mock the
 * specific methods the hub touches; everything else stays as-is.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

import {
  useExplorationActions,
  FOLLOW_DEPTH,
  ADD_ADJACENT_DEFAULT_DEPTH,
} from './useExplorationActions';
import { useGraphStore } from '../store/graphStore';

// Mock the API client surface the hub touches.
vi.mock('../api/client', () => ({
  apiClient: {
    getSubgraph: vi.fn(async () => ({ nodes: [], links: [] })),
    executeProgram: vi.fn(async () => ({
      result: { vertices: [], relationships: [] },
    })),
  },
}));

// mapWorkingGraphToRawGraph operates on the WorkingGraph shape from
// executeProgram. The mock above returns an empty graph; map it to an
// empty raw graph for runCypher's merge step.
vi.mock('../utils/cypherResultMapper', async () => {
  const actual = await vi.importActual<
    typeof import('../utils/cypherResultMapper')
  >('../utils/cypherResultMapper');
  return {
    ...actual,
    mapWorkingGraphToRawGraph: vi.fn(() => ({ nodes: [], links: [] })),
  };
});

// QueryClientProvider wrapper — the hub uses `useQueryClient` even though
// the query client isn't actively consumed in the tested code paths yet.
function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

// Snapshot helpers — extract just what the assertions look at.
const stepCount = () =>
  useGraphStore.getState().explorationSession?.steps.length ?? 0;
const sessionId = () => useGraphStore.getState().explorationSession?.id;
const lastStep = () => {
  const s = useGraphStore.getState().explorationSession;
  return s?.steps[s.steps.length - 1];
};

beforeEach(() => {
  // Reset the exploration session to a clean state for each test. Using
  // the public action keeps us honest — if resetExplorationSession ever
  // changes behavior, tests recompose against the new semantics rather
  // than against an internal snapshot.
  useGraphStore.getState().resetExplorationSession();
  useGraphStore.getState().setRawGraphData(null);
});

describe('useExplorationActions — ledger invariants', () => {
  describe('loadExplore', () => {
    it("'clean' resets the session before recording the step", async () => {
      // Arrange: existing session with two prior steps.
      const store = useGraphStore.getState();
      store.addExplorationStep({
        action: 'explore',
        op: '+',
        cypher: 'MATCH ...',
        conceptId: 'old-a',
        conceptLabel: 'Old A',
        depth: 1,
      });
      store.addExplorationStep({
        action: 'explore',
        op: '+',
        cypher: 'MATCH ...',
        conceptId: 'old-b',
        conceptLabel: 'Old B',
        depth: 1,
      });
      expect(stepCount()).toBe(2);
      const beforeId = sessionId();

      const { result } = renderHook(() => useExplorationActions(), { wrapper });

      await act(async () => {
        await result.current.loadExplore({
          conceptId: 'new',
          conceptLabel: 'New',
          depth: 1,
          loadMode: 'clean',
        });
      });

      // 'clean' resets → new session id, exactly one step (the new one).
      expect(sessionId()).not.toBe(beforeId);
      expect(stepCount()).toBe(1);
      expect(lastStep()?.action).toBe('explore');
      expect(lastStep()?.conceptId).toBe('new');
    });

    it("'add' appends without resetting the session", async () => {
      const store = useGraphStore.getState();
      store.addExplorationStep({
        action: 'explore',
        op: '+',
        cypher: 'MATCH ...',
        conceptId: 'prior',
        conceptLabel: 'Prior',
        depth: 1,
      });
      const beforeId = sessionId();
      expect(stepCount()).toBe(1);

      const { result } = renderHook(() => useExplorationActions(), { wrapper });

      await act(async () => {
        await result.current.loadExplore({
          conceptId: 'appended',
          conceptLabel: 'Appended',
          depth: 2,
          loadMode: 'add',
        });
      });

      expect(sessionId()).toBe(beforeId);
      expect(stepCount()).toBe(2);
      expect(lastStep()?.conceptId).toBe('appended');
      expect(lastStep()?.depth).toBe(2);
    });
  });

  describe('followConcept', () => {
    it("records exactly one 'follow' step at FOLLOW_DEPTH", async () => {
      const { result } = renderHook(() => useExplorationActions(), { wrapper });

      await act(async () => {
        await result.current.followConcept('node-1');
      });

      expect(stepCount()).toBe(1);
      expect(lastStep()?.action).toBe('follow');
      expect(lastStep()?.op).toBe('+');
      expect(lastStep()?.depth).toBe(FOLLOW_DEPTH);
      expect(lastStep()?.conceptId).toBe('node-1');
    });
  });

  describe('addAdjacent', () => {
    it('defaults to ADD_ADJACENT_DEFAULT_DEPTH when no depth arg given', async () => {
      const { result } = renderHook(() => useExplorationActions(), { wrapper });

      await act(async () => {
        await result.current.addAdjacent('node-2');
      });

      expect(stepCount()).toBe(1);
      expect(lastStep()?.action).toBe('add-adjacent');
      expect(lastStep()?.depth).toBe(ADD_ADJACENT_DEFAULT_DEPTH);
    });

    it.each([1, 2, 3] as const)(
      'honors explicit depth %i from the context-menu selector',
      async (depth) => {
        const { result } = renderHook(() => useExplorationActions(), { wrapper });

        await act(async () => {
          await result.current.addAdjacent('node-3', { depth });
        });

        expect(lastStep()?.depth).toBe(depth);
      }
    );
  });

  describe('removeNode', () => {
    it("records a subtractive ('-') 'cypher' step", () => {
      const { result } = renderHook(() => useExplorationActions(), { wrapper });

      act(() => {
        result.current.removeNode('node-4');
      });

      expect(stepCount()).toBe(1);
      expect(lastStep()?.action).toBe('cypher');
      expect(lastStep()?.op).toBe('-');
      expect(lastStep()?.conceptId).toBe('node-4');
    });
  });

  describe('runCypher', () => {
    it('resets the session and records one step per statement', async () => {
      const store = useGraphStore.getState();
      store.addExplorationStep({
        action: 'explore',
        op: '+',
        cypher: 'MATCH (prior) ...',
        conceptId: 'prior',
        conceptLabel: 'Prior',
        depth: 1,
      });
      const beforeId = sessionId();
      expect(stepCount()).toBe(1);

      const { result } = renderHook(() => useExplorationActions(), { wrapper });

      const statements = [
        { op: '+' as const, cypher: 'MATCH (a) RETURN a' },
        { op: '+' as const, cypher: 'MATCH (b) RETURN b' },
        { op: '-' as const, cypher: 'MATCH (c) RETURN c' },
      ];

      await act(async () => {
        await result.current.runCypher(statements);
      });

      // runCypher resets the session and records one step per stmt.
      expect(sessionId()).not.toBe(beforeId);
      expect(stepCount()).toBe(3);

      const session = useGraphStore.getState().explorationSession;
      expect(session?.steps.map((s) => s.op)).toEqual(['+', '+', '-']);
      expect(session?.steps.every((s) => s.action === 'cypher')).toBe(true);
    });

    it('is a no-op on an empty statement list', async () => {
      const store = useGraphStore.getState();
      store.addExplorationStep({
        action: 'explore',
        op: '+',
        cypher: 'MATCH (kept) ...',
        conceptId: 'kept',
        conceptLabel: 'Kept',
        depth: 1,
      });
      const beforeId = sessionId();

      const { result } = renderHook(() => useExplorationActions(), { wrapper });

      await act(async () => {
        await result.current.runCypher([]);
      });

      // No reset, no new steps when given nothing to run.
      expect(sessionId()).toBe(beforeId);
      expect(stepCount()).toBe(1);
    });
  });
});
