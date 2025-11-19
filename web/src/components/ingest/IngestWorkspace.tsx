/**
 * Ingest Workspace
 *
 * Web-based content ingestion interface.
 */

import React from 'react';
import { Upload } from 'lucide-react';
import { WorkspacePlaceholder } from '../shared/WorkspacePlaceholder';

export const IngestWorkspace: React.FC = () => {
  return (
    <WorkspacePlaceholder
      icon={Upload}
      title="Ingest"
      description="Upload documents and URLs for knowledge extraction"
      pattern="Drop files → configure → approve → monitor"
      features={[
        {
          label: 'Drag-and-drop file upload',
          description: 'Support for text, PDF, and other document formats',
        },
        {
          label: 'URL ingestion',
          description: 'Extract content from web pages',
        },
        {
          label: 'Batch directory selection',
          description: 'Process multiple files at once',
        },
        {
          label: 'Ontology selector',
          description: 'Choose target ontology for extracted concepts',
        },
        {
          label: 'Job preview with cost estimate',
          description: 'Review extraction plan before submission',
        },
      ]}
    />
  );
};
