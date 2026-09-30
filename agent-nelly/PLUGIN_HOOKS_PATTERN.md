# Plugin Hooks Pattern: Memory-Directory Permission Model

How `agent-nelly` gates writes to its own memory directory with PreToolUse hooks. This describes
what ships today; the earlier design for a shared audit trail, history rotation, and
all-plugin adoption was never built and was removed from this document (see the 2026-09-30 note
in `CHANGELOG.md`).

## What ships

| Piece | File | Role |
|---|---|---|
| Validator | `hooks/plugin_data_whitelist.py` | `create_whitelist_validator()` blocks file types in `BLOCKED_FILE_TYPES` (`.exe`) and, when `check_namespace=True`, enforces a per-plugin namespace |
| Allow hook | `hooks/nelly_memory_permission.py` | Allows `Write`/`Edit`/`MultiEdit` under the memory dir and global dir, after the validator passes |
| Slug guard | `hooks/nelly_slug_guard.py` | Denies writes whose project slug is not the canonical one (`hooks/shared_slug.py`) |
| Extra guards | `nelly_summary_guard.py`, `nelly_digest_guard.py` | Entry-shape checks for summary and research-digest entries |
| Registration | `hooks/hooks.json` | PreToolUse, matcher `Write\|Edit\|MultiEdit` |

`plugin_data_whitelist.py` also defines `create_audit_logger()`, but nothing calls it: no audit
trail is written.

## Hook rules

1. **Env gate first.** If the plugin's gate variable is `off`, `0`, `false` or `disabled`
   (case-insensitive), return **no decision**. Never `allow`: a gate that is off must step aside,
   not widen permissions.
2. **Allow hooks** emit `allow` only for paths inside the plugin's own directory and only after
   the validator passes; anything else returns no decision.
3. **Deny hooks** emit `deny` for a clear violation (wrong slug, cross-plugin write) and no
   decision otherwise.
4. Fail open on malformed input, so a hook bug never blocks the user's edit.

```python
validator = create_whitelist_validator(check_namespace=False)
validation = validator(file_path=norm, operation="write", plugin_name="agent-nelly")
if not validation.get("allowed"):
    no_decision()
if path_under_memory_dir(norm):
    allow("Agent Nelly memory permission: ...")
```

## Extending the blocklist

Add the extension to `BLOCKED_FILE_TYPES` in `plugin_data_whitelist.py` and add a test in
`hooks/test_plugin_data_whitelist.py`. The validator is currently only in `agent-nelly`; if another
plugin copies it, update every copy.

## Environment gates

| Plugin | Gate | Behavior when off |
|---|---|---|
| agent-nelly | `NELLY_GATE` | No decision (never `allow`) |
| agent-isdd | `SDD_GATE` | Short-circuits to allow (skips validation) |
| agent-tdd | none | Ships no plugin-data permission hook |

Gates exist for testing and backward compatibility, not production use.

## Adopting the pattern in another plugin

- `agent-isdd` uses its own `hooks/memory_permission.py` and `hooks/memory_slug_guard.py`
  without the shared validator; read those files for what it does.
- A new plugin needs: a gate name, an allow hook, a slug or namespace deny hook, a `hooks.json`
  entry, and tests for cross-plugin denial, blocked file types, and path traversal.

## Related files

- [plugin_data_whitelist.py](hooks/plugin_data_whitelist.py)
- [shared_slug.py](hooks/shared_slug.py)
- [nelly_memory_permission.py](hooks/nelly_memory_permission.py)
