# Prose and Voice Guide

Every page in this documentation follows the rules below. Read this before writing or editing any page.

---

## Voice in one sentence

Plain, direct, declarative. State what the system does and what the reader should do. Stop there.

---

## Defaults

**Declarative first.** State the fact, then the evidence or command.

**Second person for how-to.** "Run `./operator.sh status`," not "the user should run."

**Commands and real output over abstraction.** Show the command, show what it produces, trust the reader to extrapolate.

**Depth is earned.** Go deep only where the reader needs it to act correctly or avoid a mistake. Otherwise link out.

**Name gaps honestly.** "This is not implemented yet" is correct prose. Optimistic silence is not.

---

## Ban-list

### 1. The antithesis cliché ("it's not X, it's Y")

Sounds like a manifesto, not documentation.

> Bad: "Unlike traditional retrieval systems that find similar text chunks, this system understands and preserves the *relationships* between ideas."
>
> Good: "Kappa Graph stores concepts and the typed relationships between them — IMPLIES, CONTRADICTS, ENABLES. Queries traverse these edges; similarity search finds where to start."

The comparison earns one appearance, in the system introduction, where positioning is a real reader job. In a feature or reference page it is filler — cut it.

### 2. Marketing superlatives

Words that carry no information: powerful, seamless, robust, revolutionary, cutting-edge, simply, just, unique, innovative, game-changing.

> Bad: "Simply run `./operator.sh init` to get started."
>
> Good: "Run `./operator.sh init` to start."

If removing the adjective loses no meaning, remove it.

### 3. Rhetorical-question setups and anthropomorphism

> Bad: "Think of them as smart maintenance workers that check if there's work to do."
>
> Good: "Scheduled jobs run on a timer and skip execution when there is no work to do."

### 4. Hollow openers and transitions

"In today's world," "It's important to note that," "Let's dive in," "At its heart is."

> Bad: "It's important to note that grounding is not the same as truth."
>
> Good: "Grounding measures evidence in your corpus, not universal truth."

### 5. Exhaustive dumps

A reference page that lists every option at equal weight, or an explanation that makes the same point from six angles, wastes the reader's time. One page, one reader job. To explain why a design decision was made, link the ADR — do not reproduce its reasoning in a guide.

---

## Two registers, kept separate

**Explanatory** (`explanation/`): longer sentences acceptable; first-person plural acceptable when the author's reasoning is the subject ("we do not encode truth"). The computed-evidence note is the model.

**Operational** (`how-to/`, `self-host/`, `reference/`): imperative, short paragraphs, command first and explanation after. The async-architecture and querying guides are the models.

Do not mix the two registers in one page.

---

## Structure conventions

- Headers name what the section delivers ("How the lane manager claims jobs"), not the topic ("Overview," "Background").
- Code blocks are the primary vehicle for how-to; prose says what the code accomplishes and what to watch for, not a line-by-line narration.
- Tables for comparisons, flags, status codes — not for prose that happens to have two columns.
- The first sentence of a page names what the page covers, declaratively. Not a question, not a promise, not the title restated.

---

## Pre-commit checklist

- [ ] Does the first sentence name what this page covers?
- [ ] Is every adjective that survives removal-without-meaning-loss gone?
- [ ] Any "it's not X, it's Y" that should be one sentence or cut?
- [ ] Does every section serve one reader job?
- [ ] Could a section be replaced by a link to an ADR or research note?
- [ ] Is depth proportional to what the reader needs to act?
- [ ] Does each code block show a real command with real or representative output?
