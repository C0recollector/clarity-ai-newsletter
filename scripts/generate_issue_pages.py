"""Generate newsletter edition pages from a structured issue JSON file.

This first generator preserves the current hand-designed HTML as the template
surface and synchronizes the issue-driven fields that should stay consistent
between the editorial model and the published pages.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import date
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ISSUE = ROOT / "data" / "issues" / "2026-05-11.json"

TECHNICAL_SECTION_MAP = {
    "model-news": {
        "id": "model-routing",
        "title": "Model Routing: Stop Asking for One Best Model",
        "nav": "Model Routing",
        "nav_summary": "Portfolio design, evals, cost tiers, fallback paths.",
    },
    "agents": {
        "id": "agent-architecture",
        "title": "Agent Architecture: Workflow First, Memory Later",
        "nav": "Agent Architecture",
        "nav_summary": "Roles, artifacts, permissions, validation, review gates.",
    },
    "platforms": {
        "id": "platform-integrations",
        "title": "Platform Integrations: AI Is Moving to the Point of Work",
        "nav": "Platform Integrations",
        "nav_summary": "Search, browser, desktop, creative, and workflow surfaces.",
    },
    "infrastructure": {
        "id": "compute-ops",
        "title": "Compute Ops: Capacity Is Now an Architecture Constraint",
        "nav": "Compute Ops",
        "nav_summary": "Capacity, latency, token cost, resilience, data boundaries.",
    },
    "power-moves": {
        "id": "vendor-risk",
        "title": "Vendor Risk: Governance, Ads, and Compute Deals Matter",
        "nav": "Vendor Risk",
        "nav_summary": "Governance, incentives, ads, partnerships, lock-in.",
    },
}


def load_issue(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_if_changed(path: Path, content: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def week_label(week_of: str) -> str:
    year, month, day = (int(part) for part in week_of.split("-"))
    return f"Week of {date(year, month, day):%B %-d, %Y}"


def portable_week_label(week_of: str) -> str:
    try:
        return week_label(week_of)
    except ValueError:
        year, month, day = (int(part) for part in week_of.split("-"))
        parsed = date(year, month, day)
        return f"Week of {parsed:%B} {parsed.day}, {parsed.year}"


def section_href(section: dict) -> str:
    return f"#{section['id']}"


def executive_nav(sections: list[dict]) -> str:
    cards = []
    for section in sections:
        cards.append(
            '        <a class="nav-card" href="{href}"><b>{title}</b><span>{summary}</span></a>'.format(
                href=escape(section_href(section)),
                title=escape(section["title"]),
                summary=escape(section.get("summary", "")),
            )
        )
    return "\n".join(cards)


def technical_nav(sections: list[dict]) -> str:
    cards = []
    for section in sections:
        mapped = TECHNICAL_SECTION_MAP.get(section["id"], {})
        href = f"#{mapped.get('id', section['id'])}"
        cards.append(
            '        <a href="{href}"><b>{title}</b><span>{summary}</span></a>'.format(
                href=escape(href),
                title=escape(mapped.get("nav", section["title"])),
                summary=escape(mapped.get("nav_summary", section.get("summary", ""))),
            )
        )
    return "\n".join(cards)


def replace_once(content: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"Expected one match for {label}, found {count}.")
    return updated


def replace_all(content: str, pattern: str, replacement: str, label: str, expected: int | None = None) -> str:
    updated, count = re.subn(pattern, replacement, content, flags=re.S)
    if expected is not None and count != expected:
        raise RuntimeError(f"Expected {expected} matches for {label}, found {count}.")
    if count == 0:
        raise RuntimeError(f"Expected at least one match for {label}.")
    return updated


def sync_common(content: str, issue: dict, edition_label: str, hero_prefix: str) -> str:
    item = issue["issue"]
    hero = Path(issue["assets"]["hero"]).name
    hero_url = f'{hero_prefix}{hero}'
    generated = f"<!-- Generated from data/issues/{item['id']}.json by scripts/generate_issue_pages.py. -->"

    if "<!-- Generated from data/issues/" in content:
        content = replace_once(content, r"<!-- Generated from data/issues/.*? -->", generated, "generated comment")
    else:
        content = content.replace("<head>", f"<head>\n  {generated}", 1)

    content = replace_once(content, r"<h1>.*?</h1>", f"<h1>{escape(item['title'])}</h1>", "hero title")
    content = replace_once(content, r'<p class="dek">.*?</p>', f'<p class="dek">{escape(item["dek"])}</p>', "dek")
    content = replace_all(
        content,
        r'url\(".*?ai-infrastructure-hero\.png"\)',
        f'url("{hero_url}")',
        "hero CSS urls",
    )
    content = content.replace("AI infrastructure hero graphic", escape(f"{item['title']} hero graphic"))
    content = replace_once(
        content,
        r"<title>.*?</title>",
        f"<title>{escape(item['title'])} - {escape(edition_label)}</title>",
        "page title",
    )
    content = replace_once(
        content,
        r"<span class=\"pill\">Week of .*?</span>",
        f'<span class="pill">{escape(portable_week_label(item["week_of"]))}</span>',
        "week pill",
    )
    return content


def sync_executive(content: str, issue: dict) -> str:
    sections = sorted(deepcopy(issue["sections"]), key=lambda section: section["order"])
    content = sync_common(content, issue, "Executive Brief", "../assets/")
    content = replace_once(
        content,
        r'<nav class="nav-strip"(?: aria-label="[^"]*")?>\s*.*?\s*</nav>',
        '<nav class="nav-strip" aria-label="Top signals">\n' + executive_nav(sections) + "\n      </nav>",
        "executive nav",
    )

    for index, section in enumerate(sections, start=1):
        section_id = re.escape(section["id"])
        title = escape(section.get("headline") or section["title"])
        summary = escape(section.get("summary", ""))
        pattern = (
            rf'(<section class="signal" id="{section_id}">\s*'
            rf'<div class="signal-head">\s*<div>\s*<h2>).*?(</h2>\s*<p>).*?(</p>\s*</div>\s*<div class="signal-num">)'
        )
        replacement = rf"\g<1>{title}\g<2>{summary}\g<3>"
        content = replace_once(content, pattern, replacement, f"executive section {section['id']}")
    return content


def sync_technical(content: str, issue: dict) -> str:
    sections = sorted(deepcopy(issue["sections"]), key=lambda section: section["order"])
    content = sync_common(content, issue, "Technical Edition", "../../assets/")
    content = replace_once(
        content,
        r'<nav aria-label="Technical signals">\s*.*?\s*</nav>',
        '<nav aria-label="Technical signals">\n' + technical_nav(sections) + "\n      </nav>",
        "technical nav",
    )

    for section in sections:
        mapped = TECHNICAL_SECTION_MAP.get(section["id"], {"id": section["id"], "title": section.get("headline", section["title"])})
        section_id = re.escape(mapped["id"])
        title = escape(mapped["title"])
        summary = escape(section.get("summary", ""))
        pattern = (
            rf'(<section class="signal" id="{section_id}">\s*'
            rf'<div class="signal-head"><div><h2>).*?(</h2><p>).*?(</p></div><div class="num">)'
        )
        replacement = rf"\g<1>{title}\g<2>{summary}\g<3>"
        content = replace_once(content, pattern, replacement, f"technical section {section['id']}")
    return content


def edition_path(issue: dict, edition_id: str) -> Path:
    for edition in issue["issue"]["editions"]:
        if edition["id"] == edition_id:
            return ROOT / edition["path"]
    raise RuntimeError(f"No edition path found for {edition_id}.")


def generate(issue_path: Path) -> list[tuple[Path, bool]]:
    issue = load_issue(issue_path)
    executive_path = edition_path(issue, "executive")
    technical_path = edition_path(issue, "technical")

    executive = sync_executive(executive_path.read_text(encoding="utf-8"), issue)
    technical = sync_technical(technical_path.read_text(encoding="utf-8"), issue)

    return [
        (executive_path, write_if_changed(executive_path, executive)),
        (technical_path, write_if_changed(technical_path, technical)),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate newsletter pages from an issue JSON model.")
    parser.add_argument("issue", nargs="?", default=DEFAULT_ISSUE, type=Path)
    args = parser.parse_args()

    results = generate(args.issue.resolve())
    for path, changed in results:
        status = "updated" if changed else "unchanged"
        print(f"{status}: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
