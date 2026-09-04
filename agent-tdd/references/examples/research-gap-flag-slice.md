<!-- TDD-SKIP -->
# Worked example: a Research Gap Flag, when the real code diverges from the Slice Spec

This is a fully illustrative transcript. The feature ("send a welcome email when a user
completes signup") does not exist anywhere in this repo — it is a small, concrete stand-in chosen
so the mechanics of the Mid-Slice Research Request path (see
[`agent-TDD.md`](../../agents/agent-TDD.md)) are easy to follow without needing any other file
open.

Unlike the [`standard`-tier example](standard-tier-slice.md), the caller's Data Contracts And
Interfaces here turn out to be stale: the interface named in the Slice Spec doesn't exist in the
actual code. `agent-TDD` does not guess or invent structure to compensate — it stops at the same
handoff point it uses for the mandatory review pause and raises a **Research Gap Flag** instead.

## Caller's Slice Spec (spawn prompt to `agent-TDD`)

- **Task description**: When a user completes signup, send them a welcome email via
  `EmailService.send_welcome(user)`.
- **Acceptance criteria / Test Intent**: Completing signup (`SignupFlow.complete(user)`) results
  in exactly one call to `EmailService.send_welcome` with the newly created user. If sending
  raises, signup itself still succeeds (the user is created either way) but the error is logged.
- **Risk Tier**: `standard`
- **Data Contracts And Interfaces**: `EmailService.send_welcome(user: User) -> None`, defined in
  `notifications/email_service.py`. `SignupFlow.complete(user_data: dict) -> User`, defined in
  `accounts/signup.py`, currently only creates the `User` record.
- **Pre-Slice Brief**: (none — no prior project memory available for this illustrative scenario)
- **Review handoff mode**: unset (defaults to mandatory pause for caller-driven review)

## `agent-TDD` invocation — Plan through the divergence

### Plan

Smallest safe slice: call `EmailService.send_welcome(user)` from `SignupFlow.complete` after user
creation, wrapped so a send failure doesn't block signup, backed by one test file covering the
happy path and the failure-is-logged-not-raised path. Expected single file to reach green
(`accounts/signup.py`), assuming `EmailService.send_welcome` exists as specified.

### Red (interrupted by the divergence)

Before writing the test, read `notifications/email_service.py` to confirm the exact call
signature (per operating principle 1: start from behavior, and per the Plan step's instruction to
identify the tests that describe the intended behavior against the real interface). The file
exists, but it defines `EmailService.dispatch(template_name: str, user: User) -> None` — there is
no `send_welcome` method anywhere in the class, and no other file in `notifications/` defines one
either (checked via grep across the module).

This is a named-interface mismatch, not a naming nitpick: `send_welcome` may be a template-specific
wrapper that doesn't exist yet, or the Slice Spec may have meant `dispatch("welcome", user)` using
the real generic method — those are two different implementations with different test assertions,
and guessing wrong here would mean asserting against a method this codebase doesn't have. Per
*Mid-Slice Research Request* in `agent-TDD.md`, this stops here rather than inventing either
interpretation.

No test file was written and no production code was touched — the divergence was caught during
interface confirmation, before Red began.

### Handoff report (pre-review pause, with Research Gap Flag)

```
<!--AGENT-TDD-REPORT-->
1. Plan: call EmailService's welcome-email method from SignupFlow.complete after user creation,
   with send failures logged rather than raised; one production file, one test file — blocked
   before Red began (see Research Gap Flag).
2. Test Changes: none written — blocked before Red, see Research Gap Flag below.
3. Implementation Changes: none — blocked before Green.
4. Validation Evidence: none to report; no tests were added or run.
5. Acceptance Criteria: not yet attempted — blocked on the divergence below.
6. Risks and Follow-ups: none beyond the Research Gap Flag itself.
7. Handoff Facts: notifications/email_service.py defines a generic
   EmailService.dispatch(template_name: str, user: User) -> None, not a per-template
   send_welcome method — worth persisting if the caller has a memory store, since any future
   slice touching "send an email" in this codebase will hit the same naming mismatch.
8. Research Gap Flag: the Slice Spec's Data Contracts And Interfaces named
   EmailService.send_welcome(user: User) -> None in notifications/email_service.py. That method
   does not exist; the actual class defines EmailService.dispatch(template_name: str, user:
   User) -> None, and a repo-wide grep for "send_welcome" and "welcome" in notifications/ found
   no per-template wrapper either. Two different implementations are possible depending on
   intent — (a) SignupFlow.complete should call dispatch("welcome", user) directly against the
   existing generic method, or (b) a new EmailService.send_welcome wrapper should be added first
   as its own slice, if the caller wants a stable typed call site rather than a bare template-name
   string. Need the caller to confirm which before Red can proceed — guessing would mean
   asserting against a method this codebase doesn't have.

Pausing here — not for the mandatory review step (Green was never reached), but per the Research
Gap Flag above. Awaiting caller clarification on which EmailService interface this slice should
target before Red begins.
```

## Caller's response

Caller checks the codebase's own notification conventions, confirms `dispatch("welcome", user)` is
the established pattern (three other call sites already use `dispatch` with different template
names), and resumes the same `agent-TDD` instance: "Use `EmailService.dispatch(\"welcome\", user)`
directly — no new wrapper method. Proceed with Red using that interface."

## `agent-TDD` invocation (resumed) — Red through final handoff

With the interface confirmed, the rest of the slice proceeds exactly as the
[`standard`-tier example](standard-tier-slice.md) does: Red against
`EmailService.dispatch("welcome", user)`, Green in `SignupFlow.complete`, the mandatory review
pause (Review handoff mode was left unset), then Refactor and Validate once review clears. Not
reproduced in full here since the mechanics from that point on are identical to the other
examples — only the divergence-and-resume step above is specific to a Research Gap Flag.

## Why this differs from the default path

The [`standard`-tier example](standard-tier-slice.md) pauses once, after Green, for review. This
example pauses earlier — before Red even starts — because the Data Contracts And Interfaces the
caller supplied turned out not to match the real code. `agent-TDD` never invents the missing
`send_welcome` method or guesses which of the two interpretations the caller meant; it names the
exact mismatch and both plausible resolutions, and waits.
