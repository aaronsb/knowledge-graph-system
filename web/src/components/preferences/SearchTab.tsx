/**
 * Search Tab
 *
 * Search result display preferences.
 */

import React from 'react';
import {
  Search,
  FileText,
  Image,
  ListOrdered,
} from 'lucide-react';
import { usePreferencesStore } from '../../store/preferencesStore';
import { Section, Toggle, NumberInput } from './components';

export const SearchTab: React.FC = () => {
  const { search, updateSearchPreferences } = usePreferencesStore();

  return (
    <Section title="Search Results" icon={<Search className="w-5 h-5" />}>
      <Toggle
        enabled={search.showEvidenceQuotes}
        onChange={(v) => updateSearchPreferences({ showEvidenceQuotes: v })}
        label="Show evidence quotes"
        description="Display supporting quotes from source documents"
        icon={<FileText className="w-4 h-4" />}
      />
      <Toggle
        enabled={search.showImagesInline}
        onChange={(v) => updateSearchPreferences({ showImagesInline: v })}
        label="Show images inline"
        description="Display images directly in search results"
        icon={<Image className="w-4 h-4" />}
      />
      <NumberInput
        value={search.defaultResultLimit}
        onChange={(v) => updateSearchPreferences({ defaultResultLimit: v })}
        min={5}
        max={100}
        step={5}
        label="Default result limit"
        description="Maximum number of results to show"
        icon={<ListOrdered className="w-4 h-4" />}
      />
    </Section>
  );
};

export default SearchTab;
