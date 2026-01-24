#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
TEMPLATE_PATH = DOCS_DIR / "_index.mdx"
OUTPUT_PATH = DOCS_DIR / "index.mdx"
PLACEHOLDER = "$$AGENTS_CARDS$$"


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _escape_text(text: str) -> str:
    return _escape_html(text).replace("\n", " ")


def _sanitize_svg(svg: str) -> str:
    svg = svg.strip()
    svg = re.sub(r'\s(width|height)="[^"]*"', "", svg)
    svg = re.sub(r'\sclass="[^"]*"', "", svg)
    svg = re.sub(
        r"<svg\b",
        (
            '<svg width="20" height="20" '
            'className="agent-icon" '
            'aria-hidden="true" focusable="false"'
        ),
        svg,
        count=1,
    )
    replacements = {
        "fill-rule": "fillRule",
        "clip-rule": "clipRule",
        "clip-path": "clipPath",
        "stroke-width": "strokeWidth",
        "stroke-linecap": "strokeLinecap",
        "stroke-linejoin": "strokeLinejoin",
        "stroke-miterlimit": "strokeMiterlimit",
        "stroke-dasharray": "strokeDasharray",
        "stroke-dashoffset": "strokeDashoffset",
        "stroke-opacity": "strokeOpacity",
        "fill-opacity": "fillOpacity",
        "stop-color": "stopColor",
        "stop-opacity": "stopOpacity",
        "vector-effect": "vectorEffect",
    }
    for old, new in replacements.items():
        svg = svg.replace(f"{old}=", f"{new}=")
    return svg


def _load_icon_svg(agent: dict) -> str:
    icon_src = agent["_dir"] / "icon.svg"
    if not icon_src.exists():
        return ""
    return _sanitize_svg(icon_src.read_text())


def _load_agents() -> list[dict]:
    agents: list[dict] = []
    for entry in sorted(ROOT.iterdir()):
        if not entry.is_dir():
            continue
        agent_file = entry / "agent.json"
        if not agent_file.exists():
            continue
        data = json.loads(agent_file.read_text())
        data["_dir"] = entry
        agents.append(data)
    agents.sort(key=lambda agent: agent.get("name", "").lower())
    return agents


def _render_agent_cards(agents: list[dict]) -> str:
    lines: list[str] = ["<Columns cols={2}>"]

    for agent in agents:
        agent_id = agent.get("id", "-")
        name = agent.get("name", agent_id)
        description = _escape_text(agent.get("description", "-"))
        version = _escape_text(agent.get("version", "-"))
        repository = agent.get("repository", "")
        icon_svg = _load_icon_svg(agent)

        lines.append("  <Card")
        lines.append(f'    title="{_escape_html(name)}"')
        if icon_svg:
            lines.append("    icon={")
            for line in icon_svg.splitlines():
                lines.append(f"      {line}")
            lines.append("    }")
        if repository:
            lines.append(f'    href="{_escape_html(repository)}"')
            lines.append('    arrow="true"')
        lines.append("  >")
        lines.append(f"    {description}")
        version_text = version if version not in ("", "-") else "version unknown"
        lines.append(f"    <p><code>{_escape_text(version_text)}</code></p>")
        lines.append("  </Card>")

    lines.append("</Columns>")
    return "\n".join(lines)


def main() -> None:
    agents = _load_agents()
    template = TEMPLATE_PATH.read_text()
    cards = _render_agent_cards(agents)
    output = template.replace(PLACEHOLDER, cards)
    OUTPUT_PATH.write_text(output)


if __name__ == "__main__":
    main()
