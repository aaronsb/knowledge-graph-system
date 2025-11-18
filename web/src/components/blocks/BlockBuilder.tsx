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
  type Edge,
  type NodeTypes,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { Code, Play, Trash2, AlertCircle, ChevronDown, ChevronUp, Save, FolderOpen, Download, Upload } from 'lucide-react';
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
import { EnrichBlock } from './EnrichBlock';
import { VectorSearchBlock } from './VectorSearchBlock';
import { EpistemicFilterBlock } from './EpistemicFilterBlock';
import { BlockHelpPopup } from './BlockHelpPopup';
import { compileBlocksToOpenCypher } from '../../lib/blockCompiler';
import { apiClient } from '../../api/client';
import { useGraphStore } from '../../store/graphStore';
import { useThemeStore } from '../../store/themeStore';
import { useBlockDiagramStore, type DiagramMetadata } from '../../store/blockDiagramStore';

import type { BlockType, BlockData, StartBlockParams, EndBlockParams, SearchBlockParams, VectorSearchBlockParams, NeighborhoodBlockParams, OntologyFilterBlockParams, EdgeFilterBlockParams, NodeFilterBlockParams, AndBlockParams, OrBlockParams, NotBlockParams, LimitBlockParams, EpistemicFilterBlockParams, EnrichBlockParams } from '../../types/blocks';

interface BlockBuilderProps {
  onSendToEditor?: (cypher: string) => void;
}

export const BlockBuilder: React.FC<BlockBuilderProps> = ({ onSendToEditor }) => {
  // Get initial state from store (persists across view switches)
  const { workingNodes: initialNodes, workingEdges: initialEdges } = useBlockDiagramStore.getState();

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
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
    id: string;
    type: 'node' | 'edge';
    top: number;
    left: number;
  } | null>(null);

  // Help popup state
  const [helpPopup, setHelpPopup] = useState<{
    blockType: BlockType;
    position: { x: number; y: number };
  } | null>(null);

  // Save/Load dialog state
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showLoadDialog, setShowLoadDialog] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveDescription, setSaveDescription] = useState('');
  const [savedDiagrams, setSavedDiagrams] = useState<DiagramMetadata[]>([]);

  // File input ref for import
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Get theme for MiniMap styling
  const { theme } = useThemeStore();

  // Block diagram persistence
  const {
    currentDiagramId,
    currentDiagramName,
    hasUnsavedChanges,
    setHasUnsavedChanges,
    workingNodes,
    workingEdges,
    setWorkingCanvas,
    clearWorkingCanvas,
    saveDiagram,
    loadDiagram,
    listDiagrams,
    deleteDiagram,
    exportToFile,
    importFromFile,
  } = useBlockDiagramStore();

  // Register custom node types
  const nodeTypes: NodeTypes = useMemo(
    () => ({
      start: StartBlock,
      end: EndBlock,
      // Cypher blocks
      search: SearchBlock,
      neighborhood: NeighborhoodBlock,
      filterOntology: OntologyFilterBlock,
      filterEdge: EdgeFilterBlock,
      filterNode: NodeFilterBlock,
      and: AndBlock,
      or: OrBlock,
      not: NotBlock,
      limit: LimitBlock,
      // Smart blocks
      vectorSearch: VectorSearchBlock,
      epistemicFilter: EpistemicFilterBlock,
      enrich: EnrichBlock,
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
        params = { executionMode: 'interactive' } as StartBlockParams;
        label = 'Start';
        break;
      case 'end':
        params = { outputFormat: 'visualization' } as EndBlockParams;
        label = 'End';
        break;
      case 'search':
        params = { query: '', similarity: 0.6, limit: 1 } as SearchBlockParams;
        label = 'Text Search';
        break;
      case 'vectorSearch':
        params = { query: '', similarity: 0.7, limit: 10 } as VectorSearchBlockParams;
        label = 'Vector Search';
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
        params = { excludePattern: '', excludeProperty: 'label' } as NotBlockParams;
        label = 'Exclude (NOT)';
        break;
      case 'limit':
        params = { count: 10 } as LimitBlockParams;
        label = 'Limit Results';
        break;
      case 'epistemicFilter':
        params = { includeStatuses: [], excludeStatuses: [] } as EpistemicFilterBlockParams;
        label = 'Epistemic Filter';
        break;
      case 'enrich':
        params = { fetchOntology: true, fetchGrounding: true, fetchSearchTerms: false } as EnrichBlockParams;
        label = 'Enrich Data';
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
    setHasUnsavedChanges(true);
  }, [nodes.length, setNodes, setHasUnsavedChanges]);

  // Handle edge connections
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges(eds => addEdge(connection, eds));
      setHasUnsavedChanges(true);
    },
    [setEdges, setHasUnsavedChanges]
  );

  // Handle right-click on node
  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.preventDefault();
      setContextMenu({
        id: node.id,
        type: 'node',
        top: event.clientY,
        left: event.clientX,
      });
    },
    []
  );

  // Handle right-click on edge
  const onEdgeContextMenu = useCallback(
    (event: React.MouseEvent, edge: Edge) => {
      event.preventDefault();
      setContextMenu({
        id: edge.id,
        type: 'edge',
        top: event.clientY,
        left: event.clientX,
      });
    },
    []
  );

  // Delete a node or edge
  const handleDelete = useCallback(
    (id: string) => {
      if (contextMenu?.type === 'edge') {
        setEdges(eds => eds.filter(e => e.id !== id));
      } else {
        setNodes(nds => nds.filter(n => n.id !== id));
        setEdges(eds => eds.filter(e => e.source !== id && e.target !== id));
      }
      setHasUnsavedChanges(true);
    },
    [contextMenu?.type, setNodes, setEdges, setHasUnsavedChanges]
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
      setHasUnsavedChanges(true);
    },
    [nodes, setNodes, setHasUnsavedChanges]
  );

  // Close context menu
  const handleCloseContextMenu = useCallback(() => {
    setContextMenu(null);
  }, []);

  // Show help for a node
  const handleHelp = useCallback(
    (nodeId: string) => {
      const node = nodes.find(n => n.id === nodeId);
      if (!node) return;

      // Position popup near where the context menu was
      setHelpPopup({
        blockType: node.data.type,
        position: {
          x: contextMenu?.left || 200,
          y: contextMenu?.top || 200,
        },
      });
    },
    [nodes, contextMenu]
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

  // Sync canvas state to store (persists across view switches)
  React.useEffect(() => {
    setWorkingCanvas(nodes, edges);
  }, [nodes, edges, setWorkingCanvas]);

  // Clear all blocks
  const handleClear = useCallback(() => {
    setNodes([]);
    setEdges([]);
    setExecutionError(null);
    setHasUnsavedChanges(true);
  }, [setNodes, setEdges, setHasUnsavedChanges]);

  // Save diagram
  const handleSave = useCallback(() => {
    if (currentDiagramName) {
      // Quick save to existing diagram
      saveDiagram(currentDiagramName, nodes, edges);
    } else {
      // Open save dialog for new diagram
      setSaveName('');
      setSaveDescription('');
      setShowSaveDialog(true);
    }
  }, [currentDiagramName, nodes, edges, saveDiagram]);

  // Save As (always show dialog)
  const handleSaveAs = useCallback(() => {
    setSaveName(currentDiagramName || '');
    setSaveDescription('');
    setShowSaveDialog(true);
  }, [currentDiagramName]);

  // Confirm save from dialog
  const handleConfirmSave = useCallback(() => {
    if (!saveName.trim()) return;
    saveDiagram(saveName.trim(), nodes, edges, saveDescription.trim() || undefined);
    setShowSaveDialog(false);
  }, [saveName, saveDescription, nodes, edges, saveDiagram]);

  // Open load dialog
  const handleOpenLoadDialog = useCallback(() => {
    setSavedDiagrams(listDiagrams());
    setShowLoadDialog(true);
  }, [listDiagrams]);

  // Load a diagram
  const handleLoadDiagram = useCallback((id: string) => {
    const diagram = loadDiagram(id);
    if (diagram) {
      setNodes(diagram.nodes);
      setEdges(diagram.edges);
      setShowLoadDialog(false);
      setExecutionError(null);
    }
  }, [loadDiagram, setNodes, setEdges]);

  // Delete a saved diagram
  const handleDeleteDiagram = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this diagram?')) {
      deleteDiagram(id);
      setSavedDiagrams(listDiagrams());
    }
  }, [deleteDiagram, listDiagrams]);

  // Export current diagram to file
  const handleExport = useCallback(() => {
    const name = currentDiagramName || 'untitled-diagram';
    exportToFile(nodes, edges, name);
  }, [currentDiagramName, nodes, edges, exportToFile]);

  // Import diagram from file
  const handleImport = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const diagram = await importFromFile(file);
    if (diagram) {
      setNodes(diagram.nodes);
      setEdges(diagram.edges);
      setExecutionError(null);
      // Note: imported diagram is not auto-saved, user must save it
      setHasUnsavedChanges(true);
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [importFromFile, setNodes, setEdges, setHasUnsavedChanges]);

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
      console.log('[BlockBuilder] Executing annotated openCypher:', compiledCypher);

      // Check for smart blocks that need special handling
      const vectorSearchBlock = nodes.find(node => node.data.type === 'vectorSearch');

      let result: any;

      if (vectorSearchBlock) {
        // Smart block execution path - use API search
        const vsParams = vectorSearchBlock.data.params as VectorSearchBlockParams;
        console.log('[BlockBuilder] Vector Search smart block detected:', vsParams);

        if (!vsParams.query || vsParams.query.trim() === '') {
          setExecutionError('Vector Search requires a search query');
          return;
        }

        // Call the semantic search API
        const searchResult = await apiClient.searchConcepts({
          query: vsParams.query,
          limit: vsParams.limit || 10,
          min_similarity: vsParams.similarity || 0.7,
        });

        console.log('[BlockBuilder] Vector search result:', searchResult);

        // Transform search results to match Cypher result format
        result = {
          nodes: searchResult.results.map((r: any) => ({
            id: r.concept_id,
            label: r.label,
            properties: {
              concept_id: r.concept_id,
              label: r.label,
              ontology: r.ontology,
              grounding_strength: r.grounding_strength,
              search_terms: r.search_terms || [],
            }
          })),
          relationships: [], // Vector search returns nodes only, no relationships
        };
      } else {
        // Standard Cypher execution path
        result = await apiClient.executeCypherQuery({
          query: compiledCypher,
          limit: 100,
        });
      }

      console.log('[BlockBuilder] Execution result:', result);

      // Check if we got any results
      if (!result.nodes || result.nodes.length === 0) {
        setExecutionError(`Query executed successfully but returned 0 nodes. This could mean:\n- No concepts match your search criteria\n- The Start block query returned no results\n- Check the openCypher output for the actual query`);
        return;
      }

      // Build a map of internal vertex IDs to concept_ids
      // The API returns internal AGE vertex IDs, but we need concept_ids
      const internalToConceptId = new Map<string, string>();
      result.nodes.forEach((n: any) => {
        const conceptId = n.properties?.concept_id || n.id;
        internalToConceptId.set(n.id, conceptId);
      });

      // Check if there's an Enrich block in the flow
      const enrichBlock = nodes.find(node => node.data.type === 'enrich');
      const enrichParams = enrichBlock?.data.params as EnrichBlockParams | undefined;
      const shouldEnrich = enrichBlock && (enrichParams?.fetchOntology || enrichParams?.fetchGrounding || enrichParams?.fetchSearchTerms);

      // Transform to raw API format (same as getSubgraph returns)
      let rawNodes = result.nodes.map((n: any) => ({
        concept_id: n.properties?.concept_id || n.id,
        label: n.label,
        ontology: n.properties?.ontology || 'default',
        grounding_strength: n.properties?.grounding_strength,
        search_terms: n.properties?.search_terms || [],
      }));

      // If Enrich block is present, fetch full concept details (same as Smart Search)
      if (shouldEnrich) {
        console.log('[BlockBuilder] Enrich block detected, fetching concept details for', rawNodes.length, 'nodes');

        const enrichedNodes = await Promise.all(
          rawNodes.map(async (node) => {
            try {
              const details = await apiClient.getConceptDetails(node.concept_id);

              // Build enriched node matching Smart Search format (getSubgraph)
              // Always include all available data for consistent visualization
              return {
                concept_id: node.concept_id,
                label: details.label || node.label,
                // Use first document as ontology (same as getSubgraph line 87)
                ontology: details.documents?.[0] || node.ontology || 'Unknown',
                // Always include grounding_strength for node info display
                grounding_strength: details.grounding_strength ?? node.grounding_strength,
                // Include search_terms for display
                search_terms: details.search_terms || node.search_terms || [],
              };
            } catch (error) {
              console.warn(`[BlockBuilder] Failed to enrich concept ${node.concept_id}:`, error);
              return node; // Return unenriched node on error
            }
          })
        );

        rawNodes = enrichedNodes;
        console.log('[BlockBuilder] Enrichment complete');
      }

      // Map relationship IDs from internal vertex IDs to concept_ids
      const rawLinks = result.relationships.map((r: any) => ({
        from_id: internalToConceptId.get(r.from_id) || r.from_id,
        to_id: internalToConceptId.get(r.to_id) || r.to_id,
        relationship_type: r.type,
        category: r.properties?.category,
      }));

      console.log('[BlockBuilder] Raw nodes:', rawNodes.length, 'links:', rawLinks.length);

      // Use the same flow as Smart Search - set raw data and let App.tsx transform it
      // This ensures vocabulary enrichment and consistent visualization
      const store = useGraphStore.getState();
      store.setGraphData(null); // Clear old transformed data
      store.setRawGraphData({ nodes: rawNodes, links: rawLinks });

      console.log('[BlockBuilder] Raw graph data set in store (transformation will happen automatically)');
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
            {currentDiagramName ? (
              <span className="text-xs text-muted-foreground dark:text-gray-400">
                {currentDiagramName}{hasUnsavedChanges ? ' *' : ''}
              </span>
            ) : (
              <span className="text-xs text-muted-foreground dark:text-gray-400">{nodes.length} blocks</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Save/Load/Export/Import buttons */}
            <button
              onClick={handleSave}
              disabled={nodes.length === 0}
              className="px-2 py-1.5 text-sm text-card-foreground dark:text-gray-100 bg-card dark:bg-gray-700 border border-border dark:border-gray-600 rounded hover:bg-accent dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              title={currentDiagramName ? `Save "${currentDiagramName}"` : 'Save diagram'}
            >
              <Save className="w-4 h-4" />
            </button>

            <button
              onClick={handleOpenLoadDialog}
              className="px-2 py-1.5 text-sm text-card-foreground dark:text-gray-100 bg-card dark:bg-gray-700 border border-border dark:border-gray-600 rounded hover:bg-accent dark:hover:bg-gray-600"
              title="Load diagram"
            >
              <FolderOpen className="w-4 h-4" />
            </button>

            <button
              onClick={handleExport}
              disabled={nodes.length === 0}
              className="px-2 py-1.5 text-sm text-card-foreground dark:text-gray-100 bg-card dark:bg-gray-700 border border-border dark:border-gray-600 rounded hover:bg-accent dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Export to file"
            >
              <Download className="w-4 h-4" />
            </button>

            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-2 py-1.5 text-sm text-card-foreground dark:text-gray-100 bg-card dark:bg-gray-700 border border-border dark:border-gray-600 rounded hover:bg-accent dark:hover:bg-gray-600"
              title="Import from file"
            >
              <Upload className="w-4 h-4" />
            </button>

            <div className="w-px h-6 bg-border dark:bg-gray-600 mx-1" />

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

        {/* Hidden file input for import */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleImport}
          accept=".json"
          className="hidden"
        />

        {/* React Flow Canvas - grows to fill available space */}
        <div className="flex-1 bg-muted dark:bg-gray-900 min-h-0">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeContextMenu={onNodeContextMenu}
            onEdgeContextMenu={onEdgeContextMenu}
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
          id={contextMenu.id}
          top={contextMenu.top}
          left={contextMenu.left}
          onDelete={handleDelete}
          onDuplicate={contextMenu.type === 'node' ? handleDuplicateNode : undefined}
          onHelp={contextMenu.type === 'node' ? handleHelp : undefined}
          onClose={handleCloseContextMenu}
        />
      )}

      {/* Help Popup */}
      {helpPopup && (
        <BlockHelpPopup
          blockType={helpPopup.blockType}
          position={helpPopup.position}
          onClose={() => setHelpPopup(null)}
        />
      )}

      {/* Save Dialog */}
      {showSaveDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card dark:bg-gray-800 rounded-lg shadow-xl w-96 p-6">
            <h3 className="text-lg font-semibold text-card-foreground dark:text-gray-100 mb-4">Save Diagram</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-muted-foreground dark:text-gray-400 mb-1">Name</label>
                <input
                  type="text"
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  placeholder="My Query Diagram"
                  className="w-full px-3 py-2 border border-border dark:border-gray-600 bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm text-muted-foreground dark:text-gray-400 mb-1">Description (optional)</label>
                <textarea
                  value={saveDescription}
                  onChange={(e) => setSaveDescription(e.target.value)}
                  placeholder="What does this query do?"
                  rows={2}
                  className="w-full px-3 py-2 border border-border dark:border-gray-600 bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setShowSaveDialog(false)}
                className="px-4 py-2 text-sm text-card-foreground dark:text-gray-100 bg-card dark:bg-gray-700 border border-border dark:border-gray-600 rounded hover:bg-accent dark:hover:bg-gray-600"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmSave}
                disabled={!saveName.trim()}
                className="px-4 py-2 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Load Dialog */}
      {showLoadDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card dark:bg-gray-800 rounded-lg shadow-xl w-[500px] max-h-[600px] flex flex-col">
            <div className="p-6 border-b border-border dark:border-gray-700">
              <h3 className="text-lg font-semibold text-card-foreground dark:text-gray-100">Load Diagram</h3>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {savedDiagrams.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground dark:text-gray-400">
                  No saved diagrams yet
                </div>
              ) : (
                <div className="space-y-2">
                  {savedDiagrams.map((diagram) => (
                    <div
                      key={diagram.id}
                      onClick={() => handleLoadDiagram(diagram.id)}
                      className="p-3 border border-border dark:border-gray-600 rounded-lg hover:bg-accent dark:hover:bg-gray-700 cursor-pointer group"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-card-foreground dark:text-gray-100 truncate">
                            {diagram.name}
                          </div>
                          {diagram.description && (
                            <div className="text-xs text-muted-foreground dark:text-gray-400 truncate mt-0.5">
                              {diagram.description}
                            </div>
                          )}
                          <div className="text-[10px] text-muted-foreground dark:text-gray-500 mt-1">
                            {diagram.nodeCount} blocks, {diagram.edgeCount} connections
                          </div>
                        </div>
                        <button
                          onClick={(e) => handleDeleteDiagram(diagram.id, e)}
                          className="p-1 opacity-0 group-hover:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/30 rounded text-red-600 dark:text-red-400 transition-opacity"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="p-4 border-t border-border dark:border-gray-700">
              <button
                onClick={() => setShowLoadDialog(false)}
                className="w-full px-4 py-2 text-sm text-card-foreground dark:text-gray-100 bg-card dark:bg-gray-700 border border-border dark:border-gray-600 rounded hover:bg-accent dark:hover:bg-gray-600"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
