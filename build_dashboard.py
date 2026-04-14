#!/usr/bin/env python3
"""Build a local dashboard UI for the roofing wiki.

The output is a self-contained HTML file that can be opened directly in a
browser. It reads the wiki index and page content, then renders a command
center for planning, implementation, and learning.
"""

from __future__ import annotations

import argparse
import json
import re
import webbrowser
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = TOOLS_DIR
SOURCE_ROOT = DASHBOARD_DIR.parent / "Roofing company"
WIKI_DIR = SOURCE_ROOT / "wiki"
OUTPUT_DIR = DASHBOARD_DIR
OUTPUT_FILE = OUTPUT_DIR / "index.html"
BASE_PATH = "../Roofing company/"


PLAN_KEYWORDS = (
    "roadmap",
    "strategy",
    "benchmark",
    "opportunity",
    "research",
    "compliance",
    "acquisition",
    "marketing",
    "advertising",
    "storm",
    "priority",
    "map",
    "analysis",
    "execution plan",
    "next step",
)

IMPLEMENT_KEYWORDS = (
    "sop",
    "checklist",
    "workflow",
    "system",
    "calendar",
    "template",
    "kit",
    "cadence",
    "playbook",
    "guide",
    "bank",
    "capture",
    "intake",
    "sla",
    "photo",
    "content",
    "tracking",
    "verification",
)

LEARN_KEYWORDS = (
    "index",
    "glossary",
    "101",
    "atlas",
    "fundamentals",
    "faq",
    "library",
    "repair vs replace",
    "inspection",
    "estimating",
    "learning",
    "damage",
    "trade",
)

ENTITY_IMPLEMENT_KEYWORDS = (
    "gbp",
    "xactimate",
    "hover",
    "eagleview",
    "jobnimbus",
    "oneclickcode",
    "crm",
)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())
def parse_frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---"):
        return {}

    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}

    frontmatter: dict[str, object] = {}
    for raw_line in lines[1:end]:
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            try:
                frontmatter[key] = json.loads(value.replace("'", '"'))
            except json.JSONDecodeError:
                frontmatter[key] = [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
        else:
            frontmatter[key] = value.strip("'\"")
    return frontmatter


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def extract_wikilinks(text: str) -> list[str]:
    return re.findall(r"\[\[([^\]]+)\]\]", text)


def extract_summary(text: str) -> str:
    if not text:
        return ""

    summary_match = re.search(
        r"^##\s+Summary\s*$\n+(.+?)(?=\n##\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if summary_match:
        block = summary_match.group(1)
        paragraph = first_paragraph(block)
        if paragraph:
            return paragraph

    body = text.split("---", 2)
    if len(body) == 3:
        text = body[2]

    return first_paragraph(text)


def first_paragraph(text: str) -> str:
    paragraphs = []
    current = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        if line.startswith("#"):
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        if line.startswith("- ") and not current:
            current.append(line[2:].strip())
            paragraphs.append(" ".join(current).strip())
            current = []
            continue
        if line.startswith("> "):
            line = line[2:].strip()
        current.append(line)

    if current:
        paragraphs.append(" ".join(current).strip())

    for paragraph in paragraphs:
        if paragraph:
            cleaned = re.sub(r"\s+", " ", paragraph).strip()
            if len(cleaned) > 260:
                return cleaned[:257].rstrip() + "..."
            return cleaned
    return ""


def parse_index(index_text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    current_section = ""

    for raw_line in index_text.splitlines():
        line = raw_line.rstrip()
        section_match = re.match(r"^##\s+(.*)$", line)
        if section_match:
            current_section = section_match.group(1).strip().lower()
            continue

        link_match = re.match(r"^- \[([^\]]+)\]\(([^)]+)\)(?:\s+—\s+(.*))?$", line)
        if link_match:
            items.append(
                {
                    "section": current_section,
                    "title": link_match.group(1).strip(),
                    "path": link_match.group(2).strip(),
                    "description": (link_match.group(3) or "").strip(),
                }
            )
            continue

        wikilink_match = re.match(r"^- \[\[([^\]]+)\]\](?:\s+—\s+(.*))?$", line)
        if wikilink_match:
            title = wikilink_match.group(1).strip()
            section_slug = current_section.rstrip("s")
            path = f"{current_section}/{title}.md" if current_section in {"entities", "concepts"} else f"{section_slug}/{title}.md"
            if current_section == "overview":
                path = "overview.md"
            items.append(
                {
                    "section": current_section,
                    "title": title,
                    "path": path,
                    "description": (wikilink_match.group(2) or "").strip(),
                }
            )

    return items


def section_type(section: str) -> str:
    if section.startswith("source"):
        return "source"
    if section.startswith("entit"):
        return "entity"
    if section.startswith("concept"):
        return "concept"
    if section.startswith("synthe"):
        return "synthesis"
    if section.startswith("overview"):
        return "synthesis"
    return "unknown"


def resolve_path(entry: dict[str, str]) -> Path | None:
    rel = entry["path"]
    if rel.startswith("wiki/"):
        rel = rel.removeprefix("wiki/")
    candidate = WIKI_DIR / rel
    return candidate if candidate.exists() else None


def choose_lane(text: str, type_name: str) -> str:
    blob = normalize_key(text)

    if type_name == "source":
        if any(normalize_key(word) in blob for word in PLAN_KEYWORDS):
            return "plan"
        if any(normalize_key(word) in blob for word in IMPLEMENT_KEYWORDS):
            return "implement"
        if any(normalize_key(word) in blob for word in LEARN_KEYWORDS):
            return "learn"
        return "plan"

    if type_name == "entity":
        if any(normalize_key(word) in blob for word in ENTITY_IMPLEMENT_KEYWORDS):
            return "implement"
        if any(normalize_key(word) in blob for word in PLAN_KEYWORDS):
            return "plan"
        return "learn"

    if type_name == "concept":
        if any(normalize_key(word) in blob for word in PLAN_KEYWORDS):
            return "plan"
        if any(normalize_key(word) in blob for word in IMPLEMENT_KEYWORDS):
            return "implement"
        return "learn"

    if type_name == "synthesis":
        return "plan"

    return "learn"


def score_page(page: dict[str, object]) -> int:
    text = f"{page['title']} {page.get('summary', '')} {' '.join(page.get('tags', []))}"
    blob = normalize_key(text)
    score = 0

    if page["type"] == "source":
        score += 100
    elif page["type"] == "concept":
        score += 40
    elif page["type"] == "entity":
        score += 30
    else:
        score += 20

    if any(normalize_key(word) in blob for word in PLAN_KEYWORDS):
        score += 80
    if any(normalize_key(word) in blob for word in IMPLEMENT_KEYWORDS):
        score += 60
    if any(normalize_key(word) in blob for word in LEARN_KEYWORDS):
        score += 40

    score += int(page.get("inbound_count", 0)) * 5
    score += int(page.get("related_count", 0)) * 2

    try:
        updated = datetime.fromisoformat(str(page.get("updated", "")).replace("Z", "+00:00"))
        age_days = max((datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).days, 0)
        score += max(0, 45 - min(age_days, 45))
    except Exception:
        pass

    return score


def update_from_frontmatter(page: dict[str, object], frontmatter: dict[str, object]) -> None:
    if "title" in frontmatter and frontmatter["title"]:
        page["title"] = str(frontmatter["title"])
    if "tags" in frontmatter and isinstance(frontmatter["tags"], list):
        page["tags"] = [str(tag) for tag in frontmatter["tags"]]
    if "sources" in frontmatter and isinstance(frontmatter["sources"], list):
        page["sources"] = [str(src) for src in frontmatter["sources"]]
    if "last_updated" in frontmatter and frontmatter["last_updated"]:
        page["updated"] = str(frontmatter["last_updated"])
    elif "date" in frontmatter and frontmatter["date"]:
        page["updated"] = str(frontmatter["date"])
    if "source_file" in frontmatter and frontmatter["source_file"]:
        page["source_file"] = str(frontmatter["source_file"])


def build_data() -> dict[str, object]:
    index_text = read_text(WIKI_DIR / "index.md")
    index_items = parse_index(index_text)

    pages: list[dict[str, object]] = []
    normalized_map: dict[str, dict[str, object]] = {}

    for item in index_items:
        abs_path = resolve_path(item)
        content = read_text(abs_path) if abs_path else ""
        frontmatter = parse_frontmatter(content)
        page = {
            "section": item["section"],
            "type": section_type(item["section"]),
            "title": item["title"],
            "path": item["path"],
            "repo_path": f"wiki/{item['path'].removeprefix('wiki/')}",
            "relative_path": item["path"].removeprefix("wiki/"),
            "description": item["description"],
            "summary": extract_summary(content) or item["description"],
            "tags": [],
            "sources": [],
            "updated": "",
            "source_file": "",
            "lane": "",
            "related": [],
            "related_count": 0,
            "inbound_count": 0,
            "broken_link_count": 0,
            "summary_present": bool(extract_summary(content)),
            "exists": abs_path is not None,
        }
        update_from_frontmatter(page, frontmatter)
        if not page["updated"] and abs_path:
            page["updated"] = datetime.fromtimestamp(abs_path.stat().st_mtime, tz=timezone.utc).date().isoformat()
        if not page["summary"]:
            page["summary"] = "No summary captured in the wiki index yet."
        page["lane"] = choose_lane(f"{page['title']} {page['summary']} {' '.join(page['tags'])}", page["type"])

        pages.append(page)
        normalized_map[normalize_key(str(page["title"]))] = page
        normalized_map[normalize_key(page["relative_path"].removesuffix(".md"))] = page

    resolved_links = 0
    broken_links = 0
    inbound_counts: Counter[str] = Counter()

    for page in pages:
        abs_path = WIKI_DIR / str(page["relative_path"])
        content = read_text(abs_path)
        links = extract_wikilinks(content)
        seen_related: set[str] = set()

        for link in links:
            target = normalized_map.get(normalize_key(link))
            if target and target["relative_path"] != page["relative_path"]:
                target_key = str(target["relative_path"])
                inbound_counts[target_key] += 1
                resolved_links += 1
                if target_key not in seen_related and len(seen_related) < 4:
                    page["related"].append(
                        {
                            "title": target["title"],
                            "path": target["repo_path"],
                            "type": target["type"],
                        }
                    )
                    seen_related.add(target_key)
            else:
                broken_links += 1

        page["related_count"] = len(page["related"])

    for page in pages:
        page["inbound_count"] = int(inbound_counts.get(str(page["relative_path"]), 0))

    for page in pages:
        page["lane_score"] = score_page(page)

    pages_by_lane = {
        lane: sorted(
            [page for page in pages if page["lane"] == lane],
            key=lambda page: (-int(page["lane_score"]), page["title"].lower()),
        )
        for lane in ("plan", "implement", "learn")
    }

    top_referenced = sorted(
        pages,
        key=lambda page: (-int(page["inbound_count"]), page["title"].lower()),
    )

    recent_pages = sorted(
        pages,
        key=lambda page: (str(page.get("updated", "")), page["title"].lower()),
        reverse=True,
    )

    summary_pages = [page for page in pages if page.get("summary_present")]

    stats = {
        "pages": len(pages),
        "sources": sum(1 for page in pages if page["type"] == "source"),
        "entities": sum(1 for page in pages if page["type"] == "entity"),
        "concepts": sum(1 for page in pages if page["type"] == "concept"),
        "syntheses": sum(1 for page in pages if page["type"] == "synthesis"),
        "summary_coverage": round((len(summary_pages) / max(len(pages), 1)) * 100),
        "resolved_links": resolved_links,
        "broken_links": broken_links,
        "orphan_pages": len([page for page in pages if page["inbound_count"] == 0 and page["relative_path"] != "overview.md"]),
    }

    lane_counts = {lane: len(pages_by_lane[lane]) for lane in ("plan", "implement", "learn")}
    type_counts = {
        "source": stats["sources"],
        "entity": stats["entities"],
        "concept": stats["concepts"],
        "synthesis": stats["syntheses"],
    }
    freshness_counts = {
        "new": 0,
        "recent": 0,
        "mid": 0,
        "stale": 0,
    }
    for page in pages:
        try:
            updated = datetime.fromisoformat(str(page.get("updated", "")).replace("Z", "+00:00"))
            age_days = max((datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).days, 0)
        except Exception:
            age_days = 999
        if age_days <= 7:
            freshness_counts["new"] += 1
        elif age_days <= 30:
            freshness_counts["recent"] += 1
        elif age_days <= 90:
            freshness_counts["mid"] += 1
        else:
            freshness_counts["stale"] += 1

    today_focus = []
    for lane in ("plan", "implement", "learn"):
        top_page = pages_by_lane[lane][0] if pages_by_lane[lane] else None
        if top_page:
            today_focus.append(
                {
                    "lane": lane,
                    "title": top_page["title"],
                    "summary": top_page["summary"],
                    "path": top_page["repo_path"],
                }
            )

    work_queue = [
        {
            "kind": "Compliance",
            "title": "Review the most current compliance source pages",
            "detail": "Keep ad copy, truck wraps, and offers within Illinois rules and contractor-lane boundaries.",
        },
        {
            "kind": "Marketing",
            "title": "Advance the next priority source pages",
            "detail": "Use the roadmap, storm, and GBP pages to decide what to publish or improve next.",
        },
        {
            "kind": "Operations",
            "title": "Fix broken links and orphan pages",
            "detail": "The wiki should stay internally linked so the dashboard works as a system, not a pile of files.",
        },
        {
            "kind": "Learning",
            "title": "Keep the trade-learning stack current",
            "detail": "Use the glossary, 101 pages, and SOPs to build real field fluency.",
        },
    ]

    quick_links = [
        {
            "label": "Wiki Index",
            "path": "wiki/index.md",
        },
        {
            "label": "Overview",
            "path": "wiki/overview.md",
        },
        {
            "label": "Graph",
            "path": "graph/graph.html",
        },
    ]

    data = {
        "stats": stats,
        "pages": pages,
        "lane_pages": pages_by_lane,
        "top_referenced": top_referenced[:8],
        "recent_pages": recent_pages[:8],
        "quick_links": quick_links,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(SOURCE_ROOT),
        "base_path": BASE_PATH,
        "lane_counts": lane_counts,
        "type_counts": type_counts,
        "freshness_counts": freshness_counts,
        "today_focus": today_focus,
        "work_queue": work_queue,
    }

    return data


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Roofing Wiki Dashboard</title>
  <style>
    :root {
      --bg: #071017;
      --bg-soft: #0d1720;
      --panel: rgba(12, 19, 27, 0.86);
      --panel-strong: #111b25;
      --panel-alt: #0e1822;
      --line: rgba(255, 255, 255, 0.08);
      --line-strong: rgba(255, 255, 255, 0.14);
      --text: #eef4f8;
      --muted: #9db0c2;
      --muted-2: #74879a;
      --accent: #d4ad4e;
      --accent-2: #5bc8b8;
      --accent-3: #86a7ff;
      --success: #5dd39e;
      --warning: #f2b94d;
      --danger: #ff7a73;
      --shadow: 0 20px 60px rgba(0, 0, 0, 0.34);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-md: 14px;
      --radius-sm: 10px;
    }

    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(circle at 20% 0%, rgba(212, 173, 78, 0.15), transparent 35%),
        radial-gradient(circle at 85% 10%, rgba(91, 200, 184, 0.12), transparent 28%),
        linear-gradient(180deg, #061019 0%, #09121a 55%, #050b10 100%);
      font-family: "Avenir Next", "Segoe UI", "Trebuchet MS", sans-serif;
      letter-spacing: 0.01em;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size: 40px 40px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.45), transparent 70%);
      opacity: 0.55;
    }

    a { color: inherit; text-decoration: none; }
    .app {
      position: relative;
      max-width: 1640px;
      margin: 0 auto;
      padding: 28px 20px 36px;
    }

    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(300px, 0.9fr);
      gap: 18px;
      align-items: stretch;
      margin-bottom: 18px;
    }

    .brand, .metrics, .bar, .panel, .card, .small-card {
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
    }

    .brand {
      border-radius: var(--radius-xl);
      padding: 26px 28px;
      position: relative;
      overflow: hidden;
    }

    .brand::after {
      content: "";
      position: absolute;
      inset: auto -25% -50% auto;
      width: 320px;
      height: 320px;
      background: radial-gradient(circle, rgba(212, 173, 78, 0.2), transparent 60%);
      pointer-events: none;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      margin-bottom: 18px;
    }

    .hero h1 {
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      font-size: clamp(2.6rem, 4vw, 4.4rem);
      line-height: 0.96;
      letter-spacing: -0.04em;
    }

    .hero p {
      max-width: 72ch;
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 1.02rem;
      line-height: 1.62;
    }

    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 22px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 11px 14px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      font-size: 0.92rem;
      transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
    }

    .pill:hover {
      transform: translateY(-1px);
      border-color: var(--line-strong);
      background: rgba(255,255,255,0.07);
    }

    .metrics {
      border-radius: var(--radius-xl);
      padding: 18px;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .metric {
      padding: 16px;
      border-radius: var(--radius-lg);
      background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
      border: 1px solid rgba(255,255,255,0.06);
      min-height: 104px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }

    .metric .label {
      color: var(--muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.18em;
    }

    .metric .value {
      margin-top: 8px;
      font-size: clamp(1.8rem, 2.3vw, 2.5rem);
      font-weight: 700;
      letter-spacing: -0.05em;
    }

    .metric .note {
      color: var(--muted-2);
      font-size: 0.9rem;
      line-height: 1.4;
      margin-top: 8px;
    }

    .bar {
      border-radius: var(--radius-xl);
      padding: 14px;
      margin-bottom: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
    }

    .filters {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }

    .search {
      flex: 1 1 280px;
      min-width: 260px;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(4, 10, 14, 0.55);
    }

    .search svg { flex: none; opacity: 0.75; }
    .search input {
      flex: 1;
      border: 0;
      outline: none;
      color: var(--text);
      background: transparent;
      font: inherit;
    }
    .search input::placeholder { color: var(--muted-2); }

    .chip {
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
      color: var(--muted);
      border-radius: 999px;
      padding: 10px 13px;
      font: inherit;
      cursor: pointer;
      transition: transform 140ms ease, border-color 140ms ease, background 140ms ease, color 140ms ease;
    }
    .chip:hover { transform: translateY(-1px); border-color: var(--line-strong); color: var(--text); }
    .chip[aria-pressed="true"] {
      background: linear-gradient(135deg, rgba(212,173,78,0.18), rgba(91,200,184,0.12));
      color: var(--text);
      border-color: rgba(212,173,78,0.4);
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 2.1fr) minmax(320px, 0.9fr);
      gap: 16px;
      align-items: start;
    }

    .lanes {
      display: grid;
      gap: 16px;
    }

    .lane {
      border-radius: var(--radius-xl);
      padding: 20px;
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      overflow: hidden;
      position: relative;
    }

    .lane::before {
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, rgba(212,173,78,0.85), rgba(91,200,184,0.85), rgba(134,167,255,0.85));
      opacity: 0.7;
    }

    .lane-header {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      align-items: end;
      justify-content: space-between;
      margin-bottom: 16px;
    }

    .lane-title {
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      font-size: 1.8rem;
      line-height: 1.05;
      letter-spacing: -0.04em;
    }

    .lane-copy {
      margin: 8px 0 0;
      color: var(--muted);
      max-width: 68ch;
      line-height: 1.55;
      font-size: 0.96rem;
    }

    .lane-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      color: var(--muted);
      border: 1px solid var(--line);
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      white-space: nowrap;
    }

    .cards {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .card {
      border-radius: var(--radius-lg);
      padding: 16px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02)),
        var(--panel-alt);
      border: 1px solid rgba(255,255,255,0.07);
      display: flex;
      flex-direction: column;
      min-height: 220px;
      transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
    }

    .card:hover {
      transform: translateY(-2px);
      border-color: rgba(212, 173, 78, 0.3);
    }

    .card.hidden {
      display: none;
    }

    .card-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: start;
      margin-bottom: 12px;
    }

    .badges {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 9px;
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.08);
      color: var(--muted);
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.16em;
    }

    .badge.source { color: var(--success); }
    .badge.concept { color: var(--accent); }
    .badge.entity { color: var(--accent-2); }
    .badge.synthesis { color: var(--accent-3); }
    .badge.plan { color: var(--warning); }
    .badge.implement { color: var(--accent-2); }
    .badge.learn { color: var(--accent-3); }

    .card h3 {
      margin: 0;
      font-size: 1.04rem;
      line-height: 1.34;
      letter-spacing: -0.02em;
    }

    .card p {
      color: var(--muted);
      line-height: 1.58;
      font-size: 0.94rem;
      margin: 10px 0 0;
      flex: 1;
    }

    .card-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      margin-top: 14px;
      color: var(--muted-2);
      font-size: 0.82rem;
    }

    .card-links {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }

    .link {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--line);
      color: var(--text);
      font-size: 0.83rem;
    }

    .link:hover { border-color: var(--line-strong); }

    .side {
      display: grid;
      gap: 16px;
      position: sticky;
      top: 18px;
    }

    .panel {
      border-radius: var(--radius-xl);
      padding: 18px;
      overflow: hidden;
    }

    .panel h2 {
      margin: 0;
      font-size: 1.2rem;
      letter-spacing: -0.03em;
    }

    .panel .sub {
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.55;
      font-size: 0.93rem;
    }

    .stack {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }

    .stack.tight {
      gap: 8px;
    }

    .small-card {
      border-radius: var(--radius-lg);
      padding: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
    }

    .small-card strong {
      display: block;
      font-size: 0.96rem;
      margin-bottom: 4px;
    }

    .small-card span {
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.45;
    }

    .small-card .meta {
      margin-top: 10px;
      color: var(--muted-2);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    .priority-card {
      border-radius: var(--radius-lg);
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
      padding: 14px;
      display: grid;
      gap: 8px;
    }

    .priority-card .head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .priority-card .lane-tag {
      display: inline-flex;
      align-items: center;
      padding: 6px 9px;
      border-radius: 999px;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }

    .priority-card strong {
      font-size: 0.98rem;
      line-height: 1.35;
    }

    .priority-card span {
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.45;
    }

    .priority-card .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 4px;
    }

    .plan-summary {
      margin-top: 12px;
      color: var(--muted-2);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    .plan-form {
      display: grid;
      gap: 10px;
      margin-top: 14px;
      padding: 14px;
      border-radius: var(--radius-lg);
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.02);
    }

    .plan-inputs {
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(0, 0.8fr) minmax(0, 1fr);
      gap: 10px;
    }

    .plan-form input,
    .plan-form select,
    .task-note,
    .task-title {
      border-radius: var(--radius-md);
      border: 1px solid var(--line);
      background: rgba(4, 10, 14, 0.58);
      color: var(--text);
      font: inherit;
      outline: none;
    }

    .plan-form input,
    .plan-form select {
      padding: 11px 12px;
      min-height: 44px;
    }

    .plan-form input::placeholder,
    .task-note::placeholder {
      color: var(--muted-2);
    }

    .plan-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .task-list {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }

    .task-item {
      border-radius: var(--radius-lg);
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
      padding: 12px;
      display: grid;
      gap: 10px;
    }

    .task-item.done {
      opacity: 0.7;
    }

    .task-top {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) 168px;
      gap: 10px;
      align-items: center;
    }

    .task-check {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      user-select: none;
    }

    .task-check input {
      width: 18px;
      height: 18px;
      accent-color: var(--accent-2);
    }

    .task-title {
      width: 100%;
      padding: 11px 12px;
      min-width: 0;
    }

    .task-lane {
      width: 100%;
    }

    .task-note {
      width: 100%;
      min-height: 76px;
      resize: vertical;
      padding: 11px 12px;
      line-height: 1.45;
    }

    .task-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .task-meta {
      color: var(--muted-2);
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    .empty-tasks {
      margin-top: 14px;
      border-radius: var(--radius-lg);
      border: 1px dashed var(--line);
      padding: 14px;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .note-area {
      width: 100%;
      min-height: 124px;
      resize: vertical;
      border-radius: var(--radius-lg);
      border: 1px solid var(--line);
      background: rgba(4, 10, 14, 0.55);
      color: var(--text);
      padding: 14px;
      font: inherit;
      line-height: 1.5;
      outline: none;
    }

    .note-area::placeholder {
      color: var(--muted-2);
    }

    .note-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }

    .chart-grid {
      margin-top: 16px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }

    .chart-panel {
      border-radius: var(--radius-xl);
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 18px;
      overflow: hidden;
    }

    .chart-panel h2 {
      margin: 0;
      font-size: 1.1rem;
      letter-spacing: -0.02em;
    }

    .chart-panel .sub {
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.5;
      font-size: 0.92rem;
    }

    .bars {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }

    .bar-row {
      display: grid;
      gap: 6px;
    }

    .bar-row .top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 0.86rem;
      color: var(--muted);
    }

    .bar-track {
      height: 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      overflow: hidden;
      border: 1px solid rgba(255,255,255,0.06);
    }

    .bar-fill {
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, rgba(212,173,78,0.92), rgba(91,200,184,0.92));
    }

    .chart-footer {
      margin-top: 12px;
      color: var(--muted-2);
      font-size: 0.8rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .reference-grid {
      margin-top: 16px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }

    .ref-group {
      border-radius: var(--radius-xl);
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 18px;
    }

    .ref-group h2 {
      margin: 0;
      font-size: 1.1rem;
      letter-spacing: -0.02em;
    }

    .ref-list {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }

    .ref-item {
      display: grid;
      gap: 4px;
      padding: 12px 13px;
      border-radius: var(--radius-md);
      border: 1px solid rgba(255,255,255,0.06);
      background: rgba(255,255,255,0.03);
      transition: border-color 140ms ease, transform 140ms ease;
    }

    .ref-item:hover {
      transform: translateY(-1px);
      border-color: rgba(212,173,78,0.28);
    }

    .ref-item .title {
      font-weight: 650;
      line-height: 1.35;
    }

    .ref-item .meta {
      color: var(--muted-2);
      font-size: 0.8rem;
      line-height: 1.4;
    }

    .footer-note {
      margin-top: 16px;
      color: var(--muted-2);
      font-size: 0.82rem;
      text-align: right;
    }

    .empty {
      border-radius: var(--radius-xl);
      border: 1px dashed var(--line-strong);
      padding: 20px;
      color: var(--muted);
      text-align: center;
      display: none;
    }
    .empty.visible { display: block; }

    @media (max-width: 1180px) {
      .hero, .layout, .reference-grid { grid-template-columns: 1fr; }
      .side { position: static; }
      .cards { grid-template-columns: 1fr; }
      .chart-grid { grid-template-columns: 1fr; }
    }

    @media (max-width: 720px) {
      .app { padding: 16px 12px 28px; }
      .brand, .metrics, .bar, .lane, .panel, .ref-group { border-radius: 22px; }
      .metric { min-height: 88px; }
      .search { min-width: 100%; }
      .lane-header { align-items: flex-start; }
      .reference-grid { margin-top: 12px; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="hero">
      <section class="brand">
        <div class="eyebrow">Local Ops Dashboard · Roofing Wiki</div>
        <h1>Plan the work, run the work, learn the trade.</h1>
        <p>
          This is the command center for the roofing and exterior wiki: strategic planning,
          execution systems, and trade education in one place. The layout is tuned for a
          new roofing company that needs to make faster marketing decisions, execute cleanly,
          and learn the craft without losing the thread.
        </p>
        <div class="hero-actions">
          <a class="pill" href="___BASE_PATH___wiki/index.md">Open wiki index</a>
          <a class="pill" href="___BASE_PATH___wiki/overview.md">Read overview</a>
          <a class="pill" href="___BASE_PATH___graph/graph.html">Open graph</a>
        </div>
      </section>
      <aside class="metrics" id="metrics"></aside>
    </header>

    <section class="bar">
      <div class="search" aria-label="Search docs">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M10.5 18a7.5 7.5 0 1 1 5.8-12.2A7.5 7.5 0 0 1 10.5 18Z" stroke="currentColor" stroke-width="1.7"/>
          <path d="M16.2 16.2 21 21" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
        </svg>
        <input id="search" type="search" placeholder="Search titles, summaries, tags, and related pages..." />
      </div>
      <div class="filters" role="tablist" aria-label="Dashboard lanes">
        <button class="chip" data-lane="all" aria-pressed="true">All</button>
        <button class="chip" data-lane="plan" aria-pressed="false">Plan</button>
        <button class="chip" data-lane="implement" aria-pressed="false">Implement</button>
        <button class="chip" data-lane="learn" aria-pressed="false">Learn</button>
      </div>
    </section>

    <section class="layout">
      <div class="lanes" id="lanes"></div>
      <aside class="side">
        <section class="panel">
          <h2>Today</h2>
          <p class="sub">The three highest-priority actions for the three lanes, plus the operational tasks that keep the wiki usable.</p>
          <div class="stack tight" id="today-focus"></div>
          <div class="stack" id="queue"></div>
        </section>

        <section class="panel">
          <h2>Daily Plan</h2>
          <p class="sub">Create, reorder, and mark off the tasks you actually want to do today. This stays local to your browser.</p>
          <div class="plan-summary" id="plan-summary"></div>
          <div class="plan-form">
            <div class="plan-inputs">
              <input id="task-title" type="text" placeholder="Add a task title..." />
              <select id="task-lane" aria-label="Task lane">
                <option value="plan">Plan</option>
                <option value="implement">Implement</option>
                <option value="learn">Learn</option>
              </select>
              <input id="task-note" type="text" placeholder="Optional note or context..." />
            </div>
            <div class="plan-actions">
              <button class="chip" id="add-task" type="button" aria-pressed="false">Add task</button>
              <button class="chip" id="seed-plan" type="button" aria-pressed="false">Seed from today</button>
            </div>
          </div>
          <div class="task-list" id="daily-plan"></div>
        </section>

        <section class="panel">
          <h2>Pinned</h2>
          <p class="sub">Pages you want to keep at hand. Pin directly from any card and the list persists in this browser.</p>
          <div class="stack" id="pinned"></div>
        </section>

        <section class="panel">
          <h2>Wiki Health</h2>
          <p class="sub">How complete the wiki is as a working system rather than a pile of notes.</p>
          <div class="stack" id="health"></div>
        </section>

        <section class="panel">
          <h2>Notes</h2>
          <p class="sub">A persistent scratchpad for what you need to do next. Stored locally in this browser only.</p>
          <textarea id="notes" class="note-area" placeholder="Write notes, reminders, or a short plan here..."></textarea>
          <div class="note-actions">
            <button class="chip" id="save-note" type="button" aria-pressed="false">Save note</button>
            <button class="chip" id="clear-note" type="button" aria-pressed="false">Clear note</button>
          </div>
        </section>

        <section class="panel">
          <h2>Export</h2>
          <p class="sub">Download wiki-ready markdown for pinned pages, your daily plan, your notes, or a combined synthesis bundle. Use the helper script to write the export directly into the wiki folder.</p>
          <div class="note-actions">
            <button class="chip" id="export-pins" type="button" aria-pressed="false">Export pins</button>
            <button class="chip" id="export-plan" type="button" aria-pressed="false">Export plan</button>
            <button class="chip" id="export-notes" type="button" aria-pressed="false">Export notes</button>
            <button class="chip" id="export-bundle" type="button" aria-pressed="false">Export bundle</button>
            <button class="chip" id="save-plan" type="button" aria-pressed="false">Save plan to wiki</button>
            <button class="chip" id="copy-plan" type="button" aria-pressed="false">Copy plan</button>
            <button class="chip" id="copy-bundle" type="button" aria-pressed="false">Copy bundle</button>
          </div>
          <p class="sub" style="margin-top:10px">Save exports as `wiki/syntheses/dashboard-*.md` to sync them back into the wiki. The dashboard can try to write the daily plan directly into the wiki, and the companion script remains the fallback.</p>
        </section>

        <section class="panel">
          <h2>Quick Links</h2>
          <p class="sub">Fast access to the index, the living overview, and the graph if it exists.</p>
          <div class="stack" id="quicklinks"></div>
        </section>
      </aside>
    </section>

    <section class="chart-grid">
      <article class="chart-panel">
        <h2>Corpus by Lane</h2>
        <p class="sub">How the wiki content is distributed across planning, implementation, and learning.</p>
        <div class="bars" id="lane-chart"></div>
        <div class="chart-footer">Balanced cockpit view</div>
      </article>
      <article class="chart-panel">
        <h2>Content Types</h2>
        <p class="sub">What the repo currently holds: sources, entities, concepts, and syntheses.</p>
        <div class="bars" id="type-chart"></div>
        <div class="chart-footer">Corpus composition</div>
      </article>
      <article class="chart-panel">
        <h2>Freshness</h2>
        <p class="sub">How recently the wiki pages were updated, which helps spot stale areas fast.</p>
        <div class="bars" id="freshness-chart"></div>
        <div class="chart-footer">Maintenance signal</div>
      </article>
    </section>

    <section class="reference-grid">
      <article class="ref-group">
        <h2>Recently Updated</h2>
        <div class="ref-list" id="recent"></div>
      </article>
      <article class="ref-group">
        <h2>Most Referenced</h2>
        <div class="ref-list" id="referenced"></div>
      </article>
      <article class="ref-group">
        <h2>Browse Surface</h2>
        <div class="ref-list" id="surface"></div>
      </article>
    </section>

    <div class="empty" id="empty">No documents matched the current filter.</div>
    <div class="footer-note">Generated locally from the wiki on <span id="generated-at"></span>.</div>
  </div>

  <script id="dashboard-data" type="application/json">___DATA___</script>
  <script>
    const data = JSON.parse(document.getElementById('dashboard-data').textContent);
    const state = { lane: 'all', query: '', pins: new Set(), note: '', planTasks: [] };
    const basePath = data.base_path || '';
    const storageKey = 'roofing-wiki-dashboard-state-v2';

    const laneMeta = {
      plan: {
        title: 'Plan',
        badge: 'Strategy, compliance, market focus, and decisions that set direction.',
      },
      implement: {
        title: 'Implement',
        badge: 'SOPs, workflows, checklists, tracking systems, and production discipline.',
      },
      learn: {
        title: 'Learn',
        badge: 'Trade fundamentals, reference pages, and technical knowledge for the field.',
      },
    };

    const icons = {
      source: 'Source',
      concept: 'Concept',
      entity: 'Entity',
      synthesis: 'Synthesis',
      plan: 'Plan',
      implement: 'Implement',
      learn: 'Learn',
    };

    const metricsEl = document.getElementById('metrics');
    const lanesEl = document.getElementById('lanes');
    const healthEl = document.getElementById('health');
    const quickLinksEl = document.getElementById('quicklinks');
    const pinnedEl = document.getElementById('pinned');
    const planSummaryEl = document.getElementById('plan-summary');
    const dailyPlanEl = document.getElementById('daily-plan');
    const taskTitleEl = document.getElementById('task-title');
    const taskLaneEl = document.getElementById('task-lane');
    const taskNoteEl = document.getElementById('task-note');
    const addTaskEl = document.getElementById('add-task');
    const seedPlanEl = document.getElementById('seed-plan');
    const notesEl = document.getElementById('notes');
    const saveNoteEl = document.getElementById('save-note');
    const clearNoteEl = document.getElementById('clear-note');
    const exportPinsEl = document.getElementById('export-pins');
    const exportPlanEl = document.getElementById('export-plan');
    const exportNotesEl = document.getElementById('export-notes');
    const exportBundleEl = document.getElementById('export-bundle');
    const savePlanEl = document.getElementById('save-plan');
    const copyPlanEl = document.getElementById('copy-plan');
    const copyBundleEl = document.getElementById('copy-bundle');
    const todayFocusEl = document.getElementById('today-focus');
    const queueEl = document.getElementById('queue');
    const laneChartEl = document.getElementById('lane-chart');
    const typeChartEl = document.getElementById('type-chart');
    const freshnessChartEl = document.getElementById('freshness-chart');
    const recentEl = document.getElementById('recent');
    const referencedEl = document.getElementById('referenced');
    const surfaceEl = document.getElementById('surface');
    const emptyEl = document.getElementById('empty');
    const searchEl = document.getElementById('search');
    const generatedAtEl = document.getElementById('generated-at');

    generatedAtEl.textContent = new Date(data.generated_at).toLocaleString();

    function escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
    }

    function makeFileLink(path, label, className = 'link') {
      return `<a class="${className}" href="${escapeHtml(basePath + path)}">${escapeHtml(label)}</a>`;
    }

    function loadState() {
      try {
        const raw = localStorage.getItem(storageKey);
        const legacy = raw ? raw : localStorage.getItem('roofing-wiki-dashboard-state-v1');
        if (!legacy) return;
        const parsed = JSON.parse(legacy);
        if (Array.isArray(parsed.pins)) {
          state.pins = new Set(parsed.pins);
        }
        if (typeof parsed.note === 'string') {
          state.note = parsed.note;
        }
        if (Array.isArray(parsed.planTasks)) {
          state.planTasks = parsed.planTasks
            .filter((task) => task && typeof task === 'object')
            .map((task) => ({
              id: String(task.id || task.title || makeTaskId()),
              title: String(task.title || '').trim(),
              lane: ['plan', 'implement', 'learn'].includes(task.lane) ? task.lane : 'plan',
              note: String(task.note || ''),
              done: Boolean(task.done),
            }))
            .filter((task) => task.title);
        }
      } catch (error) {
        console.warn('Could not load dashboard state', error);
      }
    }

    function saveState() {
      try {
        localStorage.setItem(storageKey, JSON.stringify({
          pins: Array.from(state.pins),
          note: state.note,
          planTasks: state.planTasks,
        }));
      } catch (error) {
        console.warn('Could not save dashboard state', error);
      }
    }

    function makeTaskId() {
      if (window.crypto && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
      }
      return `task-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    function normalizeTask(task) {
      return {
        id: String(task.id || makeTaskId()),
        title: String(task.title || '').trim(),
        lane: ['plan', 'implement', 'learn'].includes(task.lane) ? task.lane : 'plan',
        note: String(task.note || ''),
        done: Boolean(task.done),
      };
    }

    function persistPlan() {
      saveState();
      renderDailyPlan();
    }

    function addTask(task) {
      const normalized = normalizeTask(task);
      if (!normalized.title) return;
      state.planTasks = [...state.planTasks, normalized];
      persistPlan();
    }

    function seedTasksFromToday() {
      const existing = new Set(state.planTasks.map((task) => `${task.title}::${task.lane}`));
      const additions = data.today_focus.map((focus) => ({
        id: makeTaskId(),
        title: focus.title,
        lane: focus.lane,
        note: focus.summary,
        done: false,
      })).filter((task) => !existing.has(`${task.title}::${task.lane}`));
      if (!additions.length) return;
      state.planTasks = [...state.planTasks, ...additions];
      persistPlan();
    }

    function updateTask(id, patch, options = {}) {
      state.planTasks = state.planTasks.map((task) => (
        task.id === id ? { ...task, ...patch } : task
      ));
      saveState();
      if (options.render !== false) {
        renderDailyPlan();
      }
    }

    function moveTask(id, direction) {
      const index = state.planTasks.findIndex((task) => task.id === id);
      if (index < 0) return;
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= state.planTasks.length) return;
      const next = [...state.planTasks];
      [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
      state.planTasks = next;
      persistPlan();
    }

    function deleteTask(id) {
      state.planTasks = state.planTasks.filter((task) => task.id !== id);
      persistPlan();
    }

    function metricCard(label, value, note) {
      return `
        <section class="metric">
          <div>
            <div class="label">${escapeHtml(label)}</div>
            <div class="value">${escapeHtml(value)}</div>
          </div>
          <div class="note">${escapeHtml(note)}</div>
        </section>
      `;
    }

    function renderMetrics() {
      const stats = data.stats;
      metricsEl.innerHTML = [
        metricCard('Wiki pages', stats.pages, `${stats.sources} sources, ${stats.concepts} concepts, ${stats.entities} entities`),
        metricCard('Summary coverage', `${stats.summary_coverage}%`, 'How much of the wiki has a captured summary section.'),
        metricCard('Broken links', stats.broken_links, 'Links that did not resolve inside the current wiki set.'),
        metricCard('Orphan pages', stats.orphan_pages, 'Pages with no inbound reference from another wiki page.'),
      ].join('');
    }

    function renderPriorityCard(page) {
      return `
        <article class="priority-card">
          <div class="head">
            <span class="lane-tag">${escapeHtml(page.lane)}</span>
            <button class="chip" type="button" data-pin="${escapeHtml(page.repo_path)}" aria-pressed="${state.pins.has(page.repo_path) ? 'true' : 'false'}">
              ${state.pins.has(page.repo_path) ? 'Unpin' : 'Pin'}
            </button>
          </div>
          <strong>${escapeHtml(page.title)}</strong>
          <span>${escapeHtml(page.summary)}</span>
          <div class="actions">
            ${makeFileLink(page.repo_path, 'Open')}
            ${page.source_file ? makeFileLink(page.source_file, 'Source') : ''}
          </div>
        </article>
      `;
    }

    function renderQueueItem(item) {
      return `
        <article class="small-card">
          <strong>${escapeHtml(item.kind)} · ${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(item.detail)}</span>
        </article>
      `;
    }

    function renderPinnedItem(page) {
      return `
        <article class="small-card">
          <strong>${escapeHtml(page.title)}</strong>
          <span>${escapeHtml(page.summary)}</span>
          <div class="meta">${escapeHtml(page.lane)} · ${escapeHtml(page.type)}</div>
          <div class="card-links" style="margin-top:10px">
            ${makeFileLink(page.repo_path, 'Open')}
            <button class="chip" type="button" data-pin="${escapeHtml(page.repo_path)}" aria-pressed="true">Unpin</button>
          </div>
        </article>
      `;
    }

    function renderTaskItem(task, index) {
      return `
        <article class="task-item ${task.done ? 'done' : ''}" data-task-id="${escapeHtml(task.id)}">
          <div class="task-top">
            <label class="task-check">
              <input type="checkbox" data-task-done="${escapeHtml(task.id)}" ${task.done ? 'checked' : ''} />
              <span>${index + 1}</span>
            </label>
            <input
              class="task-title"
              type="text"
              data-task-field="title"
              data-task-id="${escapeHtml(task.id)}"
              value="${escapeHtml(task.title)}"
              placeholder="Task title"
            />
            <select class="task-lane" data-task-field="lane" data-task-id="${escapeHtml(task.id)}" aria-label="Task lane">
              <option value="plan" ${task.lane === 'plan' ? 'selected' : ''}>Plan</option>
              <option value="implement" ${task.lane === 'implement' ? 'selected' : ''}>Implement</option>
              <option value="learn" ${task.lane === 'learn' ? 'selected' : ''}>Learn</option>
            </select>
          </div>
          <textarea
            class="task-note"
            data-task-field="note"
            data-task-id="${escapeHtml(task.id)}"
            placeholder="Optional note or context"
          >${escapeHtml(task.note || '')}</textarea>
          <div class="task-actions">
            <button class="chip" type="button" data-task-action="up" data-task-id="${escapeHtml(task.id)}" aria-pressed="false">Up</button>
            <button class="chip" type="button" data-task-action="down" data-task-id="${escapeHtml(task.id)}" aria-pressed="false">Down</button>
            <button class="chip" type="button" data-task-action="delete" data-task-id="${escapeHtml(task.id)}" aria-pressed="false">Delete</button>
          </div>
          <div class="task-meta">${escapeHtml(task.lane)} · ${task.done ? 'done' : 'open'}</div>
        </article>
      `;
    }

    function renderDailyPlan() {
      const tasks = state.planTasks.map(normalizeTask);
      state.planTasks = tasks;

      const done = tasks.filter((task) => task.done).length;
      const active = tasks.length - done;
      planSummaryEl.textContent = `${active} active · ${done} done · ${tasks.length} total`;

      if (!tasks.length) {
        dailyPlanEl.innerHTML = '<div class="empty-tasks">No tasks yet. Add one above, or seed the plan from today\'s focus items.</div>';
        return;
      }

      dailyPlanEl.innerHTML = tasks.map(renderTaskItem).join('');
    }

    function renderBars(target, entries) {
      const max = Math.max(...entries.map((entry) => entry.value), 1);
      target.innerHTML = entries.map((entry) => `
        <div class="bar-row">
          <div class="top">
            <span>${escapeHtml(entry.label)}</span>
            <span>${escapeHtml(entry.value)}</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:${Math.max((entry.value / max) * 100, 6)}%; background:${entry.color};"></div></div>
        </div>
      `).join('');
    }

    function renderToday() {
      todayFocusEl.innerHTML = data.today_focus.map(renderPriorityCard).join('');
      queueEl.innerHTML = data.work_queue.map(renderQueueItem).join('');
    }

    function renderPinned() {
      const pagesByPath = new Map(data.pages.map((page) => [page.repo_path, page]));
      const pinnedPages = Array.from(state.pins)
        .map((path) => pagesByPath.get(path))
        .filter(Boolean);

      if (!pinnedPages.length) {
        pinnedEl.innerHTML = '<div class="small-card"><strong>No pins yet</strong><span>Pin the pages you keep reopening and they will stay here in this browser.</span></div>';
        return;
      }

      pinnedEl.innerHTML = pinnedPages.slice(0, 6).map(renderPinnedItem).join('');
    }

    function renderCharts() {
      renderBars(laneChartEl, [
        { label: 'Plan', value: data.lane_counts.plan, color: 'linear-gradient(90deg, rgba(242,185,77,0.95), rgba(212,173,78,0.92))' },
        { label: 'Implement', value: data.lane_counts.implement, color: 'linear-gradient(90deg, rgba(91,200,184,0.95), rgba(81,164,150,0.92))' },
        { label: 'Learn', value: data.lane_counts.learn, color: 'linear-gradient(90deg, rgba(134,167,255,0.95), rgba(110,140,230,0.92))' },
      ]);
      renderBars(typeChartEl, [
        { label: 'Sources', value: data.type_counts.source, color: 'linear-gradient(90deg, rgba(93,211,158,0.95), rgba(75,187,141,0.92))' },
        { label: 'Concepts', value: data.type_counts.concept, color: 'linear-gradient(90deg, rgba(242,185,77,0.95), rgba(212,173,78,0.92))' },
        { label: 'Entities', value: data.type_counts.entity, color: 'linear-gradient(90deg, rgba(91,200,184,0.95), rgba(81,164,150,0.92))' },
        { label: 'Syntheses', value: data.type_counts.synthesis, color: 'linear-gradient(90deg, rgba(134,167,255,0.95), rgba(110,140,230,0.92))' },
      ]);
      renderBars(freshnessChartEl, [
        { label: 'New', value: data.freshness_counts.new, color: 'linear-gradient(90deg, rgba(93,211,158,0.95), rgba(75,187,141,0.92))' },
        { label: 'Recent', value: data.freshness_counts.recent, color: 'linear-gradient(90deg, rgba(91,200,184,0.95), rgba(81,164,150,0.92))' },
        { label: 'Mid', value: data.freshness_counts.mid, color: 'linear-gradient(90deg, rgba(242,185,77,0.95), rgba(212,173,78,0.92))' },
        { label: 'Stale', value: data.freshness_counts.stale, color: 'linear-gradient(90deg, rgba(255,122,115,0.95), rgba(214,88,80,0.92))' },
      ]);
    }

    function matchesQuery(page) {
      const haystack = [
        page.title,
        page.summary,
        page.description,
        page.updated,
        page.type,
        page.lane,
        ...(page.tags || []),
        ...(page.related || []).map((item) => item.title),
      ].join(' ').toLowerCase();
      return haystack.includes(state.query);
    }

    function renderHealthCard(label, value, note) {
      return `
        <article class="small-card">
          <strong>${escapeHtml(label)} · ${escapeHtml(value)}</strong>
          <span>${escapeHtml(note)}</span>
        </article>
      `;
    }

    function renderQuickLink(link) {
      return `
        <article class="small-card">
          <strong>${escapeHtml(link.label)}</strong>
          <span>Open ${escapeHtml(link.path)}</span>
          <div class="card-links">
            ${makeFileLink(link.path, 'Open')}
          </div>
        </article>
      `;
    }

    function renderReferenceItem(page) {
      return `
        <a class="ref-item" href="${escapeHtml(basePath + page.repo_path)}">
          <div class="title">${escapeHtml(page.title)}</div>
          <div class="meta">${escapeHtml(page.type)} · ${escapeHtml(page.lane)} · ${page.inbound_count} inbound links · ${page.related_count} related</div>
        </a>
      `;
    }

    function renderCard(page) {
      const pinned = state.pins.has(page.repo_path);
      const links = [
        makeFileLink(page.repo_path, 'Open page'),
      ];
      if (page.source_file) {
        links.push(makeFileLink(page.source_file, 'Open source'));
      }
      if (page.related && page.related.length) {
        links.push(...page.related.map((item) => makeFileLink(item.path, item.title)));
      }

      const searchText = [
        page.title,
        page.summary,
        page.description,
        page.updated,
        page.type,
        page.lane,
        ...(page.tags || []),
        ...(page.related || []).map((item) => item.title),
      ].join(' ').toLowerCase();

      return `
        <article class="card" data-lane="${escapeHtml(page.lane)}" data-search="${escapeHtml(searchText)}">
          <div class="card-top">
            <div class="badges">
              <span class="badge ${escapeHtml(page.type)}">${escapeHtml(page.type)}</span>
              <span class="badge ${escapeHtml(page.lane)}">${escapeHtml(page.lane)}</span>
              ${page.tags && page.tags.length ? `<span class="badge">${escapeHtml(page.tags.slice(0, 2).join(' · '))}</span>` : ''}
            </div>
            <div style="display:flex; gap:8px; align-items:center;">
              <span class="badge">${escapeHtml(page.updated || 'date unknown')}</span>
              <button class="chip" type="button" data-pin="${escapeHtml(page.repo_path)}" aria-pressed="${pinned ? 'true' : 'false'}">${pinned ? 'Unpin' : 'Pin'}</button>
            </div>
          </div>
          <h3>${escapeHtml(page.title)}</h3>
          <p>${escapeHtml(page.summary)}</p>
          <div class="card-meta">
            <span>${page.inbound_count} inbound · ${page.related_count} related</span>
            <span>${page.summary_present ? 'Summary captured' : 'Summary missing'}</span>
          </div>
          <div class="card-links">${links.join('')}</div>
        </article>
      `;
    }

    function renderLanes() {
      lanesEl.innerHTML = ['plan', 'implement', 'learn'].map((lane) => {
        const pages = data.lane_pages[lane] || [];
        const visible = pages.filter((page) => matchesQuery(page));
        const meta = laneMeta[lane];
        const cards = visible.map(renderCard).join('');
        const emptyNotice = visible.length ? '' : '<div class="empty visible" style="margin-top:12px">No documents match this lane and search query.</div>';

        return `
          <section class="lane" data-lane="${lane}">
            <div class="lane-header">
              <div>
                <h2 class="lane-title">${meta.title}</h2>
                <p class="lane-copy">${meta.badge}</p>
              </div>
              <div class="lane-badge">${visible.length} shown · ${pages.length} total</div>
            </div>
            <div class="cards">${cards}</div>
            ${emptyNotice}
          </section>
        `;
      }).join('');

      const anyVisible = lanesEl.querySelectorAll('.card:not(.hidden)').length > 0;
      emptyEl.classList.toggle('visible', !anyVisible);
    }

    function renderPanels() {
      renderToday();
      renderDailyPlan();
      renderPinned();
      renderCharts();

      healthEl.innerHTML = [
        renderHealthCard('Resolved links', data.stats.resolved_links, 'Internal references that connect pages in the wiki graph.'),
        renderHealthCard('Broken links', data.stats.broken_links, 'Links that still need a matching page or slug fix.'),
        renderHealthCard('Orphan pages', data.stats.orphan_pages, 'Pages that may need more cross-links or should be merged.'),
      ].join('');

      quickLinksEl.innerHTML = data.quick_links.map(renderQuickLink).join('');
      recentEl.innerHTML = data.recent_pages.slice(0, 6).map(renderReferenceItem).join('');
      referencedEl.innerHTML = data.top_referenced.slice(0, 6).map(renderReferenceItem).join('');

      const surfacePages = [
        ...data.pages.filter((page) => page.type === 'source').slice(0, 3),
        ...data.pages.filter((page) => page.type === 'concept').slice(0, 2),
        ...data.pages.filter((page) => page.type === 'entity').slice(0, 2),
      ];
      surfaceEl.innerHTML = surfacePages.map(renderReferenceItem).join('');
    }

    function escapeMarkdown(value) {
      return String(value).replaceAll('|', '\\|').replaceAll('\n', ' ').trim();
    }

    function markdownFrontmatter(title, tags = []) {
      const date = new Date(data.generated_at).toISOString().slice(0, 10);
      const tagList = tags.length ? `[${tags.map((tag) => `"${tag}"`).join(', ')}]` : '[]';
      return [
        '---',
        `title: "${title.replaceAll('"', '\\"')}"`,
        'type: synthesis',
        `tags: ${tagList}`,
        'sources: []',
        `last_updated: ${date}`,
        '---',
        '',
      ].join('\n');
    }

    function pinnedMarkdown() {
      const pagesByPath = new Map(data.pages.map((page) => [page.repo_path, page]));
      const pinnedPages = Array.from(state.pins)
        .map((path) => pagesByPath.get(path))
        .filter(Boolean);
      const date = new Date(data.generated_at).toISOString().slice(0, 10);
      const lines = [
        markdownFrontmatter(`Dashboard Pins — ${date}`, ['dashboard', 'pins', 'synthesis']),
        `# Dashboard Pins — ${date}`,
        '',
        '## Pinned Pages',
      ];

      if (!pinnedPages.length) {
        lines.push('', '_No pages pinned yet._');
      } else {
        pinnedPages.forEach((page) => {
          lines.push(`- [[${page.title}]] — ${page.lane} / ${escapeMarkdown(page.summary)}`);
        });
      }

      return lines.join('\n');
    }

    function notesMarkdown() {
      const date = new Date(data.generated_at).toISOString().slice(0, 10);
      const noteText = notesEl.value.trim();
      const lines = [
        markdownFrontmatter(`Dashboard Notes — ${date}`, ['dashboard', 'notes', 'synthesis']),
        `# Dashboard Notes — ${date}`,
        '',
        '## Notes',
      ];

      if (noteText) {
        lines.push('', noteText);
      } else {
        lines.push('', '_No notes captured yet._');
      }

      return lines.join('\n');
    }

    function planMarkdown() {
      const date = new Date(data.generated_at).toISOString().slice(0, 10);
      const tasks = state.planTasks.map(normalizeTask).filter((task) => task.title);
      const lines = [
        markdownFrontmatter(`Dashboard Daily Plan — ${date}`, ['dashboard', 'plan', 'synthesis']),
        `# Dashboard Daily Plan — ${date}`,
        '',
        '## Tasks',
      ];

      if (!tasks.length) {
        lines.push('', '_No tasks captured yet._');
      } else {
        tasks.forEach((task, index) => {
          const status = task.done ? '[x]' : '[ ]';
          const note = task.note.trim() ? ` — ${escapeMarkdown(task.note)}` : '';
          lines.push(`${index + 1}. ${status} **${escapeMarkdown(task.title)}** (${task.lane})${note}`);
        });
      }

      lines.push('', '## Suggested Save Path', '');
      lines.push('Save this file as `wiki/syntheses/dashboard-daily-plan-' + date + '.md` to sync it back into the wiki.');
      return lines.join('\n');
    }

    function bundleMarkdown() {
      const date = new Date(data.generated_at).toISOString().slice(0, 10);
      const pagesByPath = new Map(data.pages.map((page) => [page.repo_path, page]));
      const pinnedPages = Array.from(state.pins)
        .map((path) => pagesByPath.get(path))
        .filter(Boolean);
      const noteText = notesEl.value.trim();
      const tasks = state.planTasks.map(normalizeTask).filter((task) => task.title);
      const lines = [
        markdownFrontmatter(`Dashboard Export — ${date}`, ['dashboard', 'export', 'synthesis']),
        `# Dashboard Export — ${date}`,
        '',
        '## Summary',
        `- Pinned pages: ${pinnedPages.length}`,
        `- Daily plan tasks: ${tasks.length}`,
        `- Notes captured: ${noteText ? 'yes' : 'no'}`,
        '',
        '## Daily Plan',
      ];

      if (!tasks.length) {
        lines.push('_No tasks captured yet._');
      } else {
        tasks.forEach((task, index) => {
          const status = task.done ? '[x]' : '[ ]';
          const note = task.note.trim() ? ` — ${escapeMarkdown(task.note)}` : '';
          lines.push(`${index + 1}. ${status} **${escapeMarkdown(task.title)}** (${task.lane})${note}`);
        });
      }

      lines.push('', '## Pinned Pages');

      if (!pinnedPages.length) {
        lines.push('_No pages pinned yet._');
      } else {
        pinnedPages.forEach((page) => {
          lines.push(`- [[${page.title}]] — ${page.lane} / ${escapeMarkdown(page.summary)}`);
        });
      }

      lines.push('', '## Notes');
      lines.push(noteText || '_No notes captured yet._');
      lines.push('', '## Suggested Save Path', '');
      lines.push('Save this file as `wiki/syntheses/dashboard-export-' + date + '.md` to sync it back into the wiki.');
      return lines.join('\n');
    }

    function downloadMarkdown(filename, markdown) {
      const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    }

    async function writeMarkdownWithPicker(filename, markdown) {
      if (window.showSaveFilePicker) {
        const handle = await window.showSaveFilePicker({
          suggestedName: filename,
          types: [{ description: 'Markdown', accept: { 'text/markdown': ['.md'] } }],
        });
        const writable = await handle.createWritable();
        await writable.write(markdown);
        await writable.close();
        return true;
      }
      return false;
    }

    async function copyMarkdown(markdown) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(markdown);
        return true;
      }
      const temp = document.createElement('textarea');
      temp.value = markdown;
      temp.setAttribute('readonly', 'true');
      temp.style.position = 'fixed';
      temp.style.opacity = '0';
      document.body.appendChild(temp);
      temp.select();
      const success = document.execCommand('copy');
      temp.remove();
      return success;
    }

    function applyVisibility() {
      document.querySelectorAll('.card').forEach((card) => {
        const laneMatches = state.lane === 'all' || card.dataset.lane === state.lane;
        const queryMatches = !state.query || card.dataset.search.includes(state.query);
        card.classList.toggle('hidden', !(laneMatches && queryMatches));
      });

      document.querySelectorAll('.lane').forEach((laneEl) => {
        const visible = laneEl.querySelectorAll('.card:not(.hidden)').length;
        const badge = laneEl.querySelector('.lane-badge');
        if (badge) {
          const lane = laneEl.dataset.lane;
          const total = (data.lane_pages[lane] || []).length;
          badge.textContent = `${visible} shown · ${total} total`;
        }
        const emptyNotice = laneEl.querySelector('.empty');
        if (emptyNotice) {
          emptyNotice.classList.toggle('visible', visible === 0);
        }
      });

      const anyVisible = document.querySelectorAll('.card:not(.hidden)').length > 0;
      emptyEl.classList.toggle('visible', !anyVisible);
    }

    function setLane(lane) {
      state.lane = lane;
      document.querySelectorAll('.chip[data-lane]').forEach((chip) => {
        chip.setAttribute('aria-pressed', String(chip.dataset.lane === lane));
      });
      applyVisibility();
    }

    function togglePin(path) {
      if (state.pins.has(path)) {
        state.pins.delete(path);
      } else {
        state.pins.add(path);
      }
      saveState();
      renderPinned();
      renderLanes();
      applyVisibility();
    }

    function bindNotes() {
      notesEl.value = state.note;
      saveNoteEl.addEventListener('click', () => {
        state.note = notesEl.value.trim();
        saveState();
      });
      clearNoteEl.addEventListener('click', () => {
        state.note = '';
        notesEl.value = '';
        saveState();
      });
    }

    function addTaskFromForm() {
      const title = taskTitleEl.value.trim();
      if (!title) {
        taskTitleEl.focus();
        return;
      }
      addTask({
        id: makeTaskId(),
        title,
        lane: taskLaneEl.value,
        note: taskNoteEl.value.trim(),
        done: false,
      });
      taskTitleEl.value = '';
      taskNoteEl.value = '';
      taskLaneEl.value = 'plan';
      taskTitleEl.focus();
    }

    function init() {
      loadState();
      renderMetrics();
      renderPanels();
      renderLanes();
      applyVisibility();
      bindNotes();

      searchEl.addEventListener('input', () => {
        state.query = searchEl.value.trim().toLowerCase();
        renderLanes();
        applyVisibility();
      });

      document.querySelectorAll('.chip[data-lane]').forEach((chip) => {
        chip.addEventListener('click', () => setLane(chip.dataset.lane));
      });

      document.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-pin]');
        if (!button) return;
        togglePin(button.dataset.pin);
      });

      document.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-task-action]');
        if (!button) return;
        const { taskId, taskAction } = button.dataset;
        if (taskAction === 'up') {
          moveTask(taskId, -1);
        } else if (taskAction === 'down') {
          moveTask(taskId, 1);
        } else if (taskAction === 'delete') {
          deleteTask(taskId);
        }
      });

      document.addEventListener('change', (event) => {
        const target = event.target;
        if (target.matches('input[data-task-done]')) {
          updateTask(target.dataset.taskDone, { done: target.checked });
          return;
        }
        if (target.matches('select[data-task-field]')) {
          updateTask(target.dataset.taskId, { [target.dataset.taskField]: target.value }, { render: false });
        }
      });

      document.addEventListener('input', (event) => {
        const target = event.target;
        if (target.matches('input[data-task-field], textarea[data-task-field]')) {
          updateTask(target.dataset.taskId, { [target.dataset.taskField]: target.value }, { render: false });
        }
      });

      notesEl.addEventListener('input', () => {
        state.note = notesEl.value;
        saveState();
      });

      addTaskEl.addEventListener('click', addTaskFromForm);
      seedPlanEl.addEventListener('click', () => {
        seedTasksFromToday();
        renderDailyPlan();
      });

      taskTitleEl.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          addTaskFromForm();
        }
      });

      savePlanEl.addEventListener('click', async () => {
        const date = new Date(data.generated_at).toISOString().slice(0, 10);
        const filename = `dashboard-daily-plan-${date}.md`;
        const markdown = planMarkdown();
        try {
          const saved = await writeMarkdownWithPicker(filename, markdown);
          if (!saved) downloadMarkdown(filename, markdown);
        } catch (error) {
          console.warn('Could not save plan markdown directly', error);
          downloadMarkdown(filename, markdown);
        }
      });

      exportPlanEl.addEventListener('click', () => {
        const date = new Date(data.generated_at).toISOString().slice(0, 10);
        downloadMarkdown(`dashboard-daily-plan-${date}.md`, planMarkdown());
      });

      exportPinsEl.addEventListener('click', () => {
        const date = new Date(data.generated_at).toISOString().slice(0, 10);
        downloadMarkdown(`dashboard-pins-${date}.md`, pinnedMarkdown());
      });

      exportNotesEl.addEventListener('click', () => {
        const date = new Date(data.generated_at).toISOString().slice(0, 10);
        downloadMarkdown(`dashboard-notes-${date}.md`, notesMarkdown());
      });

      exportBundleEl.addEventListener('click', () => {
        const date = new Date(data.generated_at).toISOString().slice(0, 10);
        downloadMarkdown(`dashboard-export-${date}.md`, bundleMarkdown());
      });

      copyPlanEl.addEventListener('click', async () => {
        try {
          await copyMarkdown(planMarkdown());
          copyPlanEl.textContent = 'Copied plan';
          setTimeout(() => {
            copyPlanEl.textContent = 'Copy plan';
          }, 1400);
        } catch (error) {
          console.warn('Could not copy plan markdown', error);
        }
      });

      copyBundleEl.addEventListener('click', async () => {
        try {
          await copyMarkdown(bundleMarkdown());
          copyBundleEl.textContent = 'Copied bundle';
          setTimeout(() => {
            copyBundleEl.textContent = 'Copy bundle';
          }, 1400);
        } catch (error) {
          console.warn('Could not copy bundle markdown', error);
        }
      });
    }

    init();
  </script>
</body>
</html>
"""


def write_dashboard(output: Path, data: dict[str, object]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False)
    payload = payload.replace("<", "\\u003c")
    html = HTML_TEMPLATE.replace("___BASE_PATH___", BASE_PATH).replace("___DATA___", payload)
    output.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the roofing wiki dashboard.")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE, help="Output HTML file.")
    parser.add_argument("--open", action="store_true", help="Open the dashboard after building.")
    args = parser.parse_args()

    data = build_data()
    write_dashboard(args.output, data)
    print(f"Wrote {args.output}")
    if args.open:
        webbrowser.open(args.output.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
