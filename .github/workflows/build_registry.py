#!/usr/bin/env python3
"""Build aggregated registry.json from individual agent directories."""

import json
import os
import re
import sys
from pathlib import Path

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

REGISTRY_VERSION = "1.0.0"
SKIP_DIRS = {".claude", ".git", ".github", ".idea", "__pycache__", "dist"}
REQUIRED_FIELDS = {"id", "name", "version", "description", "distribution"}
VALID_DISTRIBUTION_TYPES = {"binary", "npx", "bunx", "uvx"}
VALID_PLATFORMS = {
    "darwin-aarch64",
    "darwin-x86_64",
    "linux-aarch64",
    "linux-x86_64",
    "windows-aarch64",
    "windows-x86_64",
}

# Can be overridden via environment variable
DEFAULT_BASE_URL = "https://github.com/agentclientprotocol/registry/releases/latest/download"

# Icon requirements
PREFERRED_ICON_SIZE = 16


def validate_icon(icon_path: Path) -> list[str]:
    """Validate icon.svg and return list of warnings/errors."""
    errors = []

    try:
        content = icon_path.read_text()
    except Exception as e:
        errors.append(f"Cannot read icon: {e}")
        return errors

    # Extract width and height from SVG
    width_match = re.search(r'<svg[^>]*\swidth=["\'](\d+)', content)
    height_match = re.search(r'<svg[^>]*\sheight=["\'](\d+)', content)

    # Try viewBox if width/height not found
    if not width_match or not height_match:
        viewbox_match = re.search(r'viewBox=["\'][\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)', content)
        if viewbox_match:
            vb_width = float(viewbox_match.group(1))
            vb_height = float(viewbox_match.group(2))
        else:
            errors.append("Icon missing width/height attributes and viewBox")
            return errors
    else:
        vb_width = float(width_match.group(1))
        vb_height = float(height_match.group(1))

    # Check size
    if vb_width != vb_height:
        errors.append(f"Icon must be square (got {vb_width}x{vb_height})")

    if vb_width != PREFERRED_ICON_SIZE or vb_height != PREFERRED_ICON_SIZE:
        errors.append(f"Icon should be {PREFERRED_ICON_SIZE}x{PREFERRED_ICON_SIZE} (got {int(vb_width)}x{int(vb_height)})")

    return errors


def get_base_url():
    """Get base URL from environment or use default."""
    return os.environ.get("REGISTRY_BASE_URL", DEFAULT_BASE_URL)


def load_schema(registry_dir: Path) -> dict | None:
    """Load agent.schema.json if available."""
    schema_path = registry_dir / "agent.schema.json"
    if not schema_path.exists():
        return None
    try:
        with open(schema_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not load agent.schema.json: {e}")
        return None


def validate_against_schema(agent: dict, schema: dict) -> list[str]:
    """Validate agent against JSON schema."""
    if not HAS_JSONSCHEMA:
        return []

    errors = []
    try:
        jsonschema.validate(instance=agent, schema=schema)
    except jsonschema.ValidationError as e:
        # Get the path to the error
        path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        errors.append(f"Schema validation error at '{path}': {e.message}")
    except jsonschema.SchemaError as e:
        errors.append(f"Invalid schema: {e.message}")

    return errors


def validate_agent(agent: dict, agent_dir: str, schema: dict | None = None) -> list[str]:
    """Validate agent.json and return list of errors."""
    errors = []

    # Validate against JSON schema first
    if schema is not None:
        schema_errors = validate_against_schema(agent, schema)
        if schema_errors:
            errors.extend(schema_errors)
            return errors  # Return early if schema validation fails

    # Check required fields
    missing = REQUIRED_FIELDS - set(agent.keys())
    if missing:
        errors.append(f"Missing required fields: {', '.join(sorted(missing))}")

    # Validate id format
    if "id" in agent:
        agent_id = agent["id"]
        if not agent_id:
            errors.append("Field 'id' cannot be empty")
        elif not agent_id[0].isalpha():
            errors.append("Field 'id' must start with a letter")
        elif not all(c.islower() or c.isdigit() or c == "-" for c in agent_id):
            errors.append("Field 'id' must be lowercase with hyphens only")
        elif agent_id != agent_dir:
            errors.append(f"Field 'id' ({agent_id}) must match directory name ({agent_dir})")

    # Validate version format
    if "version" in agent:
        version = agent["version"]
        parts = version.split(".")
        if len(parts) < 3 or not all(p.isdigit() for p in parts[:3]):
            errors.append(f"Field 'version' ({version}) must be semantic version (e.g., 1.0.0)")

    # Validate distribution
    if "distribution" in agent:
        dist = agent["distribution"]
        if not isinstance(dist, dict) or not dist:
            errors.append("Field 'distribution' must be a non-empty object")
        else:
            unknown_types = set(dist.keys()) - VALID_DISTRIBUTION_TYPES
            if unknown_types:
                errors.append(f"Unknown distribution types: {', '.join(sorted(unknown_types))}")

            # Validate binary platforms
            if "binary" in dist:
                binary = dist["binary"]
                if not isinstance(binary, dict) or not binary:
                    errors.append("Field 'distribution.binary' must be a non-empty object")
                else:
                    unknown_platforms = set(binary.keys()) - VALID_PLATFORMS
                    if unknown_platforms:
                        errors.append(f"Unknown platforms: {', '.join(sorted(unknown_platforms))}")

                    for platform, target in binary.items():
                        if platform in VALID_PLATFORMS:
                            if "archive" not in target:
                                errors.append(f"Platform {platform} missing 'archive' field")
                            if "cmd" not in target:
                                errors.append(f"Platform {platform} missing 'cmd' field")

            # Validate package distributions
            for dist_type in ("npx", "bunx", "uvx"):
                if dist_type in dist:
                    pkg_dist = dist[dist_type]
                    if "package" not in pkg_dist:
                        errors.append(f"Distribution '{dist_type}' missing 'package' field")

    return errors


def build_registry():
    """Build registry.json from agent directories."""
    registry_dir = Path(__file__).parent.parent.parent
    base_url = get_base_url()
    agents = []
    seen_ids = {}
    has_errors = False

    # Load schema for validation
    schema = load_schema(registry_dir)
    if schema and not HAS_JSONSCHEMA:
        print("Warning: jsonschema not installed, skipping schema validation")
        print("  Install with: pip install jsonschema")

    for agent_dir in sorted(registry_dir.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name in SKIP_DIRS:
            continue

        agent_json_path = agent_dir / "agent.json"
        if not agent_json_path.exists():
            print(f"Warning: {agent_dir.name}/ has no agent.json, skipping")
            continue

        # Parse JSON with error handling
        try:
            with open(agent_json_path) as f:
                agent = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: {agent_dir.name}/agent.json is invalid JSON: {e}")
            has_errors = True
            continue

        # Validate agent
        errors = validate_agent(agent, agent_dir.name, schema)
        if errors:
            print(f"Error: {agent_dir.name}/agent.json validation failed:")
            for error in errors:
                print(f"  - {error}")
            has_errors = True
            continue

        # Check for duplicate IDs
        agent_id = agent["id"]
        if agent_id in seen_ids:
            print(f"Error: Duplicate agent ID '{agent_id}' in {agent_dir.name}/ (already in {seen_ids[agent_id]}/)")
            has_errors = True
            continue
        seen_ids[agent_id] = agent_dir.name

        # Validate and set icon URL if icon exists
        icon_path = agent_dir / "icon.svg"
        if icon_path.exists():
            icon_errors = validate_icon(icon_path)
            if icon_errors:
                print(f"Warning: {agent_dir.name}/icon.svg:")
                for error in icon_errors:
                    print(f"  - {error}")
            agent["icon"] = f"{base_url}/{agent_id}.svg"

        agents.append(agent)
        print(f"Added: {agent_id} v{agent['version']}")

    if has_errors:
        print("\nBuild failed due to validation errors")
        sys.exit(1)

    if not agents:
        print("\nWarning: No agents found")

    registry = {
        "version": REGISTRY_VERSION,
        "agents": agents,
    }

    # Create dist directory
    dist_dir = registry_dir / "dist"
    dist_dir.mkdir(exist_ok=True)

    # Write registry.json
    output_path = dist_dir / "registry.json"
    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")

    # Copy icons to dist
    for agent in agents:
        agent_id = agent["id"]
        icon_src = registry_dir / agent_id / "icon.svg"
        if icon_src.exists():
            icon_dst = dist_dir / f"{agent_id}.svg"
            icon_dst.write_bytes(icon_src.read_bytes())

    print(f"\nBuilt dist/ with {len(agents)} agents")


if __name__ == "__main__":
    build_registry()
