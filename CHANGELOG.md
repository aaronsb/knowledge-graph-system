# Changelog

What each platform release contains, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), with an **Upgrade
notes** group first: what an operator must do, or should know, before
upgrading. Versions follow [Semantic Versioning](https://semver.org/). The CLI
(`@aaronsb/kg-cli`) and FUSE driver (`kg-fuse`) version independently; an entry
names their versions when they ship with the release.

Entries are written when a release is cut, from the commits and pull requests
since the previous tag. `./publish.sh release` refuses to tag a version that has
no entry here, and `./publish.sh gh-release` uses the entry as the GitHub
release notes.

## [0.19.0] - 2026-09-26

CLI 0.15.1.

### Upgrade notes

- **Upgrade from 0.18.0 if you use Ollama, OpenRouter or llama.cpp.** The 0.18.0
  API image shipped without the `requests` package, so those providers failed at
  runtime with `ModuleNotFoundError`. They now use `httpx`.
- **Extraction output budgets follow the configured `max_tokens`.** Providers
  used to hardcode their own (OpenAI 4096, Anthropic 16384; llama.cpp inherited
  OpenAI's). The configured value now applies to every provider, capped at the
  model's limit from the model catalog. Installs still carrying the seeded
  `max_tokens` of 16384 let OpenAI extraction produce up to 16384 output tokens,
  up from 4096.
- **Refresh the model catalog after upgrading** (AI Providers → *Get models*, or
  `POST /admin/models/catalog/refresh`). Anthropic, Ollama and llama.cpp entries
  now record real context and output limits and capabilities.

### Added

- The model catalog records each model's real limits and capabilities:
  Anthropic from the Models API (`max_input_tokens`, `max_tokens`,
  `capabilities`), Ollama from `/api/show`, llama.cpp from `/props`. OpenAI's
  output limits come from a known-limits table, since its API reports none.
- The AI Providers card shows the active model's context window and maximum
  output next to the configured max tokens.
- `/database/info` reports the Apache AGE version.
- Dev mode hot-reloads the API (`uvicorn --reload`, watching `api/`), and
  `./operator.sh start` rebuilds the web dev image and renews its
  `node_modules` volume, so dependency changes reach the Vite server.

### Changed

- Model capabilities shown for the active extraction model (vision, JSON mode)
  come from the model catalog. The flag stored with the extraction config is
  only a fallback for models the catalog does not list.
- OpenAI calls send `max_completion_tokens`, which the o-series and gpt-5
  reasoning models require.
- Ollama models that report both completion and vision (for example gemma3,
  qwen2.5vl, moondream) are listed as extraction and vision models; vision is
  detected from the model's capabilities, not its name.

### Fixed

- The AI Providers card showed **Vision: No** for vision-capable models, and
  every save reset the flag.
- Disabled accounts could still use the `/query-definitions` endpoints.
- The operator accepted any string as an OpenRouter API key.
- `/database/query` called a helper that did not exist; rows are returned as
  parsed.
- `cd cli && npm run build` left 43 generated doc pages untracked in the working
  tree, and `npm run docs:check` pointed at a deleted file.
- The web dev container kept Tailwind 3 after the Tailwind 4 migration, which
  broke the Vite dev server.

### Removed

- The unused `api/app/middleware` package, whose placeholder `get_current_user`
  was easy to import by mistake in place of the real dependency.
- The `requests` dependency.
