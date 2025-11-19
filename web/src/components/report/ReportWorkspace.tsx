/**
 * Report Workspace
 *
 * Tabular and export views for query results.
 */

import React from 'react';
import { FileText } from 'lucide-react';
import { WorkspacePlaceholder } from '../shared/WorkspacePlaceholder';

export const ReportWorkspace: React.FC = () => {
  return (
    <WorkspacePlaceholder
      icon={FileText}
      title="Report"
      description="View query results in tabular format and export"
      pattern="Query → view table → export"
      features={[
        {
          label: 'Saved queries list',
          description: 'Quick access to your saved queries',
        },
        {
          label: 'Tabular result view',
          description: 'Data grid with column sorting and filtering',
        },
        {
          label: 'Export formats',
          description: 'Download as JSON, CSV, or Markdown',
        },
        {
          label: 'Column selection',
          description: 'Choose which fields to display',
        },
        {
          label: 'Pagination',
          description: 'Handle large result sets efficiently',
        },
      ]}
    />
  );
};
