# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands

```bash
# Build registry (validates all agents and outputs to dist/)
uv run --with jsonschema .github/workflows/build_registry.py

# Build without schema validation (if jsonschema not available)
python .github/workflows/build_registry.py
```

## Architecture

This is a registry of ACP (Agent Client Protocol) agents and extensions. The structure is:

```
<id>/
├── agent.json      # Agent metadata and distribution info
├── extension.json  # OR extension metadata (same schema as agent.json)
└── icon.svg        # Icon: 16x16 SVG, monochrome with currentColor (optional)
```

Each directory contains either `agent.json` (for agents) or `extension.json` (for extensions), but not both. Extensions use the same schema as agents (`agent.schema.json`).

**Build process** (`.github/workflows/build_registry.py`):
1. Scans directories for `agent.json` or `extension.json` files
2. Validates against `agent.schema.json` (JSON Schema)
3. Validates icons (16x16 SVG, monochrome with `currentColor`)
4. Aggregates into `dist/registry.json` with separate `agents` and `extensions` arrays
5. Copies icons to `dist/<id>.svg`

**CI/CD** (`.github/workflows/build-registry.yml`):
- PRs: Runs validation only
- Push to main: Validates, then publishes versioned + `latest` GitHub releases

## Validation Rules

- `id`: lowercase, hyphens only, must match directory name
- `version`: semantic versioning (e.g., `1.0.0`)
- `distribution`: at least one of `binary`, `npx`, `uvx`
- `icon.svg`: must be SVG format, 16x16, monochrome using `currentColor` (enables theming)
- **URL validation**: All distribution URLs must be accessible (binary archives, npm/PyPI packages)

Set `SKIP_URL_VALIDATION=1` to bypass URL checks during local development.

## Updating Agent Versions

### Automated Updates

Agent versions are automatically updated via `.github/workflows/update-versions.yml`:
- **Schedule:** Runs hourly (cron: `0 * * * *`)
- **Scope:** Checks all agents in root and `_not_yet_unsupported/`
- **Supported distributions:** `npx` (npm), `uvx` (PyPI), `binary` (GitHub releases)

```bash
# Dry run - check for available updates
uv run .github/workflows/update_versions.py

# Apply updates locally
uv run .github/workflows/update_versions.py --apply

# Check specific agents only
uv run .github/workflows/update_versions.py --agents gemini,github-copilot
```

The workflow can also be triggered manually via GitHub Actions with options to apply updates and filter by agent IDs.

### Manual Updates

To update agents manually:

1. **For npm packages** (`npx` distribution): Check latest version at `https://registry.npmjs.org/<package>/latest`
2. **For GitHub binaries** (`binary` distribution): Check latest release at `https://api.github.com/repos/<owner>/<repo>/releases/latest`

Update `agent.json`:
- Update the `version` field
- Update version in all distribution URLs (use replace-all for consistency)
- For npm: update `package` field (e.g., `@google/gemini-cli@0.22.5`)
- For binaries: update archive URLs with new version/tag

Run build to validate: `uv run --with jsonschema .github/workflows/build_registry.py`

**Note:** Agents in `_not_yet_unsupported/` should remain there - do not move them to the main registry. They can still have their versions updated in place.

## Distribution Types

- `binary`: Platform-specific archives (`darwin-aarch64`, `linux-x86_64`, etc.)
- `npx`: npm packages
- `uvx`: PyPI packages

## Icon Requirements

Icons must be:
- **SVG format** (only `.svg` files accepted)
- **16x16 dimensions** (via width/height attributes or viewBox)
- **Monochrome using `currentColor`** - all fills and strokes must use `currentColor` or `none`

Using `currentColor` enables icons to adapt to different themes (light/dark mode) automatically.

**Valid example:**
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <path fill="currentColor" d="M..."/>
</svg>
```

**Invalid patterns:**
- Hardcoded colors: `fill="#FF5500"`, `fill="red"`, `stroke="rgb(0,0,0)"`
- Missing currentColor: `fill` or `stroke` without `currentColor`

## Documentation Site

The registry has a documentation site built with [Mintlify](https://mintlify.com/) in the `docs/` folder.

### Structure

```
docs/
├── docs.json          # Mintlify configuration
├── _index.mdx         # Template for index page (contains $$AGENTS_CARDS$$ placeholder)
├── index.mdx          # Generated index page with agent cards
├── registry.mdx       # Registry format documentation
└── logo/              # Logo assets
```

### Commands

```bash
# Generate docs (regenerates index.mdx from template)
uv run .github/workflows/generate_mintlify_agents.py

# Run local dev server
cd docs && npx mintlify dev --port 3000
```

### How It Works

1. `_index.mdx` is a template containing `$$AGENTS_CARDS$$` placeholder
2. `generate_mintlify_agents.py` reads all `agent.json` files from the registry
3. Generates `<Card>` components for each agent with name, description, version, and icon
4. Icons are inlined as sanitized SVG (converted to JSX-compatible attributes)
5. Replaces placeholder and writes to `index.mdx`

### Automation

Docs are automatically regenerated when agent versions are updated:
- The `update-versions.yml` workflow runs `generate_mintlify_agents.py` after applying updates
- Changes to `docs/index.mdx` are committed along with version updates

### Adding New Pages

1. Create new `.mdx` file in `docs/`
2. Add the page name (without extension) to `docs.json` navigation
