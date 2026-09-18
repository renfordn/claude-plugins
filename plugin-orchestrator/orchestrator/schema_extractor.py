"""Schema Extraction Module: Parse INTEROP.md files and extract handoff schemas.

This module extracts field schemas from normalized markdown tables in INTEROP.md files,
establishing INTEROP.md as the single authoritative source of truth for handoff contracts.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Field:
    """A single field in a handoff contract."""
    name: str
    type_name: str  # JSON Schema type: string, object, array, etc.
    required: bool
    description: str = ""


@dataclass
class Schema:
    """A handoff schema (consumes or produces section) for a plugin capability."""
    plugin_name: str
    capability_name: str
    fields: Dict[str, Field]  # field_name → Field


class SchemaRegistry:
    """In-memory registry of extracted schemas from all INTEROP.md files."""

    def __init__(self):
        """Initialize empty registry."""
        self.schemas: Dict[str, Dict[str, Schema]] = {}  # {plugin: {capability: Schema}}
        self.file_hashes: Dict[str, str] = {}  # {file_path: sha256_hash}

    def get_schema(self, plugin_name: str, capability_name: str) -> Optional[Schema]:
        """Retrieve a schema by plugin and capability name.

        Args:
            plugin_name: Name of the plugin (e.g., "agent-tdd")
            capability_name: Name of the capability (e.g., "design_spec_slicing")

        Returns:
            Schema object if found, None otherwise.
        """
        if plugin_name not in self.schemas:
            return None
        return self.schemas[plugin_name].get(capability_name)

    def get_capability_consumes(self, plugin_name: str, capability_name: str) -> Dict[str, str]:
        """Get consumes schema as Dict[field_name: type_name] for a capability.

        This is the shape expected by interop_parser.py's Capability.consumes field.

        Args:
            plugin_name: Name of the plugin
            capability_name: Name of the capability

        Returns:
            Dict mapping field names to type names, or empty dict if not found.
        """
        schema = self.get_schema(plugin_name, capability_name)
        if not schema:
            return {}
        return {field.name: field.type_name for field in schema.fields.values()}

    def add_schema(self, schema: Schema):
        """Add a schema to the registry.

        Args:
            schema: Schema object to add.
        """
        if schema.plugin_name not in self.schemas:
            self.schemas[schema.plugin_name] = {}
        self.schemas[schema.plugin_name][schema.capability_name] = schema


class SchemaExtractor:
    """Parse INTEROP.md files and extract schemas."""

    # Known plugin INTEROP file locations
    PLUGIN_INTEROP_PATHS = {
        "agent-isdd": "agent-isdd/INTEROP.md",
        "agent-tdd": "agent-tdd/INTEROP.md",
        "code-reviewer": "code-reviewer/INTEROP.md",
        "plugin-orchestrator": "plugin-orchestrator/INTEROP.md",
        "agent-nelly": "agent-nelly/INTEROP.md",
        "agent-ux": "agent-ux/INTEROP.md",
        "agent-cache-plugin": "agent-cache-plugin/STRUCTURE.md",
    }

    # Mapping of plugin name to expected capability names
    EXPECTED_CAPABILITIES = {
        "agent-isdd": ["design_spec_handoff"],
        "agent-tdd": ["design_spec_slicing"],
        "code-reviewer": ["code_review"],
        "agent-nelly": ["memory_brief"],
        "agent-cache-plugin": ["phase_state_cache"],
        "agent-ux": ["render_event"],
    }

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize schema extractor.

        Args:
            base_dir: Base directory containing plugin folders (e.g., ~/.claude/plugins/claude-plugins).
                     If None, attempts to locate automatically.
        """
        self.base_dir = base_dir or self._locate_plugin_base()
        self.registry = SchemaRegistry()

    @staticmethod
    def _locate_plugin_base() -> Path:
        """Locate the base plugin directory.

        Returns:
            Path to plugin base directory.

        Raises:
            FileNotFoundError if base directory cannot be found.
        """
        import os

        # Try environment variable first
        env_dir = os.environ.get("CLAUDE_PLUGINS_DIR")
        if env_dir:
            path = Path(os.path.expanduser(os.path.expandvars(env_dir)))
            if path.exists():
                return path

        # Try standard bootstrap location
        default_dir = Path.home() / ".claude" / "plugins" / "claude-plugins"
        if default_dir.exists():
            return default_dir

        # Try relative to this file
        rel_dir = Path(__file__).parent.parent.parent
        if (rel_dir / "agent-isdd").exists():
            return rel_dir

        raise FileNotFoundError("Cannot locate plugin base directory")

    def extract_from_file(self, file_path: Path) -> Optional[str]:
        """Extract file content and return its sha256 hash.

        Args:
            file_path: Path to INTEROP.md file.

        Returns:
            File content as string, or None if file not found.
        """
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            return content
        except (FileNotFoundError, IOError) as e:
            logger.warning(f"Cannot read {file_path}: {e}")
            return None

    def parse_markdown_table(self, table_text: str) -> List[Tuple[str, str, bool]]:
        """Parse a markdown table and extract (field_name, type_name, required) tuples.

        Expected format:
        | Field | Type | Required |
        |-------|------|----------|
        | field_name | string | yes |
        | field_name2 | object | no |

        Args:
            table_text: Raw markdown table text.

        Returns:
            List of (field_name, type_name, required_bool) tuples.
        """
        rows = []
        lines = table_text.strip().split('\n')
        in_data_section = False

        for i, line in enumerate(lines):
            # Skip empty lines and separator lines
            if not line.strip() or line.strip().startswith('|---'):
                in_data_section = False
                continue

            # Skip header row (contains "Field" and "Type" as column names)
            if '| Field |' in line and '| Type |' in line:
                in_data_section = False
                continue

            # Only start collecting data after we've seen a header and separator
            if i > 0 and line.strip().startswith('|') and '|' in line:
                # Extract cells from | field | type | required | ...
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if len(cells) < 2:
                    continue

                field_name = cells[0]
                type_name = cells[1]

                # Skip if field_name looks like a header (e.g., "Field" or starts with space)
                if field_name.lower() == 'field' or field_name.startswith(' '):
                    continue

                required = len(cells) > 2 and cells[2].lower() in ('yes', 'true', 'required')
                rows.append((field_name, type_name, required))

        return rows

    def extract_schema_from_content(
        self,
        plugin_name: str,
        capability_name: str,
        content: str
    ) -> Optional[Schema]:
        """Extract a schema from INTEROP.md content.

        Looks for markdown table sections with "Consumes" or "Produces" headers.

        Args:
            plugin_name: Name of the plugin.
            capability_name: Name of the capability.
            content: Full INTEROP.md content.

        Returns:
            Schema object if found, None otherwise.
        """
        # Look for a markdown table with field definitions
        # Pattern: | Field | Type | Required | followed by rows
        table_pattern = r'\| Field \| Type \| Required \|[^\|]*\|[^\|]*\|[^\|]*\|([^#]+?)(?=^##|\Z)'

        matches = re.finditer(table_pattern, content, re.MULTILINE | re.DOTALL)

        for match in matches:
            table_text = match.group(0)

            # Try to parse as markdown table
            try:
                rows = self.parse_markdown_table(table_text)
                if not rows:
                    continue

                # Build Field objects
                fields = {}
                for field_name, type_name, required in rows:
                    fields[field_name] = Field(
                        name=field_name,
                        type_name=type_name,
                        required=required
                    )

                if fields:
                    return Schema(
                        plugin_name=plugin_name,
                        capability_name=capability_name,
                        fields=fields
                    )
            except Exception as e:
                logger.warning(f"Error parsing table in {plugin_name}: {e}")
                continue

        return None

    def extract_all_plugins(self) -> SchemaRegistry:
        """Extract schemas from all plugin INTEROP.md files.

        Returns:
            Populated SchemaRegistry with all extracted schemas.
        """
        for plugin_name, interop_path in self.PLUGIN_INTEROP_PATHS.items():
            file_path = self.base_dir / interop_path
            content = self.extract_from_file(file_path)

            if not content:
                logger.warning(f"Skipping {plugin_name} (file not found)")
                continue

            # Calculate and cache file hash for change detection
            file_hash = hashlib.sha256(content.encode()).hexdigest()
            self.registry.file_hashes[str(file_path)] = file_hash

            # Extract schemas for expected capabilities
            expected_caps = self.EXPECTED_CAPABILITIES.get(plugin_name, [])
            for capability_name in expected_caps:
                schema = self.extract_schema_from_content(
                    plugin_name,
                    capability_name,
                    content
                )

                if schema:
                    self.registry.add_schema(schema)
                    logger.debug(f"Extracted schema: {plugin_name}:{capability_name}")
                else:
                    logger.warning(f"No schema found for {plugin_name}:{capability_name}")

        return self.registry

    def validate_schemas_against_code(self) -> List[str]:
        """Validate extracted schemas against hardcoded schemas in interop_parser.py.

        Returns:
            List of drift errors (empty if all schemas match).
        """
        from orchestrator.interop_parser import CapabilityMap

        errors = []

        # Create a CapabilityMap to get hardcoded schemas
        try:
            capability_map = CapabilityMap(plugin_dir_base=str(self.base_dir))
        except Exception as e:
            logger.error(f"Cannot create CapabilityMap: {e}")
            return [f"Cannot validate schemas: {e}"]

        # For each plugin and capability, compare schemas
        for plugin_name, capability_map_obj in self.registry.schemas.items():
            plugin_info = capability_map.get_plugin(plugin_name)
            if not plugin_info:
                continue

            for capability_name, schema in capability_map_obj.items():
                # Find corresponding capability in CapabilityMap
                capability = None
                for cap in plugin_info.capabilities:
                    if cap.id == capability_name:
                        capability = cap
                        break

                if not capability:
                    errors.append(
                        f"{plugin_name}:{capability_name} not found in CapabilityMap"
                    )
                    continue

                # Compare consumes schemas
                extracted_consumes = {f.name: f.type_name for f in schema.fields.values()}
                hardcoded_consumes = capability.consumes or {}

                # Check for missing fields
                for field_name in extracted_consumes:
                    if field_name not in hardcoded_consumes:
                        errors.append(
                            f"{plugin_name}:{capability_name} — field '{field_name}' "
                            f"in INTEROP.md but not in interop_parser.py"
                        )

                # Check for extra fields
                for field_name in hardcoded_consumes:
                    if field_name not in extracted_consumes:
                        errors.append(
                            f"{plugin_name}:{capability_name} — field '{field_name}' "
                            f"in interop_parser.py but not documented in INTEROP.md"
                        )

                # Check for type mismatches
                for field_name in extracted_consumes:
                    if field_name in hardcoded_consumes:
                        extracted_type = extracted_consumes[field_name]
                        hardcoded_type = hardcoded_consumes[field_name]
                        if extracted_type != hardcoded_type:
                            errors.append(
                                f"{plugin_name}:{capability_name}.{field_name} — "
                                f"type mismatch: INTEROP.md says '{extracted_type}', "
                                f"interop_parser.py says '{hardcoded_type}'"
                            )

        return errors


def main():
    """CLI entry point for schema validation."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Extract and validate handoff schemas from INTEROP.md files"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for drift between INTEROP.md and interop_parser.py"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=None,
        help="Base directory containing plugin folders"
    )

    args = parser.parse_args()

    try:
        base_dir = Path(args.base_dir) if args.base_dir else None
        extractor = SchemaExtractor(base_dir=base_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.check:
        # Extract all schemas
        registry = extractor.extract_all_plugins()

        # Validate against code
        errors = extractor.validate_schemas_against_code()

        if errors:
            print("Schema Validation FAILED:")
            for error in errors:
                print(f"  ✗ {error}")
            sys.exit(1)
        else:
            print("Schema Validation PASSED — all INTEROP.md schemas match interop_parser.py")
            sys.exit(0)
    else:
        # Just extract and print
        registry = extractor.extract_all_plugins()

        print("Extracted Schemas:")
        for plugin_name, capabilities in sorted(registry.schemas.items()):
            print(f"\n{plugin_name}:")
            for capability_name, schema in capabilities.items():
                print(f"  {capability_name}:")
                for field_name, field in schema.fields.items():
                    req = "required" if field.required else "optional"
                    print(f"    - {field_name}: {field.type_name} ({req})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
