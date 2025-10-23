# Documentation Writing Guidelines

These guidelines ensure consistent tone, quality, and authenticity across the Knowledge Graph System documentation.

---

## Core Principles

### 0. Primary Purpose: Clarity and Utility

The documentation exists to:
1. **Explain concepts** - What is this thing?
2. **Show how it works** - What's happening under the hood?
3. **Teach usage** - How do I actually use it?
4. **Extract value** - Why would I care? What can I do with this?

Everything else—humor, analogies, theory—serves these goals. Don't write to excite the reader. Write to **inform** the reader.

### 1. Avoid AI Constructivism

**Don't do this:**
- "It's not X, it's Y" framing
- Hype language or breathless claims
- "Revolutionary" or "paradigm-shifting" rhetoric
- Artificial enthusiasm

**Instead:**
- State what things are, directly
- Use concrete examples
- Acknowledge limitations honestly
- Let the reader decide the value

**Example - Bad:**
```
Traditional systems are broken! They can't handle real knowledge!
Knowledge graphs are revolutionary and will change everything!
```

**Example - Good:**
```
RAG systems work well for one-off queries. Knowledge graphs work
better when you need to explore relationships and accumulate
knowledge over time. Different tools for different jobs.
```

### 2. Humor and Analogies - Use Sparingly

The main goal is **explaining concepts clearly**. Humor and analogies are tools to aid understanding, not entertainment.

**When to use:**
- When an analogy genuinely clarifies a complex idea
- When humor makes a technical point memorable
- When it helps the reader connect to their own experience

**When NOT to use:**
- Don't force humor into every section
- Don't use analogies when direct explanation is clearer
- Don't entertain at the expense of clarity

**Example - Good (helps understanding):**
```
The LLM sometimes extracts "The Importance of Being Ernest" as three
separate concepts. This happens when context boundaries aren't clear
to the model.
```

**Example - Too Much:**
```
The LLM will hilariously extract "The Importance of Being Ernest" as
three separate concepts: "Importance", "Being", and "Ernest". This
is like asking your grandfather about his childhood and getting a
45-minute story about onions and how they cost a nickel. The point
is, extraction isn't perfect—much like Grandpa's memory!
```

### 3. Ground Concepts in Theory

When exploring ideas, connect to established theory:

- **Information Theory** (Shannon): Serialization requires compression and loss
- **Systems Thinking** (Ashby's Law): Requisite variety affects extraction quality
- **Cognitive Science**: Human attention as spotlight vs. ambient awareness
- **Graph Theory**: What makes graph structures powerful vs. linear

**Example - Good:**
```
Why does linear reading feel limiting? Shannon's information theory
tells us that serializing knowledge (turning a graph into a sequence)
requires lossy compression. You're forcing a multidimensional
structure through a one-dimensional channel. The graph is trying to
be "all over" like the world actually is, but text forces it into
a single path.

Ashby's Law (requisite variety) applies to extraction: your model's
conceptual variety must match the text's conceptual variety. A simple
model will extract simple concepts. A nuanced model will catch nuance.
```

### 4. Avoid Philosophical Abstraction

**Don't:**
- Deep dives into epistemology
- Abstract philosophy without grounding
- Quoting philosophers without context

**Do:**
- Use theory to explain practical behavior
- Connect abstract concepts to system features
- Stay application-focused

**Example - Bad:**
```
As Heidegger noted, being-in-the-world is fundamentally different
from Cartesian subject-object dualism...
```

**Example - Good:**
```
The Alan Watts lectures talk about how human attention works like
a spotlight—focused on one thing at a time. But the world is "all over"
simultaneously (a graph!). This is why graph traversal feels more natural
than linear reading: you can explore in multiple directions, like actual
thinking works.
```

---

## Tone Guidelines

### Direct and Practical
- Use second person ("you") when guiding the reader
- Active voice preferred over passive
- Short sentences and paragraphs
- Code examples where helpful

### Honest About Limitations
- State what doesn't work
- Admit when things are experimental
- Don't oversell capabilities
- Provide realistic use cases

### Technical Without Jargon
- Define terms before using them
- Use analogies for complex concepts
- Assume smart reader, not expert reader
- Link to deeper explanations rather than inline digressions

---

## Structure Patterns

### Each Section Should Have:

1. **Clear Goal Statement**: What will the reader learn or be able to do?
2. **Context**: Why does this matter? What problem does it solve?
3. **Concrete Examples**: Show, don't just tell
4. **Practical Application**: How do you actually use this?
5. **Next Steps**: Where to go from here?

### Avoid:
- Walls of text (break up with subheadings)
- Overly long sections (split into multiple numbered sections)
- Orphaned concepts (always link to related sections)
- **Long bullet lists**: Use paragraphs for discussion, lists only when truly listing discrete items

### When Writing Guides:
Use code blocks for commands the user should type:

**Example:**
```
To start the system, run:

```bash
docker-compose up -d
```

This starts PostgreSQL and Apache AGE in the background. You should
see output indicating the database is ready.
```

---

## Voice Examples

### Good Voice:
```
The extraction process costs tokens. A 10-page document might use
20,000 tokens at $0.005/1k = $0.10. That's cheap for a one-off, but
expensive if you're re-processing the same content repeatedly.

That's why we deduplicate concepts: once "Requisite Variety" is
extracted from document 1, document 2 can just link to it rather
than creating a duplicate. The graph gets smarter, not bigger.
```

### Bad Voice (Too Hyped):
```
Our revolutionary deduplication algorithm leverages cutting-edge
vector similarity to create unprecedented knowledge fusion! You'll
be amazed at how concepts intelligently merge!
```

### Bad Voice (Too Dry):
```
The system implements a deduplication mechanism utilizing cosine
similarity thresholding over embedding vector representations to
achieve concept canonicalization.
```

---

## Section-Specific Guidelines

### Part I (Foundations)
- Assume zero prior knowledge
- Build concepts progressively
- Use lots of examples
- Visual diagrams encouraged

### Part II-III (Configuration/Admin)
- Procedural and clear
- Step-by-step instructions
- Expected outcomes stated
- Troubleshooting tips inline

### Part IV (Architecture)
- Technical but explained
- Diagrams essential
- Reference ADRs but don't duplicate them
- Explain *why* choices were made

### Part V (Advanced)
- Assume reader knows basics
- Can be more technically dense
- Link to theory and research
- Acknowledge when things are experimental

---

## Terms to Avoid

- "Revolutionary"
- "Game-changing"
- "Paradigm shift"
- "Unlock the power of..."
- "Seamlessly"
- "Effortlessly"
- "Simply" (it's never simple)
- "Just" (minimizes real complexity)

## Good Analogies

- Spotlight attention vs. ambient awareness (Watts)
- Abe Simpson rambling stories (AI verbosity)
- GPS navigation vs. exploring a city (search vs. traversal)
- Library catalog vs. following footnotes (vector search vs. graph)

---

## Review Checklist

Before finalizing a section, check:

- [ ] Does this avoid hype language?
- [ ] Are claims grounded in examples or theory?
- [ ] Would a skeptical reader find this credible?
- [ ] Are limitations acknowledged honestly?
- [ ] Is humor natural, not forced?
- [ ] Do examples actually clarify?
- [ ] Are technical concepts explained before use?
- [ ] Links to related sections provided?

---

## Examples in Practice

### Section Opening (Good)
```
# 05 - The Extraction Process

**Goal:** Understand how documents become graphs

When you feed a document to this system, an LLM reads it and extracts
concepts, relationships, and evidence. This isn't magic—it's structured
prompting with explicit output schemas. But the result is qualitatively
different from just storing text.

Let's walk through what actually happens.
```

### Section Opening (Bad - Too Hyped)
```
# 05 - The Revolutionary Extraction Process

Witness the paradigm-shifting transformation as cutting-edge AI
effortlessly converts your documents into powerful knowledge graphs!
This game-changing process will revolutionize how you think about
information!
```

### Section Opening (Bad - Too Dry)
```
# 05 - The Extraction Process

This section describes the algorithmic methodology employed by the
system to perform semantic entity extraction and relationship
inference from unstructured textual input.
```

---

*These guidelines will evolve as we refine the documentation. When in doubt: be clear, be honest, be useful.*
