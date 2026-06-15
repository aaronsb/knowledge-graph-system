---
status: Draft
date: 2026-05-19
deciders:
  - aaronsb
  - claude
related:
  - ADR-800
  - ADR-805
  - ADR-806
  - ADR-810
---

# ADR-801: Uniform Provider Configuration Contract

## Context

ADR-800 specified the dynamic model catalog and OpenRouter support — *what
models exist* is no longer hardcoded. It deliberately left open *how an
operator configures and selects a provider*: the per-provider connectivity,
reasoning controls, and persistence model were unknown and could not be
designed on paper. We chose to **experiment first and write this ADR from
the findings** rather than guess the contract up front. This ADR records the
contract that the experiment converged on; it extends ADR-800 rather than
modifying it (ADR-800 is Accepted — its decision history is preserved).

The experiment surfaced concrete failures that drive the decisions below:

- Provider configuration was effectively a single global "active config"
  row. Saving provider B's settings meant losing provider A's. The UI was
  hardcoded to an openai/anthropic pair and could not show an
  operator-configured provider (e.g. OpenRouter) at all.
- Activating a provider, or saving one field, **nulled the rest of that
  provider's row** (`exclude_none=True` upstream → missing field → `NULL`
  written). This is the bug class that made a configured local endpoint
  silently revert to `localhost:8080`.
- A containerised API cannot reach a local inference server on host
  loopback: the host's INPUT firewall drops bridge-network traffic. The
  provider was unreachable until the topology changed.
- The "no hardcoded models" intent of ADR-800 had **regressed in places**:
  `AnthropicProvider` returned a static Claude-3 list; `OpenAIProvider`
  allowlisted a few name fragments. Both hid newer models.

## Decision

A reasoning provider is defined by a **uniform contract of four surfaces**.
Every connector implements all four; the UI and routes are provider-agnostic.

### 1. Four uniform surfaces

Every provider exposes, by the same interface:

1. **Validate** — model-agnostic connectivity/auth (`validate_provider_key`),
   never dependent on a specific model id, never raising.
2. **Enumerate** — `fetch_model_catalog()` lists models from the provider's
   own API. Enumeration *is* the connectivity test.
3. **Reasoning controls** — temperature and max-output-tokens, with sane KG
   defaults, persisted per provider.
4. **Persisted per-provider config** — base_url / model / reasoning params
   stored in the database.

The UI renders one card per provider from `/admin/providers` metadata
(`requires_key`, `is_local`). Field visibility is data-driven (key row vs.
endpoint row) — **never a provider-specific code branch**. Adding a provider
is a connector + a metadata row, not UI surgery.

### 2. Per-provider config is decoupled from the active pointer

`kg_api.ai_extraction_config` holds **one row per provider**
(`UNIQUE(provider)`). `active` is a single live-flag identifying the
provider used for extraction — it is *not* coupled to provider identity or
to whether a provider may be configured. A provider can be fully configured
and saved while another remains active. The schema constraint is the
decision.

### 3. Partial-save preservation is a persistence-layer invariant

`save_extraction_config` upserts `ON CONFLICT (provider)` and **COALESCEs
every optional field against the stored value**. An omitted field is left
alone, never nulled. This invariant lives at the persistence layer, not
threaded through each caller.

> **Principle (send-only-what-changed):** Any endpoint or caller may persist
> a partial provider config. Absent fields retain their stored value;
> brand-new rows fall to column defaults. Callers must not be required to
> re-send the whole row to avoid data loss.

`model_name` is special-cased — `COALESCE(NULLIF(EXCLUDED.model_name,''),
stored)` — so the empty-string new-row sentinel never overwrites a real
model.

### 4. Local inference servers join the API's docker network

A local inference server (llama.cpp, Ollama) is reached **by docker-network
service name**, exactly as the API reaches Postgres/Garage — not via host
loopback. Host-loopback is rejected: the host firewall drops bridge→host
traffic, so loopback is unreliable by construction, not by misconfiguration.
The persisted `base_url` therefore holds a service-name URL
(e.g. `http://kg-llamacpp:8080/v1`). Hardware passthrough and bring-up of
that container is environment-specific operational knowledge and lives in
the operator way, not here.

### Reaffirmation, not new decision

The Anthropic SDK-enumeration and OpenAI allowlist→denylist fixes restore
ADR-800's existing "no hardcoded model lists" decision where it had
regressed. They are recorded as confirmation of ADR-800, not as new
architecture: enumerate via the provider SDK/API and exclude only *known*
non-extraction families, so new model generations appear with no code
change.

## Consequences

### Positive

- The database is a **two-way source of truth**: a `GET` mirrors the `POST`,
  so every provider card pre-populates from what is actually persisted
  rather than from defaults. (This is a consequence of decisions 2 + 3, not
  a separate decision.)
- Adding a provider is connector + metadata only — no UI or route changes.
- The partial-save invariant makes whole classes of "save wiped my config"
  bugs structurally impossible for present and future callers.
- New model generations surface automatically (decision-reaffirmation).

### Negative

- The persistence layer carries non-obvious COALESCE/NULLIF logic; the
  send-only-what-changed principle must be understood before adding columns
  (a column added without a COALESCE branch reintroduces the bug class).
- Local-provider use requires the inference server to be on the API's docker
  network — a host-installed server is not directly usable without joining
  it.

### Neutral

- `vllm` remains an `EXTRACTION_PROVIDERS` placeholder with no connector; it
  is omitted from `/admin/providers` until one exists (every card maps to a
  working surface).
- Reasoning controls are temperature + max_tokens only. A provider-specific
  context-length (num_ctx) knob was deliberately excluded: no column exists,
  and it is a no-op for cloud providers. Adding it later is a schema +
  contract change, scoped separately.

## Alternatives Considered

- **Thread every field through every caller** (instead of COALESCE at the
  persistence layer). Rejected: it only fixes the one caller you remember;
  the bug class returns with the next partial-save endpoint.
- **Mutate ADR-800 to add this contract.** Rejected: ADR-800 is Accepted;
  overwriting it destroys the decision-history friction. ADR-801 extends it.
- **Host-loopback for local providers with a firewall rule.** Rejected:
  fragile and host-specific; the docker-network pattern is how every other
  service dependency already works.
- **Per-provider-shaped UI cards** (distinct cloud vs. local components).
  Rejected: divergent code paths drift; one metadata-driven card shape is
  the contract's UI expression.
</content>
