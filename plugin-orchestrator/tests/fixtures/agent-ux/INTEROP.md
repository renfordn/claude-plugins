# agent-ux INTEROP

> **Test fixture note:** minimal parser test double — exercises capability-field-presence parsing only, and is not kept in sync with the real INTEROP.md contract's field names or structure.

UI/UX rendering and events.

## Capabilities

### render_event

Render progress UI events.

Consumes:
- event_type: string
- event_data: object

Produces:
- rendered_html: string
- event_id: string
