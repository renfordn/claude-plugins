"""Tests for plugin_data_whitelist validators."""

import os
import pytest
from plugin_data_whitelist import (
    create_whitelist_validator,
    create_audit_logger,
    should_use_env_gate,
)


class TestWhitelistValidator:
    """Test file-type restrictions and directory scoping."""

    def test_file_type_blocklist_exe_denied(self):
        """Executable .exe files should be blocked."""
        validator = create_whitelist_validator()
        result = validator(
            file_path="/Users/test/.claude/plugin-data/agent-nelly/script.exe",
            operation="write",
            plugin_name="agent-nelly",
        )
        assert result["allowed"] is False
        assert "Executable" in result["reason"] or "blocked" in result["reason"].lower()

    def test_file_type_md_allowed(self):
        """Markdown files should be allowed."""
        validator = create_whitelist_validator()
        result = validator(
            file_path="/Users/test/.claude/plugin-data/agent-nelly/memory.md",
            operation="write",
            plugin_name="agent-nelly",
        )
        assert result["allowed"] is True

    def test_directory_scope_same_agent_allowed(self):
        """Agent writing to its own namespace should be allowed."""
        validator = create_whitelist_validator()
        result = validator(
            file_path="/Users/test/.claude/plugin-data/agent-nelly/entries/foo.md",
            operation="write",
            plugin_name="agent-nelly",
        )
        assert result["allowed"] is True

    def test_directory_scope_cross_agent_denied(self):
        """Agent writing to another agent's namespace should be denied."""
        validator = create_whitelist_validator()
        result = validator(
            file_path="/Users/test/.claude/plugin-data/agent-tdd/state.json",
            operation="write",
            plugin_name="agent-nelly",
        )
        assert result["allowed"] is False
        assert "namespace" in result["reason"].lower() or "denied" in result["reason"].lower()

    def test_file_type_json_allowed(self):
        """JSON files should be allowed."""
        validator = create_whitelist_validator()
        result = validator(
            file_path="/Users/test/.claude/plugin-data/agent-nelly/state.json",
            operation="write",
            plugin_name="agent-nelly",
        )
        assert result["allowed"] is True

    def test_file_type_yaml_allowed(self):
        """YAML files should be allowed."""
        validator = create_whitelist_validator()
        result = validator(
            file_path="/Users/test/.claude/plugin-data/agent-nelly/config.yaml",
            operation="write",
            plugin_name="agent-nelly",
        )
        assert result["allowed"] is True


class TestAuditLogger:
    """Test audit entry creation."""

    def test_audit_entry_has_required_fields(self):
        """Audit entry should have timestamp, action, reason."""
        logger = create_audit_logger()
        entry = logger(
            operation="write",
            file_path="/Users/test/.claude/plugin-data/agent-nelly/entry.md",
            plugin_name="agent-nelly",
            allowed=True,
            reason="File type allowed",
        )
        assert "timestamp" in entry
        assert "plugin_name" in entry
        assert "operation" in entry
        assert "allowed" in entry
        assert "reason" in entry

    def test_audit_entry_allowed_flag(self):
        """Audit entry should preserve allowed flag."""
        logger = create_audit_logger()
        entry = logger(
            operation="write",
            file_path="/test.md",
            plugin_name="agent-nelly",
            allowed=False,
            reason="Test reason",
        )
        assert entry["allowed"] is False

    def test_audit_entry_timestamp_is_numeric(self):
        """Timestamp should be numeric (Unix milliseconds or seconds)."""
        logger = create_audit_logger()
        entry = logger(
            operation="write",
            file_path="/test.md",
            plugin_name="agent-nelly",
            allowed=True,
            reason="Test",
        )
        assert isinstance(entry["timestamp"], (int, float))
        assert entry["timestamp"] > 0


class TestEnvGate:
    """Test environment-variable gate detection."""

    def test_env_gate_nelly_gate_set_returns_true(self, monkeypatch):
        """NELLY_GATE=off should return True (gate is enabled)."""
        monkeypatch.setenv("NELLY_GATE", "off")
        assert should_use_env_gate("NELLY_GATE") is True

    def test_env_gate_nelly_gate_unset_returns_false(self, monkeypatch):
        """NELLY_GATE unset should return False (gate is disabled)."""
        monkeypatch.delenv("NELLY_GATE", raising=False)
        assert should_use_env_gate("NELLY_GATE") is False

    def test_env_gate_sdd_gate_set_returns_true(self, monkeypatch):
        """SDD_GATE=1 should return True."""
        monkeypatch.setenv("SDD_GATE", "1")
        assert should_use_env_gate("SDD_GATE") is True

    def test_env_gate_tdd_gate_false_value_returns_true(self, monkeypatch):
        """TDD_GATE=false should return True (any value means gate is set)."""
        monkeypatch.setenv("TDD_GATE", "false")
        assert should_use_env_gate("TDD_GATE") is True

    def test_env_gate_missing_returns_false(self, monkeypatch):
        """Missing env var should return False."""
        monkeypatch.delenv("MISSING_GATE", raising=False)
        assert should_use_env_gate("MISSING_GATE") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
