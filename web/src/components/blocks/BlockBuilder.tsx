/**
 * Block Builder - Visual drag-and-drop query construction
 */

import React, { useState, useCallback, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  type NodeTypes,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { Code, Play, Trash2, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { BlockPalette } from './BlockPalette';
import { SearchBlock } from './SearchBlock';
import { NeighborhoodBlock } from './NeighborhoodBlock';
import { FilterBlock } from './FilterBlock';
import { LimitBlock } from './LimitBlock';
import { compileBlocksToOpenCypher } from '../../lib/blockCompiler';
import { apiClient } from '../../api/client';
import { useGraphStore } from '../../store/graphStore';

import type { BlockType, BlockData, SearchBlockParams, NeighborhoodBlockParams, FilterBlockParams, LimitBlockParams } from '../../types/blocks';

interface BlockBuilderProps {
  onSendToEditor?: (cypher: string) => void;
}

export const BlockBuilder: React.FC<BlockBuilderProps> = ({ onSendToEditor }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [compiledCypher, setCompiledCypher] = useState('');
  const [compileErrors, setCompileErrors] = useState<string[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionError, setExecutionError] = useState<string | null>(null);

  // Resizable panel state
  const [bottomPanelHeight, setBottomPanelHeight] = useState(200); // Default 200px
  const [isDragging, setIsDragging] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Register custom node types
  const nodeTypes: NodeTypes = useMemo(
    () => ({
      search: SearchBlock,
      neighborhood: NeighborhoodBlock,
      filter: FilterBlock,
      limit: LimitBlock,
    }),
    []
  );

  // Add a block to the canvas
  const handleAddBlock = useCallback((type: BlockType) => {
    const id = `${type}-${Date.now()}`;

    // Create default params based on block type
    let params: any;
    let label: string;

    switch (type) {
      case 'search':
        params = { query: '', similarity: 0.6 } as SearchBlockParams;
        label = 'Search Concepts';
        break;
      case 'neighborhood':
        params = { depth: 2, direction: 'both' } as NeighborhoodBlockParams;
        label = 'Expand Neighborhood';
        break;
      case 'filter':
        params = { ontologies: [], minConfidence: 0 } as FilterBlockParams;
        label = 'Filter Results';
        break;
      case 'limit':
        params = { count: 10 } as LimitBlockParams;
        label = 'Limit Results';
        break;
      default:
        return;
    }

    const newNode: Node<BlockData> = {
      id,
      type,
      position: { x: 100 + nodes.length * 50, y: 100 + nodes.length * 30 },
      data: { type, label, params },
    };

    setNodes(nds => [...nds, newNode]);
  }, [nodes.length, setNodes]);

  // Handle edge connections
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges(eds => addEdge(connection, eds));
    },
    [setEdges]
  );

  // Compile blocks to openCypher whenever nodes or edges change
  React.useEffect(() => {
    if (nodes.length > 0) {
      const result = compileBlocksToOpenCypher(nodes, edges);
      setCompiledCypher(result.cypher);
      setCompileErrors(result.errors);
    } else {
      setCompiledCypher('');
      setCompileErrors([]);
    }
  }, [nodes, edges]);

  // Clear all blocks
  const handleClear = useCallback(() => {
    setNodes([]);
    setEdges([]);
    setExecutionError(null);
  }, [setNodes, setEdges]);

  // Send to openCypher editor
  const handleSendToEditor = useCallback(() => {
    if (compiledCypher && onSendToEditor) {
      onSendToEditor(compiledCypher);
    }
  }, [compiledCypher, onSendToEditor]);

  // Execute the compiled query
  const handleExecute = useCallback(async () => {
    if (!compiledCypher || compileErrors.length > 0) {
      return;
    }

    setIsExecuting(true);
    setExecutionError(null);

    try {
      const result = await apiClient.executeCypherQuery({
        query: compiledCypher,
        limit: 100,
      });

      // Transform to graph format
      const { transformForD3 } = await import('../../utils/graphTransform');

      const graphNodes = result.nodes.map((n: any) => ({
        concept_id: n.id,
        label: n.label,
        ontology: n.properties?.ontology || 'default',
      }));

      const links = result.relationships.map((r: any) => ({
        from_id: r.from_id,
        to_id: r.to_id,
        relationship_type: r.type,
      }));

      const graphData = transformForD3(graphNodes, links);
      useGraphStore.getState().setGraphData(graphData);
    } catch (error: any) {
      setExecutionError(error.response?.data?.detail || error.message || 'Query execution failed');
    } finally {
      setIsExecuting(false);
    }
  }, [compiledCypher, compileErrors]);

  const hasErrors = compileErrors.length > 0;
  const canExecute = compiledCypher && !hasErrors && !isExecuting;

  // Resize handlers
  const handleMouseDown = useCallback(() => {
    setIsDragging(true);
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging) return;

    const container = document.querySelector('.block-builder-container');
    if (!container) return;

    const containerRect = container.getBoundingClientRect();
    const newHeight = containerRect.bottom - e.clientY;

    // Constrain between 100px and 600px
    const constrainedHeight = Math.max(100, Math.min(600, newHeight));
    setBottomPanelHeight(constrainedHeight);
  }, [isDragging]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Attach global mouse listeners when dragging
  React.useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  // Toggle collapse
  const toggleCollapse = useCallback(() => {
    setIsCollapsed(prev => !prev);
  }, []);

  const currentPanelHeight = isCollapsed ? 0 : bottomPanelHeight;

  return (
    <div className="flex h-full">
      {/* Block Palette */}
      <BlockPalette onAddBlock={handleAddBlock} />

      {/* Main Canvas Area */}
      <div className="flex-1 flex flex-col block-builder-container">
        {/* Top Toolbar */}
        <div className="h-14 bg-white border-b border-gray-200 px-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h3 className="font-semibold text-gray-700">Visual Query Builder</h3>
            <span className="text-xs text-gray-500">{nodes.length} blocks</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleClear}
              disabled={nodes.length === 0}
              className="px-3 py-1.5 text-sm text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Trash2 className="w-4 h-4" />
              Clear
            </button>

            <button
              onClick={handleSendToEditor}
              disabled={!compiledCypher || hasErrors}
              className="px-3 py-1.5 text-sm text-blue-700 bg-blue-50 border border-blue-300 rounded hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Code className="w-4 h-4" />
              Send to Editor
            </button>

            <button
              onClick={handleExecute}
              disabled={!canExecute}
              className="px-3 py-1.5 text-sm text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              {isExecuting ? 'Executing...' : 'Execute Query'}
            </button>
          </div>
        </div>

        {/* React Flow Canvas */}
        <div
          className="bg-gray-50"
          style={{ height: `calc(100% - 56px - ${currentPanelHeight}px${currentPanelHeight > 0 ? ' - 4px' : ''})` }}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.5}
            maxZoom={1.5}
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>

        {/* Draggable Divider */}
        {!isCollapsed && (
          <div
            onMouseDown={handleMouseDown}
            className="h-1 bg-gray-300 hover:bg-blue-500 cursor-ns-resize transition-colors flex items-center justify-center group"
          >
            <div className="w-16 h-0.5 bg-gray-400 group-hover:bg-blue-600 rounded-full" />
          </div>
        )}

        {/* Bottom Panel - openCypher Preview */}
        <div
          className="bg-gray-900 text-gray-100 p-4 overflow-auto border-t border-gray-700"
          style={{ height: `${currentPanelHeight}px` }}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <button
                onClick={toggleCollapse}
                className="hover:bg-gray-800 p-1 rounded transition-colors"
                title={isCollapsed ? "Expand panel" : "Collapse panel"}
              >
                {isCollapsed ? (
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                ) : (
                  <ChevronUp className="w-4 h-4 text-gray-400" />
                )}
              </button>
              <Code className="w-4 h-4 text-gray-400" />
              <span className="text-sm font-medium text-gray-300">Generated openCypher</span>
            </div>
            {hasErrors && (
              <div className="flex items-center gap-1 text-red-400 text-xs">
                <AlertCircle className="w-3 h-3" />
                {compileErrors.length} error{compileErrors.length > 1 ? 's' : ''}
              </div>
            )}
          </div>

          {hasErrors ? (
            <div className="space-y-2">
              {compileErrors.map((error, i) => (
                <div key={i} className="flex items-start gap-2 text-red-400 text-sm">
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              ))}
            </div>
          ) : compiledCypher ? (
            <pre className="font-mono text-sm text-green-400">{compiledCypher}</pre>
          ) : (
            <div className="text-gray-500 text-sm italic">
              Add blocks from the palette to build your query
            </div>
          )}

          {executionError && (
            <div className="mt-3 p-3 bg-red-900/20 border border-red-700 rounded text-red-300 text-sm">
              {executionError}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
