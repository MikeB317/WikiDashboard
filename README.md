# Roofing Wiki Dashboard

Standalone dashboard for the roofing and exterior wiki.

## Files

- `index.html` - self-contained dashboard UI
- `build_dashboard.py` - rebuilds the dashboard from the wiki content
- `write_export_to_wiki.py` - copies a downloaded markdown export into `wiki/syntheses/`

## Build

```bash
python3 build_dashboard.py
```

## Sync an export into the wiki

The dashboard includes a `Save plan to wiki` button that tries to write the
daily plan directly into your wiki syntheses folder when the browser allows it.

If you download an export instead, copy it into the wiki syntheses folder with:

```bash
python3 write_export_to_wiki.py /path/to/dashboard-export-YYYY-MM-DD.md
```

You can also pipe markdown in from stdin:

```bash
cat dashboard-export-YYYY-MM-DD.md | python3 write_export_to_wiki.py -
```

## Open

Open `index.html` directly in a browser, or serve the folder locally if you
prefer:

```bash
python3 -m http.server 4173
```
