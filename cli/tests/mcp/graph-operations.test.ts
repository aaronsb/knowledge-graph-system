/**
 * GraphOperationExecutor unit tests
 *
 * Tests label resolution thresholds and queue execution defaults.
 */

import { GraphOperationExecutor } from '../../src/mcp/graph-operations';
import type { KnowledgeGraphClient } from '../../src/api/client';
import type { SearchResponse } from '../../src/types';

/** Build a minimal mock client with only the methods under test. */
function mockClient(overrides: Partial<KnowledgeGraphClient> = {}): KnowledgeGraphClient {
  return {
    searchConcepts: jest.fn(),
    ...overrides,
  } as unknown as KnowledgeGraphClient;
}

/** Build a SearchResponse with the given results. */
function searchResponse(
  results: Array<{ concept_id: string; label: string; score: number }>
): SearchResponse {
  return {
    query: 'test',
    count: results.length,
    results: results.map(r => ({
      ...r,
      documents: [],
      evidence_count: 0,
    })),
  };
}

describe('GraphOperationExecutor', () => {
  describe('resolveConceptByLabel', () => {
    it('should resolve when score >= 0.75', async () => {
      const client = mockClient({
        searchConcepts: jest.fn().mockResolvedValue(
          searchResponse([{ concept_id: 'c_abc', label: 'CAP Theorem', score: 0.82 }])
        ),
      });
      const executor = new GraphOperationExecutor(client);

      const result = await executor.resolveConceptByLabel('CAP Theorem');

      expect(result).toBe('c_abc');
      expect(client.searchConcepts).toHaveBeenCalledWith(
        expect.objectContaining({ min_similarity: 0.6, limit: 3 })
      );
    });

    it('should resolve at exactly 0.75 threshold', async () => {
      const client = mockClient({
        searchConcepts: jest.fn().mockResolvedValue(
          searchResponse([{ concept_id: 'c_edge', label: 'Boundary Concept', score: 0.75 }])
        ),
      });
      const executor = new GraphOperationExecutor(client);

      const result = await executor.resolveConceptByLabel('Boundary Concept');

      expect(result).toBe('c_edge');
    });

    it('should throw "did you mean?" when score is between 0.60 and 0.75', async () => {
      const client = mockClient({
        searchConcepts: jest.fn().mockResolvedValue(
          searchResponse([
            { concept_id: 'c_near', label: 'Multipolar Trap Dynamics', score: 0.72 },
            { concept_id: 'c_alt', label: 'Multipolar Systems', score: 0.65 },
          ])
        ),
      });
      const executor = new GraphOperationExecutor(client);

      await expect(executor.resolveConceptByLabel('Multipolar Trap'))
        .rejects.toThrow('Did you mean');

      await expect(executor.resolveConceptByLabel('Multipolar Trap'))
        .rejects.toThrow('c_near');
    });

    it('should include up to 3 suggestions in "did you mean?" error', async () => {
      const client = mockClient({
        searchConcepts: jest.fn().mockResolvedValue(
          searchResponse([
            { concept_id: 'c_1', label: 'Alpha', score: 0.72 },
            { concept_id: 'c_2', label: 'Beta', score: 0.68 },
            { concept_id: 'c_3', label: 'Gamma', score: 0.62 },
          ])
        ),
      });
      const executor = new GraphOperationExecutor(client);

      await expect(executor.resolveConceptByLabel('test'))
        .rejects.toThrow(/Alpha.*Beta.*Gamma/);
    });

    it('should throw "no concept found" when no results returned', async () => {
      const client = mockClient({
        searchConcepts: jest.fn().mockResolvedValue(searchResponse([])),
      });
      const executor = new GraphOperationExecutor(client);

      await expect(executor.resolveConceptByLabel('Nonexistent'))
        .rejects.toThrow('No concept found matching label');
    });

    it('should include similarity percentage in suggestions', async () => {
      const client = mockClient({
        searchConcepts: jest.fn().mockResolvedValue(
          searchResponse([{ concept_id: 'c_x', label: 'Operational Moat', score: 0.689 }])
        ),
      });
      const executor = new GraphOperationExecutor(client);

      await expect(executor.resolveConceptByLabel('Operational Moat'))
        .rejects.toThrow('68.9%');
    });
  });

  describe('executeQueue', () => {
    it('should default to continue_on_error=true', async () => {
      const client = mockClient({
        searchConcepts: jest.fn().mockResolvedValue(searchResponse([])),
        createConcept: jest.fn()
          .mockResolvedValueOnce({ concept_id: 'c_1', label: 'A', created: true })
          .mockRejectedValueOnce(new Error('duplicate'))
          .mockResolvedValueOnce({ concept_id: 'c_3', label: 'C', created: true }),
      } as unknown as Partial<KnowledgeGraphClient>);
      const executor = new GraphOperationExecutor(client);

      const result = await executor.executeQueue([
        { op: 'create', entity: 'concept', label: 'A', ontology: 'test' },
        { op: 'create', entity: 'concept', label: 'B', ontology: 'test' },
        { op: 'create', entity: 'concept', label: 'C', ontology: 'test' },
      ]);

      // With default continue_on_error=true, all 3 operations should execute
      expect(result.results).toHaveLength(3);
      expect(result.successCount).toBe(2);
      expect(result.errorCount).toBe(1);
      expect(result.stopIndex).toBe(-1); // -1 means no early stop
    });

    it('should stop on first error when continue_on_error=false', async () => {
      const client = mockClient({
        searchConcepts: jest.fn().mockResolvedValue(searchResponse([])),
        createConcept: jest.fn()
          .mockResolvedValueOnce({ concept_id: 'c_1', label: 'A', created: true })
          .mockRejectedValueOnce(new Error('duplicate'))
          .mockResolvedValueOnce({ concept_id: 'c_3', label: 'C', created: true }),
      } as unknown as Partial<KnowledgeGraphClient>);
      const executor = new GraphOperationExecutor(client);

      const result = await executor.executeQueue(
        [
          { op: 'create', entity: 'concept', label: 'A', ontology: 'test' },
          { op: 'create', entity: 'concept', label: 'B', ontology: 'test' },
          { op: 'create', entity: 'concept', label: 'C', ontology: 'test' },
        ],
        false
      );

      // Should stop at operation 2 (index 1)
      expect(result.results).toHaveLength(2);
      expect(result.successCount).toBe(1);
      expect(result.errorCount).toBe(1);
      expect(result.stopIndex).toBe(1);
    });
  });
});
