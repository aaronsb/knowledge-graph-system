/**
 * Workspace Placeholder Component
 *
 * Structured placeholder for workspace pages showing intended layout.
 * Used during Phase 1 to prove navigation works.
 */

import React from 'react';

interface PlaceholderFeature {
  label: string;
  description: string;
}

interface WorkspacePlaceholderProps {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  features: PlaceholderFeature[];
  pattern?: string;
}

export const WorkspacePlaceholder: React.FC<WorkspacePlaceholderProps> = ({
  icon: Icon,
  title,
  description,
  features,
  pattern,
}) => {
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b border-border bg-card p-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-primary/10 rounded-lg">
            <Icon className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold">{title}</h1>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
        {pattern && (
          <div className="mt-3 text-xs text-muted-foreground">
            <span className="font-medium">Pattern:</span> {pattern}
          </div>
        )}
      </div>

      {/* Placeholder Content */}
      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-2xl mx-auto">
          <div className="bg-muted/30 border border-dashed border-border rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Planned Features</h2>
            <div className="space-y-3">
              {features.map((feature, index) => (
                <div key={index} className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-xs font-medium text-muted-foreground">
                      {index + 1}
                    </span>
                  </div>
                  <div>
                    <div className="font-medium text-sm">{feature.label}</div>
                    <div className="text-xs text-muted-foreground">
                      {feature.description}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            <p>This workspace is under development.</p>
            <p className="mt-1">See ADR-067 for architecture details.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
