/**
 * Vision Provider Card (ADR-802)
 *
 * Manages the active vision (image->prose) provider — the reasoning capability
 * behind multimodal image ingestion. Self-contained: fetches its own vision
 * config + capability metadata so it can drop into the System tab without
 * growing it. Data-driven from /admin/vision/providers (no hardcoded provider
 * list); vision is resolved independently (active vision config → active
 * extraction provider if vision-capable → fail loud).
 */

import React, { useEffect, useState } from 'react';
import { Eye, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { apiClient } from '../../api/client';
import { Section } from './components';

interface VisionProviderMeta {
  provider: string;
  supports_vision: boolean;
  vision_models: string[];
}

interface VisionEffective {
  provider: string | null;
  model: string | null;
  source: string;
}

export const VisionProviderCard: React.FC<{ onError?: (msg: string) => void }> = ({ onError }) => {
  const [loading, setLoading] = useState(true);
  const [providers, setProviders] = useState<VisionProviderMeta[]>([]);
  const [effective, setEffective] = useState<VisionEffective | null>(null);
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  const load = async () => {
    try {
      const [provResp, detail] = await Promise.all([
        apiClient.getVisionProviders(),
        apiClient.getVisionConfigDetail(),
      ]);
      setProviders(provResp.providers);
      setEffective(detail.effective);
      setActiveProvider(detail.config?.provider ?? null);
      // Seed each provider's model draft. Always re-sync the ACTIVE provider's
      // draft to what's persisted (the server may resolve/normalize the model
      // id); leave untouched drafts for inactive providers alone.
      setDrafts((prev) => {
        const next = { ...prev };
        for (const p of provResp.providers) {
          const isActive = detail.config?.provider === p.provider;
          if (isActive && detail.config?.model_name) {
            next[p.provider] = detail.config.model_name;
          } else if (next[p.provider] === undefined) {
            next[p.provider] = p.vision_models[0] || '';
          }
        }
        return next;
      });
    } catch (err: any) {
      onError?.(err?.response?.data?.detail || err?.message || 'Failed to load vision config');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleActivate = async (provider: string) => {
    setSaving(provider);
    try {
      const model = drafts[provider] || undefined;
      await apiClient.updateVisionConfig({ provider, model_name: model, active: true });
      await load();
    } catch (err: any) {
      onError?.(err?.response?.data?.detail || err?.message || 'Failed to set vision provider');
    } finally {
      setSaving(null);
    }
  };

  return (
    <Section title="Vision (Image → Prose)" icon={<Eye className="w-5 h-5" />}>
      <p className="text-sm text-muted-foreground mb-4">
        The vision provider converts images to literal prose, which is then
        extracted into concepts like any other text (the hairpin). Resolved
        independently of extraction; if unset it inherits the active extraction
        provider when that provider has a vision-capable model.
      </p>

      {loading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="w-6 h-6 text-primary animate-spin" />
        </div>
      ) : (
        <>
          {/* Effective resolution banner */}
          <div className="mb-4 p-3 rounded-lg bg-muted/50 border border-border text-sm">
            {effective?.provider ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Effective:</span>
                <span className="font-medium text-foreground capitalize">{effective.provider}</span>
                <span className="font-mono text-xs text-muted-foreground">{effective.model || '(catalog default)'}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">{effective.source}</span>
              </div>
            ) : (
              <span className="flex items-center gap-1 text-status-warning">
                <AlertCircle className="w-4 h-4" /> No vision provider resolves — set one below or configure a vision-capable extraction provider.
              </span>
            )}
            {effective?.source === 'extraction_default' && (
              <p className="mt-1 text-xs text-muted-foreground">
                No explicit vision provider set — inheriting the active extraction provider.
              </p>
            )}
          </div>

          <div className="space-y-3">
            {providers.map((p) => {
              const isActive = activeProvider === p.provider;
              const capable = p.supports_vision;
              return (
                <div
                  key={p.provider}
                  className={`p-4 rounded-lg border ${isActive ? 'border-status-active bg-status-active/5' : 'border-border bg-muted/50'}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-foreground capitalize">{p.provider}</span>
                    {isActive ? (
                      <span className="flex items-center gap-1 text-status-active text-xs font-medium">
                        <CheckCircle className="w-4 h-4" /> Active for vision
                      </span>
                    ) : !capable ? (
                      <span className="text-xs text-muted-foreground">No vision model in catalog</span>
                    ) : null}
                  </div>

                  <div className="flex items-center justify-between gap-3">
                    <select
                      className="flex-1 min-w-0 px-2 py-1 text-sm bg-background border border-border rounded text-foreground disabled:opacity-50"
                      value={drafts[p.provider] ?? ''}
                      disabled={!capable || saving === p.provider}
                      onChange={(e) => setDrafts((d) => ({ ...d, [p.provider]: e.target.value }))}
                    >
                      {p.vision_models.length === 0 ? (
                        <option value="">(no vision model in catalog — add one via AI Providers)</option>
                      ) : (
                        p.vision_models.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))
                      )}
                    </select>
                    <button
                      onClick={() => handleActivate(p.provider)}
                      disabled={!capable || saving === p.provider}
                      title={capable ? `Use ${p.provider} for vision` : 'No vision-capable model in the catalog'}
                      className="px-3 py-1 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
                    >
                      {saving === p.provider ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : isActive ? 'Re-apply' : 'Activate'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </Section>
  );
};
