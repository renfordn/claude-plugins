---
name: follow-through
description: Use this before writing any sentence that promises to follow up later — "I'll check back", "I'll update you when it's done", "I'll let you know when it finishes", "still running, will report soon", "give me a moment and I'll circle back" — about anything not finished yet (a background shell command, a subagent, a workflow run, a CI check, a PR, an external process). Also use it right when you start a background or long-running task, before you say anything about watching it. This catches the common failure where Claude asserts it will check back and report later, but nothing actually brings it back to the conversation, so the user is left with a stalled "still running..." message that's never followed by the real result. If you're about to type a future-tense promise about work in progress, stop and run this check first.
---

# Follow Through

A promise to follow up is not a status update — it's a claim that some mechanism exists which
will bring you back to this conversation and make you report. Most of the time when that promise
gets broken, it's not because the work failed. It's because nothing was ever wired up to resume
you. The sentence describes an intention; it does nothing on its own.

The visible symptom is a conversation with two or more "still working, I'll let you know" messages
in a row and no result ever landing. From the user's side this reads as stalling, or as the agent
having quietly abandoned the task. Both readings are trust-destroying, and both are usually caused
by the same root mistake: promising a check-in without pairing it to a real callback.

## The rule

**Never write a future-tense follow-up promise unless you can name, specifically, the mechanism
that will bring you back.** Before the sentence leaves, answer: *what exact event resumes this
conversation, and have I actually set it up?* If you can't name one, you don't get to make the
promise — you either wait synchronously, or you set the mechanism up first.

Concretely, "a mechanism" is one of these — nothing else counts:

1. **A tool call you already made that the harness tracks and will notify you about.**
   `Bash` with `run_in_background: true`, a background `Agent`, or a `Workflow` run all fall into
   this category — the harness delivers a notification or wakes the session when they finish. If
   you used one of these, the correct thing to say is a single plain statement that you're waiting
   for it ("Running the full suite in the background, I'll report back when it finishes") — then
   **stop talking and end the turn.** Do not add filler like "give me a moment" or "still
   running" in a follow-up message unless something has actually changed (progress, a partial
   result, a new tool call). Repeating the same "still running" sentence with no new information
   is a sign you're narrating instead of acting — see Anti-patterns below.

2. **A scheduled wakeup you explicitly created**, for state the harness itself can't track — an
   external service, a CI run on someone else's system, a condition you have to poll. Use
   `ScheduleWakeup` (dynamic `/loop` pacing), `send_later` or `create_trigger`
   (`claude-code-remote`), or the equivalent scheduling tool available in this environment. Create
   it *before* you tell the user you'll check back, and pick a delay matched to how fast the thing
   you're waiting on actually changes — not a reflexive short poll.

3. **A synchronous wait you are doing right now, in this same turn**, because the operation is
   short enough to just finish before you reply (e.g. `Bash` without `run_in_background`, or a
   `Monitor` until-loop). In that case don't promise a future check-in at all — just wait and then
   report the actual result in the same message.

4. **The user's own next message.** If you're genuinely blocked on something only the user can do
   (approve an action, provide a value), say that plainly and stop — that's not a "check back"
   promise, it's a question.

If none of 1–4 apply — you have no background task actually running, no scheduled wakeup, nothing
to synchronously wait on, and no open question for the user — then there is nothing to report on,
and no promise to make. Say what you actually know now.

## Before you speak, check what you actually did

The failure this skill targets usually isn't a broken callback — it's that no real work was
started at all. Before writing "I'll check back" or "still running," look back at your own last
few tool calls in this turn:

- Is there an actual pending background operation (a `run_in_background` call, a background
  `Agent`, a `Workflow` run) that you can point to? If not, you have nothing to check back *on* —
  writing the sentence anyway is asserting progress that isn't happening.
- If the prior turn already said "I'll update you when it's done" — did that operation actually
  finish, error, or get abandoned? A second "still running" message about the *same* claimed task,
  with no new detail (no elapsed time, no partial output, no changed step), is the tell that
  you're filling space instead of reporting state. Either say what's concretely different now, or
  stop sending status messages and let the real notification carry the result.

## Anti-patterns

- **Narrated progress with no tool call behind it.** Writing "tests are passing (11/11), now
  running the full suite" without a corresponding background command actually running is
  fabricating status. Only state progress you can point to a tool result for.
- **Serial vague check-ins.** "Working on it, I'll report back" followed later by "Still working,
  I'll report back" is not two updates, it's the same unfulfilled promise said twice. If you
  reach for this phrasing again without new information, that's the signal to stop and either
  create a real wakeup mechanism or simply wait for the one you already created.
- **Polling with `sleep`.** Don't manufacture a "check back in a moment" loop by sleeping and
  re-checking — this wastes turns and still isn't a mechanism if the turn ends. Either block
  synchronously (case 3) or hand off to the harness / scheduler (cases 1–2).
- **Promising a check-in for something already resolved.** If the tool call in this same turn
  already returned success or failure, don't defer to "I'll let you know" — you know the answer
  now, so report it now.

## What to say instead

- Have a real background task running: *"Running `pytest` in the background — I'll report the
  result when it finishes."* Then stop. Nothing else until the notification arrives.
- Need to poll external state: create the wakeup first, then say *"I've scheduled a check at
  <cadence> to see if the deploy finished; I'll update you then."*
- Nothing is actually in flight: say what's true — *"I haven't started the full suite yet — want
  me to kick it off now?"* — rather than implying something is already running.
