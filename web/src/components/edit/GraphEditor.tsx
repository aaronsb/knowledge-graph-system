/**
 * Graph Editor Workspace
 *
 * Manual graph editing interface.
 */

import React from 'react';
import { PencilLine } from 'lucide-react';
import { WorkspacePlaceholder } from '../shared/WorkspacePlaceholder';

export const GraphEditor: React.FC = () => {
  return (
    <WorkspacePlaceholder
      icon={PencilLine}
      title="Edit"
      description="Manually create and modify graph nodes and edges"
      pattern="Find node → edit properties → save"
      features={[
        {
          label: 'Node browser/search',
          description: 'Find concepts to edit',
        },
        {
          label: 'Create/update/delete nodes',
          description: 'Full CRUD operations for concepts',
        },
        {
          label: 'Create/update/delete edges',
          description: 'Manage relationships between concepts',
        },
        {
          label: 'Bypass upsert',
          description: 'Direct graph manipulation without LLM',
        },
        {
          label: 'Audit trail',
          description: 'Track all manual edits',
        },
      ]}
    />
  );
};
