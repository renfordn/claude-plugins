# agent-isdd INTEROP

> **Test fixture note:** minimal parser test double — exercises capability-field-presence parsing only, and is not kept in sync with the real INTEROP.md contract's field names or structure.

Specification-driven development workflow.

## Design Spec Handoff

The agent-isdd produces a Design Spec that gets handed off to implementation agents.

## → agent-tdd

Routes design spec to TDD agent for implementation.

## → agent-nelly

Fetches project memory and lessons.

## → agent-ux

Renders workflow progress UI events.

## Capabilities

### design_spec_handoff

Hand off design spec to implementation agent.

Produces:
- requirements_md: string
- design_md: string
- research_cache: object
- recap_md: string
