/**
 * Ingest Tab
 *
 * Default settings for document ingestion.
 */

import React, { useState, useEffect } from 'react';
import {
  Upload,
  CheckCircle2,
  Folder,
  Layers,
  Zap,
} from 'lucide-react';
import { usePreferencesStore } from '../../store/preferencesStore';
import { apiClient } from '../../api/client';
import type { OntologyItem } from '../../types/ingest';
import { Section, Toggle, Select, NumberInput } from './components';

export const IngestTab: React.FC = () => {
  const { ingest, updateIngestDefaults } = usePreferencesStore();

  // Ontologies for default ontology selector
  const [ontologies, setOntologies] = useState<OntologyItem[]>([]);

  // Load ontologies (only when authenticated)
  useEffect(() => {
    apiClient.listOntologies()
      .then((response) => setOntologies(response.ontologies || []))
      .catch(() => {
        // Silently fail if not authenticated yet
        setOntologies([]);
      });
  }, []);

  return (
    <Section title="Ingest Defaults" icon={<Upload className="w-5 h-5" />}>
      <Toggle
        enabled={ingest.autoApprove}
        onChange={(v) => updateIngestDefaults({ autoApprove: v })}
        label="Auto-approve jobs"
        description="Start processing immediately without review"
        icon={<CheckCircle2 className="w-4 h-4" />}
      />
      <Select
        value={ingest.defaultOntology}
        onChange={(v) => updateIngestDefaults({ defaultOntology: v })}
        options={[
          { value: '', label: 'None (select each time)' },
          ...ontologies.map((o) => ({ value: o.ontology, label: o.ontology })),
        ]}
        label="Default ontology"
        description="Pre-selected ontology for new ingestions"
        icon={<Folder className="w-4 h-4" />}
      />
      <NumberInput
        value={ingest.defaultChunkSize}
        onChange={(v) => updateIngestDefaults({ defaultChunkSize: v })}
        min={200}
        max={3000}
        step={100}
        label="Default chunk size"
        description="Target words per chunk (200-3000)"
        icon={<Layers className="w-4 h-4" />}
      />
      <Select
        value={ingest.defaultProcessingMode}
        onChange={(v) => updateIngestDefaults({ defaultProcessingMode: v as 'serial' | 'parallel' })}
        options={[
          { value: 'serial', label: 'Serial (reliable)' },
          { value: 'parallel', label: 'Parallel (faster)' },
        ]}
        label="Processing mode"
        description="How chunks are processed"
        icon={<Zap className="w-4 h-4" />}
      />
    </Section>
  );
};

export default IngestTab;
