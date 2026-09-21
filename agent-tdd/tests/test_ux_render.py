"""Tests for hooks/ux_render.py.

F-04 regression: this module was never imported by any test, so a SyntaxError in
render_phase_transition() (an invalid f-string: `{summary!r or f'...'!r}`) shipped
undetected -- every real SubagentStop with agent-tdd installed exited 1 with a
traceback instead of returning a delegation instruction. These tests import the
module directly (a bare `import` already fails loudly on a SyntaxError, unlike
`py_compile`-only checks) and exercise the actual branch that was broken.
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))

import ux_render  # noqa: E402


def test_module_imports_without_syntax_error():
    # A bare successful import is itself the regression test: the module used
    # to fail with `SyntaxError: f-string: expecting ':' or '}'` at import time.
    importlib.reload(ux_render)


def test_render_phase_transition_with_explicit_summary():
    result = ux_render.render_phase_transition(
        from_phase="TDD:red",
        to_phase="TDD:green",
        feature_slug="my-feature",
        phase_state="TDD:green",
        summary="Slice 1 tests passing",
    )
    assert result is not None
    assert "one_line_summary: 'Slice 1 tests passing'" in result
    assert "from_phase: 'TDD:red'" in result
    assert "to_phase: 'TDD:green'" in result
    assert "feature_slug: 'my-feature'" in result


def test_render_phase_transition_falls_back_to_stage_label_when_summary_is_empty():
    """When summary is "" (falsy), the fallback 'TDD stage: <to_phase>' label is
    used instead -- this is the exact branch the broken f-string never reached.
    """
    result = ux_render.render_phase_transition(
        from_phase="TDD:green",
        to_phase="TDD:refactor",
        feature_slug="my-feature",
        phase_state="TDD:refactor",
        summary="",
    )
    assert result is not None
    assert "one_line_summary: 'TDD stage: TDD:refactor'" in result


def test_render_phase_transition_default_summary_argument():
    """summary defaults to "" when the caller omits it entirely."""
    result = ux_render.render_phase_transition(
        from_phase="TDD:plan",
        to_phase="TDD:red",
        feature_slug="my-feature",
        phase_state="TDD:red",
    )
    assert "one_line_summary: 'TDD stage: TDD:red'" in result
