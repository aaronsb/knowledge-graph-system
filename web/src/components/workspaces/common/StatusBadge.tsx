/**
 * StatusBadge - Job status indicator with icon and color
 *
 * Displays job status consistently across all workspace components.
 * Follows ADR-014 job lifecycle states.
 */

import React from 'react';
import {
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Pause,
  Ban,
  Circle,
  HelpCircle,
} from 'lucide-react';
import type { JobStatusValue } from '../../../types/jobs';

interface StatusBadgeProps {
  status: JobStatusValue;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

const statusConfig: Record<JobStatusValue, {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  bgClass: string;
  textClass: string;
  iconClass: string;
}> = {
  completed: {
    icon: CheckCircle2,
    label: 'Completed',
    bgClass: 'bg-green-100 dark:bg-green-900/30',
    textClass: 'text-green-800 dark:text-green-300',
    iconClass: 'text-green-600 dark:text-green-400',
  },
  failed: {
    icon: XCircle,
    label: 'Failed',
    bgClass: 'bg-red-100 dark:bg-red-900/30',
    textClass: 'text-red-800 dark:text-red-300',
    iconClass: 'text-red-600 dark:text-red-400',
  },
  processing: {
    icon: Loader2,
    label: 'Processing',
    bgClass: 'bg-blue-100 dark:bg-blue-900/30',
    textClass: 'text-blue-800 dark:text-blue-300',
    iconClass: 'text-blue-600 dark:text-blue-400 animate-spin',
  },
  approved: {
    icon: CheckCircle2,
    label: 'Approved',
    bgClass: 'bg-emerald-100 dark:bg-emerald-900/30',
    textClass: 'text-emerald-800 dark:text-emerald-300',
    iconClass: 'text-emerald-600 dark:text-emerald-400',
  },
  awaiting_approval: {
    icon: Pause,
    label: 'Awaiting Approval',
    bgClass: 'bg-amber-100 dark:bg-amber-900/30',
    textClass: 'text-amber-800 dark:text-amber-300',
    iconClass: 'text-amber-600 dark:text-amber-400',
  },
  pending: {
    icon: Circle,
    label: 'Pending',
    bgClass: 'bg-gray-100 dark:bg-gray-700/50',
    textClass: 'text-gray-600 dark:text-gray-300',
    iconClass: 'text-gray-400 dark:text-gray-500',
  },
  queued: {
    icon: Clock,
    label: 'Queued',
    bgClass: 'bg-indigo-100 dark:bg-indigo-900/30',
    textClass: 'text-indigo-800 dark:text-indigo-300',
    iconClass: 'text-indigo-600 dark:text-indigo-400',
  },
  cancelled: {
    icon: Ban,
    label: 'Cancelled',
    bgClass: 'bg-gray-100 dark:bg-gray-700/50',
    textClass: 'text-gray-500 dark:text-gray-400',
    iconClass: 'text-gray-400 dark:text-gray-500',
  },
};

const sizeConfig = {
  sm: {
    iconSize: 'w-3 h-3',
    padding: 'px-1.5 py-0.5',
    text: 'text-xs',
    gap: 'gap-1',
  },
  md: {
    iconSize: 'w-4 h-4',
    padding: 'px-2 py-1',
    text: 'text-sm',
    gap: 'gap-1.5',
  },
  lg: {
    iconSize: 'w-5 h-5',
    padding: 'px-3 py-1.5',
    text: 'text-base',
    gap: 'gap-2',
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
  showLabel = true,
  className = '',
}) => {
  const config = statusConfig[status] || {
    icon: HelpCircle,
    label: status,
    bgClass: 'bg-gray-100 dark:bg-gray-700',
    textClass: 'text-gray-600 dark:text-gray-300',
    iconClass: 'text-gray-400',
  };

  const sizeStyles = sizeConfig[size];
  const Icon = config.icon;

  return (
    <span
      className={`
        inline-flex items-center ${sizeStyles.gap}
        ${sizeStyles.padding} ${sizeStyles.text}
        ${config.bgClass} ${config.textClass}
        rounded-full font-medium
        ${className}
      `}
    >
      <Icon className={`${sizeStyles.iconSize} ${config.iconClass}`} />
      {showLabel && <span>{config.label}</span>}
    </span>
  );
};

// Compact version - just icon
export const StatusIcon: React.FC<{
  status: JobStatusValue;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}> = ({ status, size = 'md', className = '' }) => {
  return <StatusBadge status={status} size={size} showLabel={false} className={className} />;
};

export default StatusBadge;
