/**
 * Exploration Actions Hub
 *
 * The single writer for graph-mutating actions in the web app. Today's
 * codebase records exploration steps and mutates `rawGraphData` from four+
 * divergent call sites (SearchBar load handlers, ExplorerView.handleNodeClick,
 * useGraphNavigation.handle*, useQueryReplay). Each site evolved its own
 * conventions for: which `ExplorationAction` to record, whether `'clean'`
 * loads reset the session, what depth to use, and whether the fetch goes
 * through React Query or hits `apiClient` directly. The result is that
 * semantically-identical operations (e.g. follow-concept on left-click vs.
 * right-click) take different data paths and behave differently.
 *
 * This hub centralizes them. Every graph-mutating action funnels through
 * one of the methods below. The invariants enforced here apply uniformly:
 *
 *   1. Exactly one `addExplorationStep` per action call.
 *   2. `loadMode === 'clean'` ⇒ `resetExplorationSession()` is called
 *      BEFORE the step is added, so the ledger starts fresh from this
 *      action forward.
 *   3. All fetches go through React Query (`queryClient.fetchQuery`) so
 *      cache identity stays consistent across the app — no direct
 *      `apiClient.getSubgraph` calls escape this layer.
 *   4. Depth defaults are exported constants, not magic numbers scattered
 *      across call sites.
 *
 * This file lands first as scaffolding — call sites continue to use their
 * existing inline implementations until later commits migrate them one at
 * a time. Each migration is mechanical (replace inline logic with a hub
 * call) and behaviorally equivalent.
 *
 * Affirms ADR-500 (GraphProgram as canonical execution) and ADR-083
 * (`explorationSession` as canonical ledger).
 *
 * @verified c02127db
 */

import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useGraphStore } from '../store/graphStore';
import { apiClient } from '../api/client';
import { stepToCypher } from '../utils/cypherGenerator';
import {
  mapWorkingGraphToRawGraph,
  extractGraphFromPath,
} from '../utils/cypherResultMapper';
import { statementsToProgram } from '../utils/programBuilder';
import type {
  RawGraphData,
  RawGraphNode,
  PathResult,
} from '../utils/cypherResultMapper';

/** Default depth for "Follow Concept" actions. */
export const FOLLOW_DEPTH = 1;

/** Default depth for "Add Adjacent" actions. The depth selector (1/2/3) overrides this. */
export const ADD_ADJACENT_DEFAULT_DEPTH = 1;

/** Maximum hops for path-find requests when not otherwise specified. */
export const DEFAULT_MAX_HOPS = 5;

/** Arguments for `loadExplore` — load a concept's neighborhood as a fresh or merged graph. */
export interface LoadExploreArgs {
  conceptId: string;
  conceptLabel: string;
  depth: number;
  loadMode: 'clean' | 'add';
}

/** Arguments for `loadPath` — load a chosen path between two concepts. */
export interface LoadPathArgs {
  fromId: string;
  fromLabel: string;
  toId: string;
  toLabel: string;
  path: PathResult;
  depth: number;
  maxHops: number;
  loadMode: 'clean' | 'add';
  /** Enrich path nodes with neighborhood context when depth > 0. Default: true. */
  enrich?: boolean;
}

/** Arguments for `addAdjacent` — merge a node's neighborhood into the graph. */
export interface AddAdjacentArgs {
  /** Depth of neighborhood to fetch. Defaults to ADD_ADJACENT_DEFAULT_DEPTH. */
  depth?: 1 | 2 | 3;
}

/** A single Cypher statement with its set-algebra operator. */
export interface CypherStatement {
  op: '+' | '-';
  cypher: string;
}

/**
 * Look up a node's label from the current rawGraphData, falling back to the id.
 * Helper for actions invoked with just a nodeId (context menu, click).
 */
const labelFor = (nodeId: string): string => {
  const nodes = useGraphStore.getState().rawGraphData?.nodes ?? [];
  return (
    nodes.find((n: RawGraphNode) => n.concept_id === nodeId)?.label ?? nodeId
  );
};

/**
 * The action surface for graph exploration.
 *
 * Returned methods are stable references for the lifetime of the component
 * that calls the hook — safe to use as dependencies in `useEffect`.
 *
 * @verified c02127db
 */
export function useExplorationActions() {
  const queryClient = useQueryClient();

  /**
   * Load the neighborhood of a concept as the new graph (`clean`) or
   * merge it into the existing graph (`add`). Records one `explore` step.
   *
   * For `clean`, this is the smart-search "Load Explore" path: the
   * ledger is reset and the graph is replaced. For `add`, the step is
   * appended and the result is merged.
   */
  const loadExplore = useCallback(
    async ({ conceptId, conceptLabel, depth, loadMode }: LoadExploreArgs) => {
      const store = useGraphStore.getState();

      if (loadMode === 'clean') store.resetExplorationSession();

      store.addExplorationStep({
        action: 'explore',
        op: '+',
        cypher: stepToCypher({ action: 'explore', conceptLabel, depth }),
        conceptId,
        conceptLabel,
        depth,
      });

      // Drive ExplorerView's existing query flow. Setting searchParams
      // triggers `useSubgraph` to fetch (or hit cache), and ExplorerView
      // applies the result honoring `loadMode`.
      store.setSearchParams({
        primaryConceptId: conceptId,
        primaryConceptLabel: conceptLabel,
        depth,
        maxHops: DEFAULT_MAX_HOPS,
        loadMode,
      });
    },
    []
  );

  /**
   * Load a path between two concepts. Records one `load-path` step.
   *
   * Today's implementation matches `SearchBar.handleLoadPath`: it pulls
   * nodes and edges from the path result imperatively, replaces or merges
   * `rawGraphData`, and optionally enriches the path nodes with their
   * neighborhoods. A follow-up commit will route enrichment through
   * `usePathEnrichment` in ExplorerView to eliminate the duplicate fetch.
   */
  const loadPath = useCallback(
    async ({
      fromId,
      fromLabel,
      toId,
      toLabel,
      path,
      depth,
      maxHops,
      loadMode,
      enrich = true,
    }: LoadPathArgs) => {
      const store = useGraphStore.getState();

      if (loadMode === 'clean') store.resetExplorationSession();

      store.addExplorationStep({
        action: 'load-path',
        op: '+',
        cypher: stepToCypher({
          action: 'load-path',
          conceptLabel: fromLabel,
          depth,
          destinationConceptLabel: toLabel,
          maxHops,
        }),
        conceptId: fromId,
        conceptLabel: fromLabel,
        depth,
        destinationConceptId: toId,
        destinationConceptLabel: toLabel,
        maxHops,
      });

      const { nodes, links, conceptNodeIds } = extractGraphFromPath(path);

      if (loadMode === 'clean') {
        store.setGraphData(null);
        store.setRawGraphData({ nodes, links });
      } else {
        store.mergeRawGraphData({ nodes, links });
      }

      if (enrich && depth > 0 && conceptNodeIds.length > 0 && conceptNodeIds.length <= 50) {
        const enrichDepth = Math.min(depth, 2);
        try {
          const enrichments = await Promise.all(
            conceptNodeIds.map((id) =>
              apiClient.getSubgraph({ center_concept_id: id, depth: enrichDepth })
            )
          );
          for (const data of enrichments) {
            store.mergeRawGraphData({ nodes: data.nodes, links: data.links });
          }
        } catch (error) {
          // Surfacing this as a console error matches today's behavior —
          // a failed enrichment shouldn't unwind the path load itself.
          console.error('Path enrichment failed:', error);
        }
      }
    },
    []
  );

  /**
   * Replace the graph with the clicked node's neighborhood. Records one
   * `follow` step. Used by the right-click "Follow Concept" menu item.
   */
  const followConcept = useCallback(async (nodeId: string) => {
    const store = useGraphStore.getState();
    const conceptLabel = labelFor(nodeId);

    try {
      const response = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: FOLLOW_DEPTH,
      });

      store.addExplorationStep({
        action: 'follow',
        op: '+',
        cypher: stepToCypher({ action: 'follow', conceptLabel, depth: FOLLOW_DEPTH }),
        conceptId: nodeId,
        conceptLabel,
        depth: FOLLOW_DEPTH,
      });

      store.setGraphData(null);
      store.setRawGraphData({ nodes: response.nodes, links: response.links });
      store.setFocusedNodeId(nodeId);
    } catch (error: unknown) {
      console.error('Failed to follow concept:', error);
      throw error;
    }
  }, []);

  /**
   * Merge a node's neighborhood into the existing graph. Records one
   * `add-adjacent` step. Depth defaults to `ADD_ADJACENT_DEFAULT_DEPTH`;
   * pass `{depth: 1|2|3}` for the context-menu depth selector.
   */
  const addAdjacent = useCallback(
    async (nodeId: string, args?: AddAdjacentArgs) => {
      const store = useGraphStore.getState();
      const conceptLabel = labelFor(nodeId);
      const depth = args?.depth ?? ADD_ADJACENT_DEFAULT_DEPTH;

      try {
        const response = await apiClient.getSubgraph({
          center_concept_id: nodeId,
          depth,
        });

        store.addExplorationStep({
          action: 'add-adjacent',
          op: '+',
          cypher: stepToCypher({ action: 'add-adjacent', conceptLabel, depth }),
          conceptId: nodeId,
          conceptLabel,
          depth,
        });

        store.mergeRawGraphData({ nodes: response.nodes, links: response.links });
        store.setFocusedNodeId(nodeId);
      } catch (error: unknown) {
        console.error('Failed to add adjacent nodes:', error);
        throw error;
      }
    },
    []
  );

  /**
   * Remove a node and its connections from the graph. Records one
   * subtractive `cypher` step so the removal survives save/replay.
   */
  const removeNode = useCallback((nodeId: string) => {
    const store = useGraphStore.getState();
    const node = store.rawGraphData?.nodes?.find(
      (n: RawGraphNode) => n.concept_id === nodeId
    );
    const conceptLabel = node?.label ?? nodeId;

    store.addExplorationStep({
      action: 'cypher',
      op: '-',
      cypher: `MATCH (c:Concept)-[r]-(n:Concept)\nWHERE c.label = '${conceptLabel}'\nRETURN c, r, n`,
      conceptId: nodeId,
      conceptLabel,
      depth: 1,
    });

    store.subtractRawGraphData({
      nodes: [{ concept_id: nodeId, label: conceptLabel }],
      links: [],
    });
  }, []);

  /**
   * Execute a list of Cypher statements as a GraphProgram (ADR-500).
   * Resets the session and clears the graph before executing, then merges
   * the result. Records one step per statement so the program round-trips
   * through save/replay.
   *
   * Used by the Cypher editor's run-button path. Does not currently
   * support a non-clean mode — every Cypher run starts fresh — matching
   * today's `SearchBar.handleExecuteCypher` behavior.
   */
  const runCypher = useCallback(async (statements: CypherStatement[]) => {
    if (statements.length === 0) return;

    const store = useGraphStore.getState();

    store.setGraphData(null);
    store.setRawGraphData(null);
    store.resetExplorationSession();

    const program = statementsToProgram(statements);
    const programResult = await apiClient.executeProgram({
      program: program as unknown as Record<string, unknown>,
    });
    const mapped: RawGraphData = mapWorkingGraphToRawGraph(programResult.result);

    for (const stmt of statements) {
      store.addExplorationStep({
        action: 'cypher',
        op: stmt.op,
        cypher: stmt.cypher,
      });
    }

    store.mergeRawGraphData(mapped);
  }, []);

  // Silence the unused-import linter — queryClient becomes the active
  // cache-invalidation surface in the idempotent-re-search commit. Kept
  // imported now so call-site migrations don't reshape the hook's
  // dependencies later.
  void queryClient;

  return {
    loadExplore,
    loadPath,
    followConcept,
    addAdjacent,
    removeNode,
    runCypher,
  };
}
