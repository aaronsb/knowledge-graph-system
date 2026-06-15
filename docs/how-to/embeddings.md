---
id: 8.H.02
domain: ai
mode: how-to
---

# Configure Embeddings

Kappa Graph stores concepts as embedding vectors for similarity search. Embeddings are managed through profiles — each profile bundles a provider, model, dimensions, precision, and resource settings. One profile is active at a time.

Configure embeddings via:

```bash
./operator.sh embedding
```

This opens the configuration shell for embedding-specific options. Embedding profiles can also be managed directly with `kg admin embedding` subcommands.

---

## Providers

| Provider | Model example | Dimensions |
|---|---|---|
| `openai` | `text-embedding-3-small` | 1536 |
| `local` | `nomic-ai/nomic-embed-text-v1.5` | 768 |

OpenAI uses API-based inference. Local uses sentence-transformers; the model downloads from HuggingFace on first load.

---

## List profiles

```bash
kg admin embedding list
```

Output:

```
  ACTIVE Config 1 [DC]
    ID:           1
    Vector Space: cosine
    Text:         openai / text-embedding-3-small
      Dims:       1536  Loader: auto
    Image:        (none)
    Protection:   delete-protected, change-protected
    Updated: 10/22/2025, 9:06:23 AM by system

  Inactive Config 2
    ID:           2
    Vector Space: cosine
    Text:         local / nomic-ai/nomic-embed-text-v1.5
      Dims:       768  Loader: auto
    Image:        (none)
    Updated: 10/21/2025, 3:45:12 PM by admin
```

Labels: `ACTIVE` — currently active profile. `Inactive` — not active. `[D]` — delete-protected. `[C]` — change-protected. `[DC]` — both flags set.

---

## Protection flags

Changing embedding dimensions breaks all existing vector search results — every stored concept embedding becomes incompatible with the new dimension space.

Two protection flags prevent accidents:

- **Delete protection** (`delete_protected`) — prevents deletion of the profile.
- **Change protection** (`change_protected`) — prevents changing the provider or dimensions. Auto-enabled after a successful hot reload.

The default OpenAI profile ships with both flags set. Remove a flag explicitly before making the corresponding change.

---

## Switch providers

This is the safe workflow for switching between providers or changing dimensions.

**Step 1 — Remove change protection from the active profile:**

```bash
kg admin embedding unprotect <active-id> --change
```

**Step 2 — Create a new profile:**

```bash
# OpenAI
kg admin embedding create \
  --provider openai \
  --model text-embedding-3-small \
  --dimensions 1536

# Local (full resource config)
kg admin embedding create \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768 \
  --precision float16 \
  --device cpu \
  --memory 512 \
  --threads 4 \
  --batch-size 8
```

**Step 3 — Activate the new profile:**

```bash
kg admin embedding activate <new-profile-id>
```

**Step 4 — Hot reload the embedding worker:**

```bash
kg admin embedding reload
```

Reload is zero-downtime: the new model loads in parallel, then swaps in atomically. In-flight requests complete against the old model. Change protection is automatically re-enabled on the newly active profile after a successful reload.

**Step 5 — Verify:**

```bash
kg admin embedding list
```

The new profile shows `ACTIVE` and `[C]`.

**After a dimension change:** existing concept embeddings are incompatible with the new dimensions. Re-ingest your data to rebuild embeddings.

```bash
# Re-ingest a specific ontology
kg ontology delete "My Ontology"
kg ingest file -o "My Ontology" -y document.txt

# Full reset (re-ingest everything)
kg admin reset
```

---

## Adjust local model resource tuning

To change memory, threads, or batch size without changing the provider or dimensions, create a new profile with updated resource values, activate it, and reload. There is no in-place update — use `create` + `activate` + `reload`.

```bash
kg admin embedding create \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768 \
  --precision float16 \
  --memory 256 \
  --batch-size 4
kg admin embedding activate <new-id>
kg admin embedding reload
```

---

## Manage protection

```bash
# Enable protection flags
kg admin embedding protect <id> --change
kg admin embedding protect <id> --delete --change

# Remove protection flags
kg admin embedding unprotect <id> --change
kg admin embedding unprotect <id> --delete
```

---

## Delete a profile

```bash
# Remove delete protection first if set
kg admin embedding unprotect <id> --delete

# Delete (prompts for confirmation)
kg admin embedding delete <id>
```

The default OpenAI profile is delete-protected by default. Keep it; it serves as a rollback target.

---

## Command reference

| Task | Command |
|---|---|
| List all profiles | `kg admin embedding list` |
| Create a profile | `kg admin embedding create [OPTIONS]` |
| Activate a profile | `kg admin embedding activate <id>` |
| Hot reload worker | `kg admin embedding reload` |
| Enable protection | `kg admin embedding protect <id> --change --delete` |
| Remove protection | `kg admin embedding unprotect <id> --change` |
| Export profile to JSON | `kg admin embedding export <id>` |
| Delete a profile | `kg admin embedding delete <id>` |

---

## Troubleshooting

**Error: "Active config is change-protected"**

Remove change protection before switching providers or dimensions:

```bash
kg admin embedding unprotect <id> --change
```

Then create a new profile, activate it, and reload.

**Hot reload shows wrong provider**

Confirm the new profile is active before reloading:

```bash
kg admin embedding list
kg admin embedding reload
kg admin embedding list
```

**Vector search returns wrong results after a dimension change**

The dimensions changed but the stored embeddings were not rebuilt. Re-ingest your data (see above).

**Local model download fails**

Use the full HuggingFace model identifier: `nomic-ai/nomic-embed-text-v1.5`, not `nomic-embed-text`. Verify network access to `huggingface.co` from the server.

**OOM during local model load**

Reduce memory or precision:

```bash
kg admin embedding create \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768 \
  --precision float16 \
  --memory 256 \
  --batch-size 4
kg admin embedding activate <new-id>
kg admin embedding reload
```
