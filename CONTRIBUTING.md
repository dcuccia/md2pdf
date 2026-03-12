# Contributing to md2pdf

Thanks for your interest in contributing! This guide covers the common ways
to extend the project.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/dcuccia/md2pdf.git
cd md2pdf

# Install Python dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install Node.js dependencies
npm install
```

## Running Tests

```bash
# All tests
npm run test:all

# Python tests only
python -m pytest tests/ -v

# JS tests only
npx jest --verbose
```

## Project Architecture

```
document.md → md2svg.py → *.svg charts
     │                        │
     └→ lib/md2html.py → styled HTML → lib/html2pdf.js → PDF
          (+ CSS theme)    (+ Mermaid CDN)   (headless Chromium)
```

Three pipeline stages, each in its own file:

| Stage | File | Language | Tests |
|-------|------|----------|-------|
| Chart generation | `md2svg.py` | Python | `tests/test_md2svg.py` |
| MD → HTML | `lib/md2html.py` | Python | `tests/test_md2html.py` |
| HTML → PDF | `lib/html2pdf.js` | Node.js | `tests/html2pdf.test.js` |

Shell scripts (`md2pdf.ps1`, `md2pdf.sh`) are thin orchestrators that call
these stages in sequence. They must stay in sync with each other.

## Common Contributions

### Adding a New Chart Type

1. Add a `generate_<type>(spec: dict) -> str` function in `md2svg.py`
2. Register it in the `CHART_GENERATORS` dispatch table
3. Add tests in `tests/test_md2svg.py` (at minimum: valid SVG output,
   labels present, empty data returns empty string)
4. Add an example in `docs/guide.md` with a YAML block and rendered SVG

### Adding a New Theme

1. Create `themes/<name>.css` — copy the structure from `themes/default.css`
2. Must include: `@page` rule, body, h1, h2, table/th/td, blockquote, lists,
   img, hr, code/pre
3. Add a test in `tests/test_md2html.py` under `TestConvertWithThemes`
4. Update the theme table in `README.md` and `docs/guide.md`

### Modifying the Pipeline

If you change `lib/md2html.py` or `lib/html2pdf.js`, check that both shell
scripts (`md2pdf.ps1` and `md2pdf.sh`) still call them correctly with the
same arguments.

## Code Style

- **Python:** 4-space indent, type hints on public functions, docstrings on
  modules and public functions
- **JavaScript:** 2-space indent, JSDoc on exported functions, CommonJS modules
- **CSS:** Comment header with theme name and description

## Pull Request Checklist

Before opening a PR, please ensure:

- [ ] All tests pass (`npm run test:all`)
- [ ] New features have tests
- [ ] Both shell scripts updated if pipeline changed
- [ ] Documentation updated if user-facing behavior changed
