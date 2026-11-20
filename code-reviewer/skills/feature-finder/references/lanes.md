# Lanes

Pick one; switch only when the question changes, keeping evidence that still applies.

## Locate

Classify the target (path, symbol, route, config key, event name, label). Search the exact form first, identify the definition before callers, read a narrow window plus one immediate caller or test. Report location, role in a line or two, and one immediate impact hint if visible in the same window. If asked only "where is it", omit the causal story.

## Explain

One bounded target. Read the definition, its immediate callers, and the narrowest relevant test or configuration. Cover inputs, decisions, state changes, effects, outputs and the failure paths that matter to the question. Lead with the answer, then the causal path.

## Trace

Follow one call chain or data path hop by hop from a named start (or end). Cite each hop. Stop at the first boundary the user has not accepted (other package, runtime, external service) and mark the continuation unverified.

## Impact

Start from the observed definition and extend along observed edges only: callers and consumers, contracts and serialization, configuration and flags, events or jobs, tests. State blast radius as a conditional surface map, not a count, unless counts were observed. Name an unknown-consumer boundary explicitly.

## Research

Cross-cutting questions spanning several modules. Frame one primary claim and one likely counterexample, probe the smallest source that settles each, record the status, and stop. Keep reading sequential; do not delegate. Propose the next tier rather than widening silently.
