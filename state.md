# Roofing Wiki Dashboard - Project State

## Index
1. Project Snapshot
2. Tech Details
3. Current Status
4. Roadmap
5. Change History (With Context)
6. Risks and Open Questions
7. Operational Commands
8. Handoff Protocol (ChatGPT Web <-> Codex)
9. Next Handoff Message Template

## 1. Project Snapshot
- Project name: `roofing-wiki-dashboard`
- Purpose: generate a standalone HTML dashboard from the roofing wiki content, with local planning and export workflows.
- Core model: build-time Python script produces a single self-contained `index.html` app.
- Primary user workflow:
  - Parse wiki pages from `../Roofing company/wiki`
  - Build lane-based dashboard (`plan`, `implement`, `learn`)
  - Use browser-local notes/tasks/pins
  - Export markdown syntheses back into wiki

Short summary:
This repo is a local-first dashboard generator for organizing roofing wiki knowledge into action lanes. It emphasizes strategy planning, operations implementation, and trade learning in one interface, with markdown export back into the wiki synthesis folder.

## 2. Tech Details
- Language/runtime:
  - Python 3 for generation scripts
  - Vanilla HTML/CSS/JS for runtime dashboard UI
- Main files:
  - `build_dashboard.py` - parses wiki, computes metadata/scoring, renders `index.html`
  - `index.html` - generated output (single-file UI + embedded JSON data payload)
  - `write_export_to_wiki.py` - helper to copy exported markdown into wiki syntheses
  - `README.md` - usage instructions
- Data source assumptions:
  - `SOURCE_ROOT = ../Roofing company`
  - `WIKI_DIR = ../Roofing company/wiki`
  - Dashboard links rely on `BASE_PATH = ../Roofing company/`
- Core behaviors in `build_dashboard.py`:
  - Parses wiki index and frontmatter
  - Extracts summaries and wikilinks
  - Classifies pages into lanes using keyword heuristics
  - Scores pages based on type/keywords/links/freshness
  - Builds stats, charts, and today-focus recommendations
  - Serializes JSON payload into `index.html`
- Browser-side dashboard behaviors:
  - Search/filter cards by lane and text
  - Persist pins/notes/daily plan via `localStorage`
  - Export pins/plan/notes/bundle as markdown
  - Save plan via File System Access API when available

## 3. Current Status
- Remote:
  - `origin` -> `https://github.com/MikeB317/WikiDashboard.git`
- Branch:
  - `main`
- Latest known commits:
  - `a7f0daf` - Regenerate dashboard HTML data payload
  - `d7b76e1` - Initial dashboard commit
- Working tree status at last Codex check:
  - clean after commit/push
- Build check:
  - `python3 build_dashboard.py` succeeded

## 4. Roadmap
### Near-term (stability)
1. Make source paths configurable via CLI flags/env vars (remove hardcoded folder assumptions).
2. Add parser robustness for frontmatter and index shape edge cases.
3. Add collision detection/reporting for normalized wiki-link key matches.
4. Add basic test coverage for parsing/linking/scoring logic.

### Mid-term (maintainability)
1. Split `build_dashboard.py` into modules:
   - parsing
   - scoring
   - data assembly
   - template/render
2. Move HTML/CSS/JS template out of Python string into template/static files.
3. Add lightweight linting/format standards for Python and JS sections.

### Longer-term (product capability)
1. Add explicit broken-link reporting page/list with repair suggestions.
2. Add per-lane roadmap tracking in exports.
3. Optional: move from static output to small local web app if dynamic features expand.

## 5. Change History (With Context)
- Initial repository setup and first push:
  - Commit `d7b76e1` created baseline dashboard project.
  - Context: establish standalone dashboard generator with wiki ingestion + export helper.
- Remote migration to company GitHub account:
  - Old remote was tied to another account.
  - `origin` updated to `MikeB317/WikiDashboard`.
  - GitHub authentication updated locally and `main` pushed to new remote.
- Data payload refresh:
  - Running `python3 build_dashboard.py` regenerated `index.html` embedded dataset timestamp/content.
  - Commit `a7f0daf` captured this regeneration.

## 6. Risks and Open Questions
- Hardcoded path dependencies can break portability across machines/directories.
- Parsing logic is regex-based and may fail on markdown/frontmatter variations.
- `index.html` is generated and large; manual edits should generally be avoided.
- Open question:
  - Should `index.html` remain committed, or be fully build-artifact-only?

## 7. Operational Commands
- Rebuild dashboard:
```bash
python3 build_dashboard.py
```

- Rebuild and open locally:
```bash
python3 build_dashboard.py --open
```

- Serve static dashboard:
```bash
python3 -m http.server 4173
```

- Copy downloaded markdown export into wiki syntheses:
```bash
python3 write_export_to_wiki.py /path/to/dashboard-export-YYYY-MM-DD.md
```

- Pipe markdown into syntheses helper:
```bash
cat dashboard-export-YYYY-MM-DD.md | python3 write_export_to_wiki.py -
```

## 8. Handoff Protocol (ChatGPT Web <-> Codex)
Use this section to transfer context quickly between tools.

### Rules
1. Update this file after meaningful architecture/workflow/code changes.
2. Always include:
   - what changed
   - why it changed
   - current blockers
   - exact next step
3. Keep roadmap and risks aligned with current repo state.
4. Never paste secrets or tokens here.

### Current Handoff Notes
- Dashboard architecture is generator-first (Python -> static HTML).
- Repo has been migrated to company GitHub remote.
- Latest push includes regenerated dashboard payload.
- Immediate priority is hardening config/path handling and adding parser tests.

## 9. Next Handoff Message Template
Copy this block when handing off:

```text
Handoff Summary:
- Project: roofing-wiki-dashboard
- Branch: main
- Latest commit: <commit-hash>
- Goal right now: <short goal>

What changed:
1) <change + reason>
2) <change + reason>

Current status:
- Build/tests: <result>
- Known issues/blockers: <list>

Next exact action:
- <single concrete next step>

Files to review first:
- build_dashboard.py
- state.md
- README.md
```
