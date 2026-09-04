# Future validation notes

Non-loaded reference file. These are the three "test-shape note" blocks moved verbatim out of
`agents/nelly-orchestrator.md` (they carry zero runtime relevance to the agent's own behavior —
they only describe fixture shapes for a future `MANUAL-VALIDATION.md` pass). Each block below is
labeled with the section of `nelly-orchestrator.md` it was moved from.

## From: "Handoff surfacing (narrower mode, restricted entry types)"

**Test-shape note for a future validation pass.** The eventual
`MANUAL-VALIDATION.md` Fixture Set P run reuses Fixture Set J's
(file-relevance matching) and Fixture Set K's (explicit-vs-inferred
exclusion) existing assertions, re-run with `handoff surfacing: true` in
place of `surface relevant memory: true`, plus a graceful-degradation
reasoning-level check (a documentation/reasoning check, since there is no
literal caller-side failure to simulate from inside this agent). This
subsection does not author that fixture; it only documents the shape a
later test-runner needs.

## From: "Aside-spinoff context bundle"

**Test-shape note for a future validation pass.** The eventual
`MANUAL-VALIDATION.md` Fixture Set N run needs two calls: one with
`aside task description` matching strong existing memory (asserting a
well-formed `Spinoff prompt:`/`Spinoff tldr:` usable verbatim as
`spawn_task` inputs) and one with no matching memory (asserting the exact
insufficiency line above). This subsection does not author that fixture; it
only documents the shape a later test-runner needs.

## From: "File-change-aware staleness (additive, `file-relevance` entries only)" (under "Staleness flagging (prune write-back)")

10. **Test-shape note for a future validation pass.** Because this check is
    independent of the age signal, the eventual `MANUAL-VALIDATION.md`
    Fixture Set M run needs at least one `file-relevance` entry whose
    `metadata.last_referenced` is deliberately set to *today* alongside a
    `metadata.files` path that has been deleted on disk, to prove the
    file-change signal fires archiving on its own rather than piggybacking
    on the age threshold. This subsection does not create that fixture; it
    only documents the shape a later test-runner needs.
