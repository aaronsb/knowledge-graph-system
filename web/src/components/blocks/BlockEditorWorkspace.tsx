/**
 * Block Editor Workspace
 *
 * Standalone mode for the Block Builder with full flow management.
 * - Left panel with tabs: Diagrams | Properties
 * - Center: Block canvas (BlockBuilder component)
 *
 * Shares state with embedded explorer mode via blockDiagramStore.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Blocks,
  Plus,
  Trash2,
  FileUp,
  Clock,
  FolderOpen,
  Settings2,
  Palette,
} from 'lucide-react';
import { BlockBuilder, type BlockBuilderHandle } from './BlockBuilder';
import { BlockPalette } from './BlockPalette';
import { IconRailPanel } from '../shared/IconRailPanel';
import { useBlockDiagramStore } from '../../store/blockDiagramStore';
import type { DiagramMetadata } from '../../store/blockDiagramStore';
import type { BlockType } from '../../types/blocks';

export const BlockEditorWorkspace: React.FC = () => {
  const navigate = useNavigate();
  const { diagramId } = useParams<{ diagramId?: string }>();

  const {
    currentDiagramId,
    currentDiagramName,
    hasUnsavedChanges,
    listDiagrams,
    listDiagramsSync,
    loadDiagram,
    deleteDiagram,
    clearWorkingCanvas,
    setWorkingCanvas,
    importFromFile,
    saveDiagram,
    workingNodes,
    workingEdges,
    diagrams,
  } = useBlockDiagramStore();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('palette');

  // Ref to BlockBuilder for adding blocks from palette
  const blockBuilderRef = useRef<BlockBuilderHandle>(null);

  // Handler for adding blocks via the palette
  const handleAddBlock = (type: BlockType) => {
    blockBuilderRef.current?.addBlock(type);
  };

  // Load diagrams list on mount and when diagram changes
  useEffect(() => {
    listDiagrams();
  }, [currentDiagramId, hasUnsavedChanges]);

  // Load diagram from URL param
  useEffect(() => {
    if (diagramId && diagramId !== currentDiagramId) {
      loadDiagram(diagramId).then((diagram) => {
        if (diagram) {
          setWorkingCanvas(diagram.nodes, diagram.edges);
          setSelectedId(diagramId);
        }
      });
    }
  }, [diagramId]);

  // Sync selected with current
  useEffect(() => {
    setSelectedId(currentDiagramId);
  }, [currentDiagramId]);

  const handleNewDiagram = () => {
    clearWorkingCanvas();
    setActiveTab('diagrams');
    navigate('/blocks');
  };

  const handleSelectDiagram = async (id: string) => {
    const diagram = await loadDiagram(id);
    if (diagram) {
      setWorkingCanvas(diagram.nodes, diagram.edges);
      navigate(`/blocks/${id}`);
    }
  };

  const handleDeleteDiagram = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this diagram?')) {
      await deleteDiagram(id);
      if (currentDiagramId === id) {
        clearWorkingCanvas();
        navigate('/blocks');
      }
    }
  };

  const handleImport = async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        const diagram = await importFromFile(file);
        if (diagram) {
          // Save imported diagram
          const id = await saveDiagram(diagram.name, diagram.nodes, diagram.edges, diagram.description);
          setWorkingCanvas(diagram.nodes, diagram.edges);
          navigate(`/blocks/${id}`);
        }
      }
    };
    input.click();
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Diagrams tab content
  const diagramsContent = (
    <div className="p-2">
      <div className="flex items-center justify-between mb-2 px-2">
        <span className="text-xs font-medium text-muted-foreground">
          {diagrams.length} saved
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={handleImport}
            className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
            title="Import diagram"
          >
            <FileUp className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleNewDiagram}
            className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
            title="New diagram"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {diagrams.length === 0 ? (
        <div className="text-center py-8 text-sm text-muted-foreground">
          <Blocks className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No saved diagrams</p>
          <p className="text-xs mt-1">Create or import a diagram</p>
        </div>
      ) : (
        <div className="space-y-1">
          {diagrams.map((diagram) => (
            <div
              key={diagram.id}
              onClick={() => handleSelectDiagram(diagram.id)}
              className={`
                w-full text-left p-2 rounded-lg transition-colors group cursor-pointer
                ${
                  selectedId === diagram.id
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-accent'
                }
              `}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate">
                    {diagram.name}
                    {currentDiagramId === diagram.id && hasUnsavedChanges && (
                      <span className="ml-1 text-yellow-500">*</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs opacity-70 mt-0.5">
                    <span>{diagram.nodeCount} blocks</span>
                    <span>·</span>
                    <Clock className="w-3 h-3" />
                    <span>{formatDate(diagram.updatedAt)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectDiagram(diagram.id);
                    }}
                    className={`
                      p-1 rounded
                      ${
                        selectedId === diagram.id
                          ? 'hover:bg-primary-foreground/20'
                          : 'hover:bg-accent'
                      }
                    `}
                    title="Open diagram"
                  >
                    <FolderOpen className="w-3 h-3" />
                  </button>
                  <button
                    onClick={(e) => handleDeleteDiagram(diagram.id, e)}
                    className={`
                      p-1 rounded
                      ${
                        selectedId === diagram.id
                          ? 'hover:bg-primary-foreground/20'
                          : 'hover:bg-destructive/20 text-destructive'
                      }
                    `}
                    title="Delete diagram"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  // Properties tab content
  const propertiesContent = (
    <div className="p-4">
      {currentDiagramId ? (
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">
              Name
            </label>
            <div className="text-sm font-medium">{currentDiagramName}</div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">
                Blocks
              </label>
              <div className="text-sm">{workingNodes.length}</div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">
                Connections
              </label>
              <div className="text-sm">{workingEdges.length}</div>
            </div>
          </div>

          <div className="pt-3 border-t border-border">
            <div className="text-xs font-medium text-muted-foreground mb-2">
              Execution Mode
            </div>
            <div className="flex gap-1.5">
              <button className="flex-1 px-2 py-1.5 text-xs rounded bg-primary text-primary-foreground">
                Interactive
              </button>
              <button
                className="flex-1 px-2 py-1.5 text-xs rounded bg-muted text-muted-foreground opacity-50 cursor-not-allowed"
                disabled
                title="Coming soon (ADR-066)"
              >
                Published
              </button>
            </div>
          </div>

          <div>
            <div className="text-xs font-medium text-muted-foreground mb-2">
              Output Format
            </div>
            <div className="flex gap-1.5">
              <button className="flex-1 px-2 py-1.5 text-xs rounded bg-primary text-primary-foreground">
                Graph
              </button>
              <button
                className="px-2 py-1.5 text-xs rounded bg-muted text-muted-foreground opacity-50 cursor-not-allowed"
                disabled
              >
                JSON
              </button>
              <button
                className="px-2 py-1.5 text-xs rounded bg-muted text-muted-foreground opacity-50 cursor-not-allowed"
                disabled
              >
                CSV
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-sm text-muted-foreground">
          <Settings2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No diagram selected</p>
          <p className="text-xs mt-1">Select or create a diagram</p>
        </div>
      )}
    </div>
  );

  // Palette tab content - styled for the panel
  const paletteContent = (
    <BlockPalette
      onAddBlock={handleAddBlock}
      className="p-3 overflow-y-auto"
    />
  );

  const panelTabs = [
    { id: 'palette', icon: Palette, label: 'Blocks', content: paletteContent },
    { id: 'diagrams', icon: FolderOpen, label: 'Diagrams', content: diagramsContent },
    { id: 'properties', icon: Settings2, label: 'Properties', content: propertiesContent },
  ];

  return (
    <div className="h-full flex">
      {/* Left Panel - Icon Rail with Palette, Diagrams, Properties */}
      <IconRailPanel
        tabs={panelTabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        defaultExpanded={true}
      />

      {/* Center - Block Canvas */}
      <div className="flex-1 flex flex-col bg-background">
        {/* Toolbar */}
        <div className="h-12 border-b border-border bg-card px-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Blocks className="w-5 h-5 text-muted-foreground" />
            <span className="font-semibold">
              {currentDiagramName || 'Untitled Diagram'}
              {hasUnsavedChanges && (
                <span className="ml-1 text-yellow-500" title="Unsaved changes">•</span>
              )}
            </span>
          </div>
        </div>

        {/* Canvas */}
        <div className="flex-1 relative">
          <BlockBuilder ref={blockBuilderRef} hidePalette />
        </div>
      </div>
    </div>
  );
};
