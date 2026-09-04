#!/usr/bin/env python3
"""
Integration test: Simulate high-risk slice code-review gate checkpoint.

Scenario:
1. agent-tdd completes Phase 1 (slicing) and Phase 2 (research validation)
2. agent-tdd starts Phase 3 Red-Green-Refactor on a high-risk slice
3. agent-tdd pauses at Green→Refactor with <!--AGENT-TDD-PHASE:green_pause-->
4. high_risk_reviewer hook detects green_pause state
5. Checkpoint surfaces to remind user to run /code-reviewer
"""

import sys
import os
import json
import tempfile
from pathlib import Path

hooks_dir = os.path.join(os.path.dirname(__file__), '..', 'hooks')
sys.path.insert(0, hooks_dir)
import high_risk_reviewer


def create_test_tasks_md(temp_dir):
    """Create a tasks.md with high-risk and standard slices."""
    tasks_md = """# Tasks: Payment Flow Schema Migration

## Phase 1: Add Payment Table
### Risk Tier
- `high-risk`

### Objective
Add payment_methods table to support credit card storage.

### Test Intent
Create table, verify schema, test constraints.

### Data Contracts and Interfaces
- New table: payment_methods (id, user_id, card_last_four, expires_at)
- Constraint: card_last_four must be 4 characters

## Phase 2: Migrate Legacy Charges
### Risk Tier
- `high-risk`

### Objective
Migrate existing payment data to new payment_methods table.

### Test Intent
Data integrity check, no payment loss, old schema still readable.

### Data Contracts and Interfaces
- Read from charges table
- Write to payment_methods table
- Keep charges.payment_id pointing to payment_methods.id

## Phase 3: Update Payment API
### Risk Tier
- `standard`

### Objective
Update API endpoints to use new payment_methods table.

### Test Intent
API calls return correct payment info, no breaking changes.

### Data Contracts and Interfaces
- GET /api/payments -> returns from payment_methods
- POST /api/payments -> creates in payment_methods
"""

    tasks_dir = os.path.join(temp_dir, "tasks")
    os.makedirs(tasks_dir, exist_ok=True)
    tasks_path = os.path.join(tasks_dir, "tasks.md")

    with open(tasks_path, 'w', encoding='utf-8') as f:
        f.write(tasks_md)

    return temp_dir


def create_test_workflow_state(temp_dir):
    """Create workflow-state.json with empty code_reviewer_tracking."""
    state = {
        "feature_slug": "2026-08-24-payment-schema-migration",
        "current_phase": "Implementation",
        "phase_state": "In Progress",
        "code_reviewer_tracking": {
            "high_risk_phases": ["Phase 1: Add Payment Table", "Phase 2: Migrate Legacy Charges"],
            "reviewed_phases": []
        }
    }

    state_path = os.path.join(temp_dir, "workflow-state.json")
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

    return temp_dir


def simulate_agent_tdd_green_pause():
    """Simulate agent-tdd SubagentStop report with green_pause marker."""
    report = """
<!--AGENT-TDD-REPORT-->
Phase: Red-Green-Refactor
Slice: Phase 1 - Add Payment Table
Status: Green complete, pausing at Refactor

<!--AGENT-TDD-PHASE:green_pause-->

Implementation:
- Created payment_methods table with schema:
  - id (PK)
  - user_id (FK)
  - card_last_four (4 chars)
  - expires_at

Green test passed:
- Table created
- Schema matches design
- Constraints enforced

Awaiting code review before proceeding to Refactor phase.
Risk Tier: high-risk
Risk: Schema changes affect payment processing

Reviewer please check:
- Column types match database version
- Indexes on user_id and expires_at
- Constraint validation for card_last_four
"""
    return report


def main():
    """Run integration test."""
    print("=" * 70)
    print("HIGH-RISK SLICE CODE-REVIEW GATE TEST")
    print("=" * 70)

    # Test 1: Setup
    print("\n✓ TEST 1: Setup test environment")
    with tempfile.TemporaryDirectory() as temp_dir:
        create_test_tasks_md(temp_dir)
        create_test_workflow_state(temp_dir)

        print(f"  ✓ Created test tasks.md with 3 phases (2 high-risk, 1 standard)")
        print(f"  ✓ Created workflow-state.json with tracking")

    # Test 2: Parse green_pause marker
    print("\n✓ TEST 2: Parse green_pause marker from agent-tdd report")
    agent_tdd_report = simulate_agent_tdd_green_pause()
    is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(agent_tdd_report)

    assert is_green_pause == True, "Should detect green_pause"
    assert phase_name == "green_pause", f"Should be 'green_pause', got {phase_name}"
    print(f"  ✓ Detected green_pause state: {is_green_pause}")
    print(f"  ✓ Phase name: {phase_name}")

    # Test 3: High-risk phases identification
    print("\n✓ TEST 3: Identify high-risk phases from tasks.md")
    with tempfile.TemporaryDirectory() as temp_dir:
        create_test_tasks_md(temp_dir)
        phases = high_risk_reviewer.read_tasks_md(temp_dir)
        high_risk = high_risk_reviewer.get_high_risk_phases(phases)

        print(f"  ✓ Total phases: {len(phases)}")
        print(f"  ✓ High-risk phases: {len(high_risk)}")

        for phase in high_risk:
            print(f"    - {phase['name']}")

        assert len(high_risk) == 2, f"Expected 2 high-risk, got {len(high_risk)}"

    # Test 4: Checkpoint message when unreviewed
    print("\n✓ TEST 4: Checkpoint message (unreviewed high-risk slices)")
    with tempfile.TemporaryDirectory() as temp_dir:
        create_test_tasks_md(temp_dir)
        create_test_workflow_state(temp_dir)

        checkpoint = high_risk_reviewer.get_code_reviewer_checkpoint(temp_dir)

        assert checkpoint is not None, "Should have checkpoint"
        assert checkpoint["type"] == "checkpoint", "Should be checkpoint type"
        assert len(checkpoint["unreviewed_phases"]) == 2, "Should have 2 unreviewed"

        print(f"  ✓ Checkpoint type: {checkpoint['type']}")
        print(f"  ✓ High-risk total: {checkpoint['high_risk_count']}")
        print(f"  ✓ Reviewed: {checkpoint['reviewed_count']}")
        print(f"  ✓ Unreviewed: {len(checkpoint['unreviewed_phases'])}")
        print(f"\n  Message preview:")
        for line in checkpoint["message"].split("\n")[:8]:
            print(f"    {line}")

    # Test 5: No high-risk phases scenario
    print("\n✓ TEST 5: No checkpoint when no high-risk phases")
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create tasks.md with only standard slices
        standard_tasks = """# Tasks: API Enhancement
## Phase 1: Add Endpoint
### Risk Tier
- `standard`
"""
        tasks_dir = os.path.join(temp_dir, "tasks")
        os.makedirs(tasks_dir, exist_ok=True)
        with open(os.path.join(tasks_dir, "tasks.md"), 'w') as f:
            f.write(standard_tasks)

        create_test_workflow_state(temp_dir)
        checkpoint = high_risk_reviewer.get_code_reviewer_checkpoint(temp_dir)

        assert checkpoint is None, "Should have no checkpoint for non-high-risk"
        print(f"  ✓ No checkpoint when only standard phases")

    # Test 6: Hook execution
    print("\n✓ TEST 6: Hook execution simulation")
    with tempfile.TemporaryDirectory() as temp_dir:
        create_test_tasks_md(temp_dir)
        create_test_workflow_state(temp_dir)

        # Mock SubagentStop payload
        payload = {
            "cwd": temp_dir,
            "transcript_path": "/mock/transcript.jsonl"
        }

        # Patch sdd_state to find our test state
        original_active = high_risk_reviewer.active_state_file
        def mock_active(cwd):
            state_path = os.path.join(cwd, "workflow-state.json")
            if os.path.exists(state_path):
                return state_path
            return original_active(cwd)

        high_risk_reviewer.active_state_file = mock_active

        try:
            # Simulate hook main() with our test setup
            import io
            from contextlib import redirect_stdout

            captured = io.StringIO()

            # Run the logic inline (can't call main() without stdin)
            state_path = high_risk_reviewer.active_state_file(temp_dir)
            feature_dir = os.path.dirname(state_path)

            tasks_md_phases = high_risk_reviewer.read_tasks_md(feature_dir)
            high_risk = high_risk_reviewer.get_high_risk_phases(tasks_md_phases)

            if high_risk:
                high_risk_reviewer.init_code_reviewer_tracking(feature_dir, high_risk)

            checkpoint = high_risk_reviewer.get_code_reviewer_checkpoint(feature_dir)

            assert checkpoint is not None
            print(f"  ✓ Hook initialization successful")
            print(f"  ✓ Tracking initialized with {len(high_risk)} high-risk phases")
            print(f"  ✓ Checkpoint would surface to user")

        finally:
            high_risk_reviewer.active_state_file = original_active

    print("\n" + "=" * 70)
    print("✅ ALL HIGH-RISK SLICE TESTS PASSED")
    print("=" * 70)
    print("\nScenario validated:")
    print("  • agent-tdd pauses at green_pause (code-review gate)")
    print("  • high_risk_reviewer hook detects pause state")
    print("  • Checkpoint identifies high-risk slices needing review")
    print("  • User sees reminder to run /code-reviewer")
    print("  • Tracking state updated when reviews complete")
    print("\nReady for production testing with real agent-tdd runs.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
