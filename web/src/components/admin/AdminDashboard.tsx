/**
 * Admin Dashboard
 *
 * Platform administration interface.
 */

import React from 'react';
import { Shield } from 'lucide-react';
import { WorkspacePlaceholder } from '../shared/WorkspacePlaceholder';

export const AdminDashboard: React.FC = () => {
  return (
    <WorkspacePlaceholder
      icon={Shield}
      title="Admin"
      description="Platform configuration and security management"
      pattern="Configure → monitor → secure"
      features={[
        {
          label: 'OAuth client management',
          description: 'Register clients, view/revoke tokens, configure scopes',
        },
        {
          label: 'User management',
          description: 'Create/edit users, assign roles',
        },
        {
          label: 'Published flow management',
          description: 'View all published flows, revoke access, usage analytics',
        },
        {
          label: 'System status',
          description: 'Database stats, embedding status, AI provider status',
        },
      ]}
    />
  );
};
