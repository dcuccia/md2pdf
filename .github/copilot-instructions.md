# md2pdf — Copilot Instructions

## Project Overview

md2pdf is a Markdown → styled HTML + PDF converter with inline chart generation.
It uses a three-stage pipeline: `lib/md2svg.py` generates charts, `lib/md2html.py`
converts MD → HTML with CSS themes, and `lib/html2pdf.js` renders HTML → PDF via
Playwright headless Chromium.

## Architecture

```
document.md → md2svg.py → *.svg charts
     │                        │
     └→ lib/md2html.py → styled HTML → lib/html2pdf.js → PDF
          (+ CSS theme)    (+ Mermaid CDN)   (headless Chromium)
```

### Key Files

| File | Language | Purpose |
|------|----------|---------|
| `lib/md2svg.py` | Python | Scans markdown for `@chart` blocks, generates SVG files |
| `lib/md2html.py` | Python | Converts Markdown → styled HTML with Mermaid support |
| `lib/html2pdf.js` | Node.js | Renders HTML → PDF via Playwright headless Chromium |
| `md2pdf.ps1` | PowerShell | Windows orchestrator — calls all three stages |
| `md2pdf.sh` | Bash | Linux/macOS orchestrator — calls all three stages |
| `md2pdf.bat` | Batch | Windows wrapper for `md2pdf.ps1` |
| `themes/*.css` | CSS | PDF themes (default, academic, minimal) |

## Conventions

### Adding a New Chart Type

1. Add a `generate_<type>(spec: dict) -> str` function in `lib/md2svg.py`
2. Register it in the `CHART_GENERATORS` dispatch table
3. Add a test in `tests/test_md2svg.py`
4. Add an example in `docs/guide.md`

### Adding a New Theme

1. Create `themes/<name>.css` following the structure of `themes/default.css`
2. Must include `@page` rule, body font, headings, tables, blockquotes, lists
3. Document in the themes table in `README.md` and `docs/guide.md`

### Code Style

- **Python:** 4-space indent, type hints on public functions, docstrings on
  modules and public functions. Follow the patterns in `lib/md2svg.py`.
- **JavaScript:** 2-space indent, JSDoc on exported functions, `const`/`let`
  only (no `var`). CommonJS modules (`require`/`module.exports`).
- **Shell scripts (ps1/sh):** Must maintain feature parity — any change to
  the pipeline in one script must be reflected in the other.
- **CSS themes:** Comment header with theme name and description. Must define
  all elements: `@page`, body, h1-h2, tables, blockquotes, lists, images, hr.

### Dependencies

- **Python:** `markdown`, `pyyaml` — declared in `requirements.txt`
- **Node.js:** `playwright` — declared in `package.json`
- Do NOT add global install dependencies. Everything installs locally.
- Do NOT mix Python and Node.js responsibilities — Python handles text
  processing, Node.js handles browser-based rendering.

### Testing

- **Python tests:** `python -m pytest tests/ -v`
- **Node.js tests:** `npx jest --verbose`
- **All tests:** `npm run test:all`
- Tests live in `tests/` — Python tests use pytest, JS tests use Jest.
- Test files mirror source: `test_md2svg.py`, `test_md2html.py`, `test_html2pdf.test.js`

### Important Rules

- Never overwrite existing PDFs — use auto-increment suffix (`_1`, `_2`, ...)
- Maintain idempotent dependency installation in shell scripts
- The `@chart` YAML block is the source of truth; SVGs are derived artifacts
- Keep the shell scripts thin — orchestration only, no business logic
- SVG chart files referenced in README live in `docs/images/`
