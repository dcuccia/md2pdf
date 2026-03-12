# CLAUDE.md — Project context for Claude Code

## What is this project?

md2pdf converts Markdown documents to styled PDFs with inline chart generation.
Three-stage pipeline: chart SVG generation → MD→HTML conversion → HTML→PDF rendering.

## Quick Reference

```bash
# Run all tests
python -m pytest tests/ -v && npx jest --verbose

# Run Python tests only
python -m pytest tests/ -v

# Run JS tests only
npx jest --verbose

# Install dependencies
pip install -r requirements.txt && pip install -r requirements-dev.txt
npm install

# Convert a document (Windows)
.\md2pdf.ps1 "path\to\doc.md"

# Convert a document (Linux/macOS)
./md2pdf.sh "path/to/doc.md"
```

## Architecture

```
document.md → md2svg.py → *.svg charts
     │                        │
     └→ lib/md2html.py → styled HTML → lib/html2pdf.js → PDF
          (+ CSS theme)    (+ Mermaid CDN)   (headless Chromium)
```

## Key Files

- `md2svg.py` — Python. Scans markdown for `@chart` YAML blocks, generates SVG files.
  Uses a dispatch table pattern (`CHART_GENERATORS` dict) for chart types.
- `lib/md2html.py` — Python. MD → HTML conversion with CSS theme injection and Mermaid support.
- `lib/html2pdf.js` — Node.js. HTML → PDF via Playwright. Starts a local HTTP server for assets.
- `md2pdf.ps1` / `md2pdf.sh` — Shell orchestrators. Must maintain feature parity.
- `themes/*.css` — PDF styling themes.
- `tests/` — pytest (Python) and Jest (JS) tests.

## Conventions to Follow

### Adding a chart type
1. Add `generate_<type>(spec)` function in `md2svg.py`
2. Register in `CHART_GENERATORS` dict
3. Add test in `tests/test_md2svg.py`
4. Add example in `docs/guide.md`

### Adding a theme
1. Create `themes/<name>.css` (copy structure from `themes/default.css`)
2. Update theme tables in `README.md` and `docs/guide.md`

### Code patterns
- Python: 4-space indent, type hints, docstrings. Follow `md2svg.py` style.
- JS: 2-space indent, JSDoc, CommonJS modules. Follow `lib/html2pdf.js` style.
- Shell scripts: thin orchestrators only — no business logic inline.
- CSS: comment header, must define all element types.

### Rules
- Never overwrite existing PDFs (auto-increment suffix)
- Keep dependency installs local (no global installs)
- Python handles text processing; Node.js handles browser rendering
- `@chart` YAML is source of truth; SVGs are derived
- Shell scripts (ps1/sh) must stay in sync — same features, same pipeline
