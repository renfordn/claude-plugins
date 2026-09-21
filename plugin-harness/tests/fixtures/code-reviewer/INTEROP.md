# code-reviewer INTEROP

> **Test fixture note:** minimal parser test double — exercises capability-field-presence parsing only, and is not kept in sync with the real INTEROP.md contract's field names or structure.

Quality gate reviewing implementation output.

## Capabilities

### code_review

Review implementation output and return approval/feedback.

Consumes:
- sliced_specs: array
- implementation: object

Produces:
- review_feedback: array
- approval: boolean
