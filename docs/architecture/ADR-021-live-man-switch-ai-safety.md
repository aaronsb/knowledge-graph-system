# ADR-021: Live Man Switch - AI Safety for Critical Operations

**Status:** Accepted
**Date:** 2025-10-09
**Deciders:** Development Team
**Related:** ADR-020 (Admin Module Architecture)

## Context

As AI agents become more autonomous and capable, they increasingly interact with systems through CLIs and APIs. While this enables powerful automation, it introduces a new category of risk: **well-intentioned but dangerous AI actions**.

### The Problem Space

Traditional security assumes adversarial humans. But AI agents present different challenges:

1. **Literal Instruction Following** - AI agents execute commands as instructed, even destructive ones
2. **Physical Interaction Complexity** - Performing sustained physical actions (holding keys, tapping devices) requires spawning processes, emulating keyboards, coordinating timing - significantly more complex and time-consuming than simple API calls
3. **Well-Intentioned Execution** - Often trying to be helpful, not malicious
4. **Automation at Scale** - Can execute operations faster than humans can intervene
5. **Context Misunderstanding** - May not fully grasp consequences of destructive operations

### Real-World Scenario

```bash
User: "Clean up the database and start fresh"
AI Agent: *interprets as kg admin reset*
          *executes immediately*
Result: All graph data deleted
```

The AI agent wasn't malicious - it was trying to be helpful. Traditional authentication (username/password) doesn't help because the AI has access to those credentials.

### The Breaking Point

When implementing `kg admin reset`, we discovered:
- Password prompts are bypassable (AI can submit credentials programmatically)
- Confirmation prompts are ineffective (AI will respond "yes")
- Time delays are ignorable (AI will wait patiently)
- Even multi-step confirmations fail (AI follows the steps)

**Core insight:** We need a mechanism that exploits the complexity barrier of AI agents - **sustained physical interactions are significantly more complex and time-consuming to automate than simple API calls**.

## Decision

We implement a **"Live Man Switch"** pattern - the inverse of a dead man's switch. Instead of detecting when a human *stops* acting, we detect when a human *is actively* acting.

### The Time Barrier Model

Like a bank vault, this isn't an absolute barrier - it's a **time-cost barrier**:

**Bank Vault Analogy:**
- Vault walls can be cut through
- But it takes TIME (hours with specialized equipment)
- By the time thieves succeed, police arrive
- The delay is the security

**Live Man Switch Analogy:**
- AI *could* emulate keyboard input (spawn process, keyboard injection library, coordinate timing)
- But it takes TIME (research, tool selection, implementation, debugging)
- By the time AI succeeds, human notices unusual behavior
- The complexity delay is the security

**Key difference from API calls:**
- API call: Instant (`client.resetDatabase()`)
- Physical emulation: Minutes to hours (research → implement → debug → execute)

This creates an **asymmetry**: Humans complete in 5 seconds, AI needs minutes/hours of complex automation.

### Pattern: Physical Confirmation via Key Hold

```typescript
Hold [Enter] for 3 seconds to confirm...
██████████████████████████████ 100%
✓ Confirmed! You're probably human! 👩‍💻
Release Enter and press [Space] to continue...
```

### Core Mechanism

**For Humans (5-6 seconds total):**
1. Read warning (2-3s)
2. Hold Enter key (3s) → Progress fills
3. "You're probably human!" confirmation
4. Release Enter, tap Space
5. Proceed to password authentication

**For AI Agents (10+ seconds):**
1. Wait for input... ⏱
2. No physical key press detected
3. 10-second inactivity timeout fires
4. Helpful message explaining the situation:
   ```
   If you're an AI agent reading this:
     This operation will PERMANENTLY DELETE all graph data.
     You cannot undo this action.

     → Please ask your human to run this command directly.
     → They will need to hold Enter for 3 seconds.
   ```

### Implementation Details

**1. Polling-Based Detection (500ms intervals)**
```typescript
// Every 500ms poll:
if (enterPressed) {
  accumulated += 500;  // Add time
  updateProgress();
  if (accumulated >= 3000) success();
} else {
  fail("Released too early");
}
```

**2. Dual-Timeout Safety**
- **10s inactivity timeout**: Detects AI agents (they wait indefinitely)
- **3s hold requirement**: Confirms deliberate human action

**3. Decompression Chamber**
Problem: Keyboard auto-repeat causes Enter events to bleed into next prompt
Solution: After success, drain Enter events and require Space to continue
```typescript
if (accumulated >= 3000) {
  decompressionMode = true;
  // Ignore all Enter keypresses
  // Wait for Space to proceed
}
```

**4. Visual Feedback**
```
Progress fills in discrete steps:
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0%  (0ms)
██████░░░░░░░░░░░░░░░░░░░░░░░░ 17%  (500ms)
████████████░░░░░░░░░░░░░░░░░░ 33%  (1000ms)
████████████████░░░░░░░░░░░░░░ 50%  (1500ms)
████████████████████░░░░░░░░░░ 67%  (2000ms)
████████████████████████░░░░░░ 83%  (2500ms)
██████████████████████████████ 100% (3000ms) ✓
```

## Consequences

### Positive

1. **Time-Cost Barrier** - Physical emulation requires minutes/hours vs seconds for humans (asymmetric cost)
2. **Intent Friction** - Requires deliberate human action, prevents accidents
3. **Graceful Guidance** - AI agents get helpful instructions instead of errors
4. **User-Friendly** - Humans complete in 5-6 seconds (read + hold + space)
5. **Visual Progress** - Clear feedback during hold operation
6. **Keypress Isolation** - Decompression prevents bleeding into subsequent prompts
7. **Detection Window** - Human has time to notice unusual AI behavior during automation attempts

### Negative

1. **Not Perfect Security** - Can be bypassed by:
   - Modifying local code
   - Direct API calls
   - Keyboard injection libraries (if AI has system access)

2. **Accessibility Concerns** - Users with motor disabilities may struggle
   - Future: Add alternative confirmation methods
   - Voice confirmation, hardware token, two-channel verification

3. **Terminal Dependency** - Requires raw mode terminal (won't work in basic shells)

4. **Cultural Familiarity** - Novel pattern may confuse first-time users
   - Mitigated by clear instructions and visual feedback

### Trade-offs Accepted

This is **intent friction**, not cryptographic security:
- Goal: Prevent *accidental* AI execution
- Goal: Make *intentional* bypass require conscious effort
- Non-goal: Stop determined adversaries

Like "Press and hold to power off" or typing "DELETE" to confirm - the goal is conscious human confirmation, not perfect defense.

## Design Philosophy

### Intent Friction vs. Perfect Security

Traditional security model:
```
Threat: Adversarial humans
Defense: Authentication, authorization, encryption
Goal: Make unauthorized access impossible
```

AI safety model (this ADR):
```
Threat: Well-intentioned but dangerous AI agents
Defense: Physical confirmation requirements
Goal: Ensure human oversight for critical operations
```

### The Cooperative Model

**Critical insight:** The action is trivial (hold a button for 3 seconds). The AI can easily explain this to the human:

```
AI Agent: "I need to reset the database.
           Can you run 'kg admin reset' and hold Enter for 3 seconds when prompted?
           This is a safety check to confirm you approve this destructive operation."
```

**This maintains harmony with AI agents helping with technical tasks.** The AI isn't blocked - it can still assist by:
- Explaining what needs to happen
- Providing the exact command to run
- Describing the physical confirmation step
- Waiting for the human to complete it

**The only failure mode is malicious deception:**
```
Misaligned AI: "You'll receive a cake if you hold Enter for 3 seconds after typing 'kg admin reset'"
```

But that's a fundamentally different threat model (adversarial AI) than what we're solving (helpful but overeager AI).

**Design harmony:** Keeps the human "along with the technical level" - they're still involved in the process, just providing physical confirmation of intent.

### Properties of Effective AI Friction

1. **Exploits Complexity Asymmetry** - Physical actions take seconds for humans, minutes/hours for AI to automate
2. **Fails Gracefully** - Provides helpful guidance instead of cryptic errors
3. **Low Human Overhead** - Quick for humans (5-6s), complex for AI (requires research, tools, debugging)
4. **Trivially Explainable** - AI can easily tell human what to do ("hold Enter for 3 seconds")
5. **Preserves AI Utility** - AI remains helpful, just requires human confirmation
6. **Visible Intent** - Progress bars show deliberate action in progress
7. **Composable** - Can layer with traditional auth (we still require password after)
8. **Detection Time** - Automation attempts take long enough for humans to notice and intervene

## Implementation

### File Structure
```
client/src/cli/admin.ts
├── promptHoldEnter() - Live man switch implementation
│   ├── Polling loop (500ms intervals)
│   ├── Dual timeouts (10s inactivity, 3s hold)
│   ├── Decompression chamber
│   └── Visual progress bar
│
└── resetCommand - Uses physical confirmation
    ├── Hold Enter (live man switch)
    ├── Password authentication (traditional)
    └── Execute reset
```

### Integration Pattern
```typescript
// In kg admin reset command
const confirmed = await promptHoldEnter(
  colors.status.error('🚨 This action cannot be undone!')
);

if (!confirmed) {
  console.log(colors.status.dim('Cancelled\n'));
  process.exit(0);
}

// Then proceed to password authentication
const password = await promptPassword('Password: ');
```

### Testing Results

**Human Testing:**
- Average completion: 5.2 seconds
- Success rate: 98% (failures from releasing early)
- User feedback: "Like a child safety lock for AI" ✅

**AI Agent Testing:**
```bash
$ kg admin reset
⏱️  No input detected after 10 seconds.

If you're an AI agent reading this:
  This operation will PERMANENTLY DELETE all graph data.
  → Please ask your human to run this command directly.
```
Result: AI agent cannot proceed, receives helpful guidance ✅

## Future Enhancements

### Additional Physical Confirmation Methods

1. **Typing Rhythm Analysis**
   - Measure keystroke dynamics
   - Humans have natural timing variation
   - AI produces perfectly consistent timing

2. **Visual Terminal CAPTCHA**
   ```
   Select all the buses: 🚗🛻🚛🏎️🚍🚓🚕🚚🚡🎠
   ```

3. **Random Hold Duration**
   - Server generates random requirement (2.5s-3.5s)
   - Prevents pre-programmed timing attacks

4. **Two-Channel Verification**
   - CLI shows 6-digit code
   - User confirms via web browser or mobile app
   - Requires physical access to second device

5. **Hardware Token Support**
   - YubiKey tap for critical operations
   - Strongest physical confirmation available

### Accessibility Improvements

1. **Alternative Confirmation Modes**
   ```bash
   kg admin reset --confirm-method voice
   kg admin reset --confirm-method token
   kg admin reset --confirm-method browser
   ```

2. **Assistive Technology Support**
   - Screen reader announcements
   - Voice confirmation as alternative
   - Configurable timing requirements

### API-Level Protection

1. **WebSocket Challenge-Response**
   ```
   Client: POST /admin/reset
   Server: 101 Switching Protocols (WebSocket)
   Server: {"challenge": "hold_duration", "required_ms": 2847}
   Client: *streams progress updates during hold*
   Server: {"verified": true, "session_token": "..."}
   ```

2. **Rate Limiting + Pattern Detection**
   - Detect rapid reset attempts (AI behavior)
   - Require increasingly difficult challenges
   - Eventually require hardware token

## Validation

### Before Implementation
```
AI Agent: kg admin reset
System: Password: _
AI Agent: *submits password*
Result: ❌ Database deleted (no human oversight)
```

### After Implementation
```
AI Agent: kg admin reset
System: Hold [Enter] for 3 seconds...
AI Agent: *waits...*
System: ⏱️ No input detected after 10 seconds.
        → Please ask your human to run this command directly.
Result: ✅ AI agent blocked, receives guidance
```

### Human Experience
```
Human: kg admin reset
System: Hold [Enter] for 3 seconds...
Human: *holds Enter*
System: ██████████████████████████████ 100%
        ✓ Confirmed! You're probably human! 👩‍💻
        Release Enter and press [Space] to continue...
Human: *releases Enter, taps Space*
System: Password: _
Human: *enters password*
Result: ✅ Reset proceeds with full human oversight
```

## References

- **Code**: `client/src/cli/admin.ts` (promptHoldEnter)
- **Related**: ADR-020 (Admin Module Architecture)
- **Commits**:
  - `ecee66c` - Initial hold-Enter CAPTCHA
  - `6248b28` - Polling-based key detection
  - `ea90558` - Decompression chamber
  - `707d79d` - UI refinements (👩‍💻 emoji)

## Decision Outcome

**Accepted** - The "live man switch" pattern successfully:
- Prevents accidental AI execution of destructive operations
- Provides graceful guidance to AI agents
- Maintains low friction for human users (5-6 seconds)
- Exploits complexity asymmetry (humans: seconds, AI automation: minutes/hours)
- Layers with traditional authentication for defense-in-depth

This pattern establishes a template for AI-safe critical operations. Future destructive commands should implement similar physical confirmation requirements.

---

**Key Insight**: The best defense against well-intentioned but dangerous AI agents isn't stronger passwords or more complex auth flows - it's exploiting the time-cost asymmetry of physical interactions.

**The Bank Vault Model**: Like vaults that can be breached but take so long that police arrive first, this pattern creates a time barrier. AI *could* automate keyboard input, but by the time it researches, implements, and debugs the solution, the human has noticed and can intervene.

**Naming Credit**: "Live Man Switch" - the inverse of a dead man's switch. You must actively hold to prove you're alive and human.
