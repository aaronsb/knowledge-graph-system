/**
 * SavedQueriesPanel
 *
 * Reusable saved queries list for IconRailPanel tabs.
 * Shows saved query definitions with load/delete, optional save button.
 * Used by any explorer that participates in the shared query system.
 *
 * @verified 2fd1194f
 */

import React, { useEffect } from 'react';
import { FolderOpen, Save, Code, Trash2 } from 'lucide-react';
import { useQueryDefinitionStore } from '../../store/queryDefinitionStore';
import type { ReplayableDefinition } from '../../hooks/useQueryReplay';

interface SavedQueriesPanelProps {
  /** Called when user clicks a saved query to load it */
  onLoadQuery: (query: ReplayableDefinition) => void;
  /** Called when user clicks Save — omit to hide the save button */
  onSaveExploration?: () => void;
  /** Called when user clicks Export to Editor — omit to hide the button */
  onExportToEditor?: () => void;
  /** Current exploration info for save button label (e.g. step count) */
  currentExploration?: { stepCount: number } | null;
  /** Filter by definition_type (e.g. 'exploration', 'block_diagram', 'polarity') */
  definitionTypeFilter?: string;
  /** Override the save button label (default: "Save (N steps)") */
  saveButtonLabel?: string;
}

/**
 * Format a type-aware subtitle for a saved query definition.
 * Each definition_type gets a meaningful summary instead of just the type name.
 */
function formatQuerySubtitle(query: ReplayableDefinition): string {
  const def = query.definition as Record<string, any>;
  switch (query.definition_type) {
    case 'exploration':
      return `${def?.statements?.length || 0} steps`;
    case 'polarity': {
      const pos = def?.positive_pole_label || 'A';
      const neg = def?.negative_pole_label || 'B';
      return `${pos} \u2194 ${neg}`;
    }
    case 'block_diagram':
      return `${def?.nodes?.length || 0} nodes`;
    case 'cypher':
      return `${def?.statements?.length || 1} statement${(def?.statements?.length || 1) !== 1 ? 's' : ''}`;
    default:
      return query.definition_type;
  }
}

/** Reusable saved queries list for any explorer's IconRailPanel sidebar.
 *  @verified 2fd1194f */
export const SavedQueriesPanel: React.FC<SavedQueriesPanelProps> = ({
  onLoadQuery,
  onSaveExploration,
  onExportToEditor,
  currentExploration,
  definitionTypeFilter,
  saveButtonLabel,
}) => {
  const {
    definitions: savedQueriesMap,
    definitionIds: savedQueryIds,
    loadDefinitions: loadSavedQueries,
    deleteDefinition: deleteSavedQuery,
    isLoading: isLoadingQueries,
  } = useQueryDefinitionStore();

  // Load saved queries on mount
  useEffect(() => {
    const params = definitionTypeFilter ? { definition_type: definitionTypeFilter } : undefined;
    loadSavedQueries(params);
  }, [loadSavedQueries, definitionTypeFilter]);

  const savedQueries = savedQueryIds.map(id => savedQueriesMap[id]).filter(Boolean);

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteSavedQuery(id);
  };

  const hasExploration = currentExploration && currentExploration.stepCount > 0;

  return (
    <div className="p-3">
      {/* Save / Export buttons (only shown if callbacks provided) */}
      {hasExploration && (onSaveExploration || onExportToEditor) && (
        <div className="flex gap-2 mb-3">
          {onSaveExploration && (
            <button
              onClick={onSaveExploration}
              className="flex-1 flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg border border-primary/30 bg-primary/5 hover:bg-primary/10 text-primary transition-colors"
            >
              <Save className="w-4 h-4" />
              {saveButtonLabel || `Save (${currentExploration!.stepCount} steps)`}
            </button>
          )}
          {onExportToEditor && (
            <button
              onClick={onExportToEditor}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border border-border hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
              title="Export to Cypher Editor"
            >
              <Code className="w-4 h-4" />
            </button>
          )}
        </div>
      )}

      {/* Query list */}
      {isLoadingQueries ? (
        <div className="text-center text-muted-foreground text-sm py-4">
          Loading...
        </div>
      ) : savedQueries.length === 0 ? (
        <div className="text-center text-muted-foreground text-sm py-4">
          <FolderOpen className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No saved queries</p>
          <p className="text-xs mt-1">Save queries from the search panel</p>
        </div>
      ) : (
        <div className="space-y-2">
          {savedQueries.map((query) => (
            <div
              key={query.id}
              className="border rounded-lg p-3 bg-card hover:bg-accent/50 transition-colors cursor-pointer group"
              onClick={() => onLoadQuery(query)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate">{query.name}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {formatQuerySubtitle(query)}
                    {' \u00b7 '}
                    {new Date(query.created_at).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={(e) => handleDelete(query.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-destructive hover:text-destructive/80 transition-opacity p-1"
                  title="Delete query"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
