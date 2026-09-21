# agent-tdd INTEROP

> **Test fixture note:** minimal parser test double — exercises capability-field-presence parsing only, and is not kept in sync with the real INTEROP.md contract's field names or structure.

Test-driven development workflow.

## Design Spec Processing

The agent-tdd consumes a Design Spec from agent-isdd and slices it into implementation phases.

## → code-reviewer

Routes TDD implementation to code review.

## Capabilities

### design_spec_slicing

Slice design into TDD-ready phases.

Consumes:
- requirements_md: string
- design_md: string
- research_cache: object
- recap_md: string

Produces:
- phase_slices: array
- test_specs: array
