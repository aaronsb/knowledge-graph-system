# What Is This?

You give it documents. It finds the ideas, connects them, and remembers what contradicts what.

## The 30-Second Version

Feed the system your documents - research papers, notes, articles, reports. It reads them and extracts the key ideas. Then it connects those ideas: this concept *supports* that one, this claim *contradicts* that one, this cause *leads to* that effect.

Unlike a search engine that just finds keywords, this system understands meaning. Ask "what causes inflation?" and it finds concepts related to inflation's causes - even if those exact words don't appear in your documents.

Unlike a chatbot that makes things up, every idea traces back to its source. You can always ask "where did this come from?" and get a real answer.

## The Real Point

This isn't just a search tool for humans. It's infrastructure for AI that can reason about what it knows.

Most AI "memory" is just similarity search - find things that look like what you asked for. This system tracks:

- **Grounding**: How well-supported is this idea? One source or twenty?
- **Contradiction**: Do sources disagree? Which ones?
- **Provenance**: Where exactly did this idea come from?

That's the foundation for AI that doesn't just retrieve information but *reasons about how reliable it is*.

Current state: AI assistants can query the system via standard protocols (MCP).
Future state: The knowledge graph becomes part of how AI thinks, not just something it queries.

## What Can You Do With It?

**As a human:**
- Search your documents by meaning, not just keywords
- See how ideas connect across different sources
- Find where your sources contradict each other
- Trace any claim back to its origin

**As an AI agent:**
- Query persistent memory that survives across sessions
- Get grounded answers with confidence levels
- Reason about contradictions and uncertainty
- Build knowledge incrementally over time

## Next Steps

- [How It Works](how-it-works.md) - The conceptual model (still no code)
- [Glossary](glossary.md) - Terms explained in plain language
- [Using the System](../using/README.md) - Getting started as a user
- [Operating the System](../operating/README.md) - Deploying and maintaining
