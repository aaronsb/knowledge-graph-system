/**
 * Jobs Workspace
 *
 * Job queue visibility and management.
 */

import React from 'react';
import { ListTodo } from 'lucide-react';
import { WorkspacePlaceholder } from '../shared/WorkspacePlaceholder';

export const JobsWorkspace: React.FC = () => {
  return (
    <WorkspacePlaceholder
      icon={ListTodo}
      title="Jobs"
      description="Monitor and manage extraction job queue"
      pattern="Monitor → approve → investigate"
      features={[
        {
          label: 'Queue view',
          description: 'See pending and running jobs',
        },
        {
          label: 'History view',
          description: 'Browse completed and failed jobs',
        },
        {
          label: 'Job details',
          description: 'View progress, logs, and results',
        },
        {
          label: 'Approve/cancel actions',
          description: 'Control job execution',
        },
        {
          label: 'Filter by status, ontology, date',
          description: 'Find specific jobs quickly',
        },
      ]}
    />
  );
};
