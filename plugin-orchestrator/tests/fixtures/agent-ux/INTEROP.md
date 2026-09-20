# agent-ux INTEROP

> **Test fixture note:** minimal parser test double — exercises capability-field-presence parsing
> only. Fields reflect the real INTEROP.md event envelope contract.

UI/UX rendering and events.

## Capabilities

### render_event

Render progress UI events via event envelope delegation.

Consumes:
- caller: string
- event_type: string
- phase_state: string
- delta: object

Produces:
- breadcrumb_line: string
- chapter_marked: boolean
