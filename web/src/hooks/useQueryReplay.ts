/**
 * useQueryReplay
 *
 * Shared hook for replaying saved query definitions into graphStore.
 * Executes { op, cypher }[] statements sequentially, applying +/- operators
 * against rawGraphData. Used by any explorer that loads saved queries.
 *
 * @verified 2fd1194f
 */

import { useState, useCallback } from 'react';
import { useGraphStore, type SearchParams } from '../store/graphStore';
import { apiClient } from '../api/client';
import { mapWorkingGraphToRawGraph } from '../utils/cypherResultMapper';
import { statementsToProgram } from '../utils/programBuilder';

/** Minimal shape a saved query must have to be replayed (exploration, polarity, or legacy).  @verified 7b5be48d */
export interface ReplayableDefinition {
  id?: number;
  name?: string;
  definition_type: string;
  definition: Record<string, unknown>;
}

/** Replays saved query definitions into graphStore.rawGraphData with +/- semantics.
 *  @verified 2fd1194f */
export function useQueryReplay() {
  const [isReplaying, setIsReplaying] = useState(false);

  const {
    setGraphData,
    setRawGraphData,
    mergeRawGraphData,
    subtractRawGraphData,
    resetExplorationSession,
    setSearchParams,
    setSimilarityThreshold,
    setPolarityState,
  } = useGraphStore();

  const replayQuery = useCallback(async (query: ReplayableDefinition) => {
    const definition = query.definition;

    // Exploration-type: replay +/- Cypher statements via GraphProgram execution
    if (query.definition_type === 'exploration' && definition?.statements) {
      setIsReplaying(true);
      try {
        setGraphData(null);
        setRawGraphData(null);
        resetExplorationSession();

        const stmts = definition.statements as Array<{ op: '+' | '-'; cypher: string }>;
        const program = statementsToProgram(stmts);
        const programResult = await apiClient.executeProgram({
          program: program as unknown as Record<string, unknown>,
        });
        const mapped = mapWorkingGraphToRawGraph(programResult.result);
        mergeRawGraphData(mapped);

        // Reconstruct exploration session so Save/Export work after load
        for (const stmt of stmts) {
          useGraphStore.getState().addExplorationStep({
            action: 'cypher',
            op: stmt.op,
            cypher: stmt.cypher,
          });
        }
      } catch (error) {
        console.error('Failed to replay exploration:', error);
      } finally {
        setIsReplaying(false);
      }
      return;
    }

    // Polarity-type: restore pole selections and trigger auto-run
    if (query.definition_type === 'polarity' && definition?.positive_pole_id) {
      setPolarityState({
        selectedPositivePole: {
          concept_id: definition.positive_pole_id as string,
          label: (definition.positive_pole_label as string) || 'Positive',
        },
        selectedNegativePole: {
          concept_id: definition.negative_pole_id as string,
          label: (definition.negative_pole_label as string) || 'Negative',
        },
        maxCandidates: typeof definition.maxCandidates === 'number' ? definition.maxCandidates : 20,
        maxHops: typeof definition.maxHops === 'number' ? definition.maxHops : 1,
        autoDiscover: typeof definition.autoDiscover === 'boolean' ? definition.autoDiscover : true,
        pendingAnalysis: true,
      });
      return;
    }

    // Legacy: searchParams-based queries
    if (definition?.searchParams) {
      setSearchParams(definition.searchParams as SearchParams);
      if (typeof definition.similarityThreshold === 'number') {
        setSimilarityThreshold(definition.similarityThreshold);
      }
    }
  }, [setGraphData, setRawGraphData, mergeRawGraphData, subtractRawGraphData, resetExplorationSession, setSearchParams, setSimilarityThreshold, setPolarityState]);

  return { replayQuery, isReplaying };
}
