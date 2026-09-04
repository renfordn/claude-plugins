# Example Envelope: review_threshold

## What this demonstrates

A review pass that crossed the dashboard-opening threshold (more than 5 findings, or touches
more than one file). `delta` carries only counts and finding summaries — no evidence text, no
diff hunks. `agent-ux` is expected to read `artifact_path` itself for hunks, and only after it
has independently confirmed the threshold from `finding_count`/`files_touched`.

## Envelope

```json
{
  "caller": "code-reviewer",
  "event_type": "review_threshold",
  "phase_state": "Implementation",
  "delta": {
    "finding_count": 7,
    "files_touched": [
      "src/session/timeout-banner.tsx",
      "src/session/timeout-banner.test.tsx",
      "src/session/session-context.ts"
    ],
    "findings": [
      { "id": "f-1", "title": "Banner re-render loop on rapid focus/blur", "tier": "high-risk", "severity": "major" },
      { "id": "f-2", "title": "Missing aria-live region on countdown text", "tier": "standard", "severity": "moderate" },
      { "id": "f-3", "title": "Dismiss handler not debounced", "tier": "standard", "severity": "minor" },
      { "id": "f-4", "title": "Test asserts on implementation detail (internal timer id)", "tier": "standard", "severity": "minor" },
      { "id": "f-5", "title": "Countdown format string not localized", "tier": "standard", "severity": "moderate" },
      { "id": "f-6", "title": "Session context re-exports unused type", "tier": "standard", "severity": "trivial" },
      { "id": "f-7", "title": "Banner z-index collides with modal overlay", "tier": "high-risk", "severity": "major" }
    ]
  },
  "artifact_path": "proposals/2026-07-01-session-timeout-warning-banner/review/findings.md"
}
```

## Notes

- No `evidence` or `diff` fields anywhere in `delta` — each finding is `id`, `title`, `tier`,
  `severity` only. `agent-ux` reads `artifact_path` on its own once it decides to render the
  dashboard card for each finding, never before.
- `finding_count` (7) and `files_touched` (3 files) both independently exceed the >5-findings /
  >1-file threshold, which is what should trigger the dashboard rather than a plain
  `ReportFindings` line.
- Expected output from `agent-ux`: breadcrumb line, plus one line confirming the review-dashboard
  Artifact was published/redeployed with 7 resolvable finding cards. A companion counter-example
  (not included as a separate file, since this is the "conforms" set) would be `finding_count: 2,
  files_touched: ["a.ts"]` — under threshold, expected output is "no artifact action — below
  threshold" instead.
