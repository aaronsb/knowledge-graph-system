# Polarity Axis Analysis

Discover where concepts fall on semantic spectrums.

## What It Does

Polarity axis analysis lets you explore bidirectional dimensions in your knowledge graph. Define two opposing concepts as poles (like *Modern* ↔ *Traditional*), and the system projects other concepts onto that axis to show where they fall.

## Example

**Question:** Where does "Agile" fall on the Modern ↔ Traditional spectrum?

```
Traditional ●────────────────────────────────● Modern
                         │
                       Agile (+0.19)
```

The system shows Agile leans toward the Modern pole, with a position score that correlates with its grounding strength—validating it as a modern, well-supported practice.

## Key Capabilities

- **Semantic Positioning** — See where any concept falls on a conceptual spectrum
- **Axis Discovery** — Auto-discover implicit dimensions from opposing relationships
- **Synthesis Detection** — Find "middle ground" concepts that integrate both poles
- **Grounding Correlation** — Validate axes by measuring alignment with evidence strength

## Use Cases

- **Framework Comparison** — Where do methodologies fall on Centralized ↔ Distributed?
- **Value Analysis** — Which concepts align with desirable outcomes?
- **Gap Discovery** — Find synthesis concepts that bridge opposing viewpoints
- **Trend Mapping** — Track how concepts position on Emerging ↔ Established

## Clients

| Client | Support |
|--------|---------|
| API | `POST /queries/polarity-axis` |
| CLI | `kg polarity analyze <from> <to>` |
| MCP | `analyze_polarity_axis` tool |
| Web | Polarity Axis Explorer workspace |

## Related

- [ADR-070: Polarity Axis Analysis](../../architecture/ai-embeddings/ADR-070-polarity-axis-analysis.md) — Architecture decision
- [ADR-058: Polarity Axis Triangulation](../../architecture/ai-embeddings/ADR-058-polarity-axis-triangulation.md) — Grounding calculation foundation
