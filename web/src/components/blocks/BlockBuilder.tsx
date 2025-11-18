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
import { BlockContextMenu } from './BlockContextMenu';
import { StartBlock } from './StartBlock';
import { EndBlock } from './EndBlock';
import { SearchBlock } from './SearchBlock';
import { NeighborhoodBlock } from './NeighborhoodBlock';
import { OntologyFilterBlock } from './OntologyFilterBlock';
import { EdgeFilterBlock } from './EdgeFilterBlock';
import { NodeFilterBlock } from './NodeFilterBlock';
import { AndBlock } from './AndBlock';
import { OrBlock } from './OrBlock';
import { NotBlock } from './NotBlock';
import { LimitBlock } from './LimitBlock';
import { compileBlocksToOpenCypher } from '../../lib/blockCompiler';
import { apiClient } from '../../api/client';
import { useGraphStore } from '../../store/graphStore';
import { useThemeStore } from '../../store/themeStore';

import type { BlockType, BlockData, StartBlockParams, EndBlockParams, SearchBlockParams, NeighborhoodBlockParams, OntologyFilterBlockParams, EdgeFilterBlockParams, NodeFilterBlockParams, AndBlockParams, OrBlockParams, NotBlockParams, LimitBlockParams } from '../../types/blocks';

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

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    nodeId: string;
    top: number;
    left: number;
  } | null>(null);

  // Get theme for MiniMap styling
  const { theme } = useThemeStore();

  // Register custom node types
  const nodeTypes: NodeTypes = useMemo(
    () => ({
      start: StartBlock,
      end: EndBlock,
      search: SearchBlock,
      neighborhood: NeighborhoodBlock,
      filterOntology: OntologyFilterBlock,
      filterEdge: EdgeFilterBlock,
      filterNode: NodeFilterBlock,
      and: AndBlock,
      or: OrBlock,
      not: NotBlock,
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
      case 'start':
        params = {} as StartBlockParams;
        label = 'Start';
        break;
      case 'end':
        params = {} as EndBlockParams;
        label = 'End';
        break;
      case 'search':
        params = { query: '', similarity: 0.6, limit: 1 } as SearchBlockParams;
        label = 'Search Concepts';
        break;
      case 'neighborhood':
        params = { depth: 2, direction: 'both' } as NeighborhoodBlockParams;
        label = 'Expand Neighborhood';
        break;
      case 'filterOntology':
        params = { ontologies: [] } as OntologyFilterBlockParams;
        label = 'Filter by Ontology';
        break;
      case 'filterEdge':
        params = { relationshipTypes: [] } as EdgeFilterBlockParams;
        label = 'Filter by Edge';
        break;
      case 'filterNode':
        params = { nodeLabels: [], minConfidence: 0 } as NodeFilterBlockParams;
        label = 'Filter by Node';
        break;
      case 'and':
        params = {} as AndBlockParams;
        label = 'AND Gate';
        break;
      case 'or':
        params = {} as OrBlockParams;
        label = 'OR Gate';
        break;
      case 'not':
        params = {} as NotBlockParams;
        label = 'NOT Gate';
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

  // Handle right-click on node
  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.preventDefault();
      setContextMenu({
        nodeId: node.id,
        top: event.clientY,
        left: event.clientX,
      });
    },
    []
  );

  // Delete a node
  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      setNodes(nds => nds.filter(n => n.id !== nodeId));
      setEdges(eds => eds.filter(e => e.source !== nodeId && e.target !== nodeId));
    },
    [setNodes, setEdges]
  );

  // Duplicate a node
  const handleDuplicateNode = useCallback(
    (nodeId: string) => {
      const node = nodes.find(n => n.id === nodeId);
      if (!node) return;

      const newId = `${node.type}-${Date.now()}`;
      const newNode: Node<BlockData> = {
        ...node,
        id: newId,
        position: {
          x: node.position.x + 50,
          y: node.position.y + 50,
        },
      };

      setNodes(nds => [...nds, newNode]);
    },
    [nodes, setNodes]
  );

  // Close context menu
  const handleCloseContextMenu = useCallback(() => {
    setContextMenu(null);
  }, []);

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
      console.log('[BlockBuilder] Executing query:', compiledCypher);

      const result = await apiClient.executeCypherQuery({
        query: compiledCypher,
        limit: 100,
      });

      console.log('[BlockBuilder] API result:', result);

      // Check if we got any results
      if (!result.nodes || result.nodes.length === 0) {
        setExecutionError(`Query executed successfully but returned 0 nodes. This could mean:\n- No concepts match your search criteria\n- The Start block query returned no results\n- Check the openCypher output for the actual query`);
        return;
      }

      // Transform to graph format
      const { transformForD3 } = await import('../../utils/graphTransform');

      // Build a map of internal vertex IDs to concept_ids
      // The API returns internal AGE vertex IDs, but we need concept_ids
      const internalToConceptId = new Map<string, string>();
      result.nodes.forEach((n: any) => {
        const conceptId = n.properties?.concept_id || n.id;
        internalToConceptId.set(n.id, conceptId);
      });

      const graphNodes = result.nodes.map((n: any) => ({
        concept_id: n.properties?.concept_id || n.id,
        label: n.label,
        ontology: n.properties?.ontology || 'default',
        grounding_strength: n.properties?.grounding_strength,
      }));

      // Map relationship IDs from internal vertex IDs to concept_ids
      const links = result.relationships.map((r: any) => ({
        from_id: internalToConceptId.get(r.from_id) || r.from_id,
        to_id: internalToConceptId.get(r.to_id) || r.to_id,
        relationship_type: r.type,
        category: r.properties?.category,
      }));

      console.log('[BlockBuilder] Transformed nodes:', graphNodes.length, 'links:', links.length);

      const graphData = transformForD3(graphNodes, links);

      console.log('[BlockBuilder] Final graph data:', graphData);

      useGraphStore.getState().setGraphData(graphData);

      console.log('[BlockBuilder] Graph data set in store');
    } catch (error: any) {
      console.error('[BlockBuilder] Execution error:', error);
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
    <div className="flex">
      {/* Block Palette */}
      <BlockPalette onAddBlock={handleAddBlock} />

      {/* Main Canvas Area */}
      <div className="flex-1 flex flex-col block-builder-container">
        {/* Top Toolbar */}
        <div className="h-14 bg-card dark:bg-gray-800 border-b border-border dark:border-gray-700 px-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h3 className="font-semibold text-card-foreground dark:text-gray-100">Visual Query Builder</h3>
            <span className="text-xs text-muted-foreground dark:text-gray-400">{nodes.length} blocks</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleClear}
              disabled={nodes.length === 0}
              className="px-3 py-1.5 text-sm text-card-foreground dark:text-gray-100 bg-card dark:bg-gray-700 border border-border dark:border-gray-600 rounded hover:bg-accent dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Trash2 className="w-4 h-4" />
              Clear
            </button>

            <button
              onClick={handleSendToEditor}
              disabled={!compiledCypher || hasErrors}
              className="px-3 py-1.5 text-sm text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30 border border-blue-300 dark:border-blue-700 rounded hover:bg-blue-100 dark:hover:bg-blue-900/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Code className="w-4 h-4" />
              Send to Editor
            </button>

            <button
              onClick={handleExecute}
              disabled={!canExecute}
              className="px-3 py-1.5 text-sm text-white bg-green-600 dark:bg-green-700 rounded hover:bg-green-700 dark:hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              {isExecuting ? 'Executing...' : 'Execute Query'}
            </button>
          </div>
        </div>

        {/* React Flow Canvas - grows to fill available space */}
        <div className="flex-1 bg-muted dark:bg-gray-900 min-h-0">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeContextMenu={onNodeContextMenu}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.5}
            maxZoom={1.5}
          >
            <Background className="dark:bg-gray-800" />
            <Controls className="dark:bg-gray-800 dark:border-gray-600" />
            <MiniMap
              className="dark:bg-gray-800 dark:border-gray-600"
              maskColor={theme === 'dark' ? 'rgba(0, 0, 0, 0.2)' : 'rgba(0, 0, 0, 0.1)'}
              nodeColor={() => theme === 'dark' ? '#374151' : '#e2e8f0'}
              style={{
                backgroundColor: theme === 'dark' ? 'rgb(31, 41, 55)' : 'rgb(249, 250, 251)',
              }}
            />
          </ReactFlow>
        </div>

        {/* Draggable Divider */}
        {!isCollapsed && (
          <div
            onMouseDown={handleMouseDown}
            className="h-1 bg-border dark:bg-gray-700 hover:bg-blue-500 dark:hover:bg-blue-400 cursor-ns-resize transition-colors flex items-center justify-center group"
          >
            <div className="w-16 h-0.5 bg-muted-foreground dark:bg-gray-500 group-hover:bg-blue-600 dark:group-hover:bg-blue-400 rounded-full" />
          </div>
        )}

        {/* Bottom Panel - openCypher Preview */}
        <div
          className="bg-gray-900 dark:bg-black text-gray-100 dark:text-gray-200 p-4 overflow-auto border-t border-border dark:border-gray-700"
          style={{ height: `${currentPanelHeight}px` }}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <button
                onClick={toggleCollapse}
                className="hover:bg-gray-800 dark:hover:bg-gray-900 p-1 rounded transition-colors"
                title={isCollapsed ? "Expand panel" : "Collapse panel"}
              >
                {isCollapsed ? (
                  <ChevronDown className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                ) : (
                  <ChevronUp className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                )}
              </button>
              <Code className="w-4 h-4 text-gray-400 dark:text-gray-500" />
              <span className="text-sm font-medium text-gray-300 dark:text-gray-400">Generated openCypher</span>
            </div>
            {hasErrors && (
              <div className="flex items-center gap-1 text-red-400 dark:text-red-500 text-xs">
                <AlertCircle className="w-3 h-3" />
                {compileErrors.length} error{compileErrors.length > 1 ? 's' : ''}
              </div>
            )}
          </div>

          {hasErrors ? (
            <div className="space-y-2">
              {compileErrors.map((error, i) => (
                <div key={i} className="flex items-start gap-2 text-red-400 dark:text-red-500 text-sm">
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              ))}
            </div>
          ) : compiledCypher ? (
            <pre className="font-mono text-sm text-green-400 dark:text-green-500">{compiledCypher}</pre>
          ) : (
            <div className="text-gray-500 dark:text-gray-600 text-sm italic">
              Add blocks from the palette to build your query
            </div>
          )}

          {executionError && (
            <div className="mt-3 p-3 bg-red-900/20 dark:bg-red-900/30 border border-red-700 dark:border-red-800 rounded text-red-300 dark:text-red-400 text-sm">
              {executionError}
            </div>
          )}
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <BlockContextMenu
          id={contextMenu.nodeId}
          top={contextMenu.top}
          left={contextMenu.left}
          onDelete={handleDeleteNode}
          onDuplicate={handleDuplicateNode}
          onClose={handleCloseContextMenu}
        />
      )}
    </div>
  );
};
