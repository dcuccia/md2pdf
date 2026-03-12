#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# md2pdf.sh — Markdown to PDF Converter
#
# Converts .md files to styled PDF via HTML intermediate using:
#   • Python 'markdown' library  (MD → HTML)
#   • Playwright headless Chromium (HTML → PDF)
#
# Idempotent: installs required tools on first run if missing.
# Never overwrites — auto-increments filename suffix (_1, _2, ...).
#
# Usage:
#   ./md2pdf.sh "../My Document.md"
#   ./md2pdf.sh                           # all .md in parent dir
#   ./md2pdf.sh --image-scale 400         # larger header images
#   ./md2pdf.sh --theme themes/academic.css
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Defaults ──
IMAGE_SCALE=350
MD_PATH=""
THEME=""

# ── Parse arguments ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --image-scale)     IMAGE_SCALE="$2"; shift 2 ;;
        --theme)           THEME="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: md2pdf.sh [OPTIONS] [path/to/file.md]"
            echo ""
            echo "Options:"
            echo "  --image-scale N      Header image height in px (default: 350)"
            echo "  --theme PATH         CSS theme file (default: themes/default.css)"
            echo "  -h, --help           Show this help"
            echo ""
            echo "If no path is given, converts all .md files in the parent directory."
            echo "Never overwrites existing PDFs — auto-increments suffix (_1, _2, ...)."
            exit 0
            ;;
        -*)                echo "Unknown option: $1" >&2; exit 1 ;;
        *)                 MD_PATH="$1"; shift ;;
    esac
done

# ── Resolve script directory ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Resolve theme CSS path ──
if [[ -n "$THEME" ]]; then
    if [[ "$THEME" != /* ]]; then
        CSS_PATH="$SCRIPT_DIR/$THEME"
    else
        CSS_PATH="$THEME"
    fi
else
    CSS_PATH="$SCRIPT_DIR/themes/default.css"
fi
if [[ ! -f "$CSS_PATH" ]]; then
    echo "Theme not found: $CSS_PATH" >&2
    exit 1
fi

# ── Color helpers ──
cyan()   { printf '\033[36m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
red()    { printf '\033[31m%s\033[0m\n' "$*"; }

# ── Dependency checks (idempotent) ──

ensure_python_markdown() {
    if ! python3 -c "import markdown; print('ok')" 2>/dev/null | grep -q ok; then
        yellow "[md2pdf] Installing Python 'markdown' library..."
        pip3 install markdown --quiet
    fi
}

ensure_pyyaml() {
    if ! python3 -c "import yaml; print('ok')" 2>/dev/null | grep -q ok; then
        yellow "[md2pdf] Installing Python 'pyyaml' library..."
        pip3 install pyyaml --quiet
    fi
}

ensure_playwright() {
    local pw_lib="$SCRIPT_DIR/node_modules/playwright"
    if [[ ! -d "$pw_lib" ]]; then
        yellow "[md2pdf] Installing Playwright locally..."
        pushd "$SCRIPT_DIR" >/dev/null
        npm install playwright >/dev/null 2>&1
        npx playwright install chromium >/dev/null 2>&1
        popd >/dev/null
        if [[ ! -d "$pw_lib" ]]; then
            red "[md2pdf] Failed to install Playwright"; exit 1
        fi
    fi
}

cyan "[md2pdf] Checking dependencies..."
ensure_python_markdown
ensure_pyyaml
ensure_playwright

# Point Node at the local node_modules so require('playwright') works
export NODE_PATH="$SCRIPT_DIR/node_modules"

# ── Auto-increment helper: never overwrite an existing PDF ──

next_pdf_path() {
    local dir="$1" base="$2"
    local candidate="$dir/$base.pdf"
    if [[ ! -f "$candidate" ]]; then echo "$candidate"; return; fi
    local counter=1
    while [[ -f "$dir/${base}_${counter}.pdf" ]]; do
        counter=$((counter + 1))
    done
    echo "$dir/${base}_${counter}.pdf"
}

# ── Resolve input files ──

MD_FILES=()

if [[ -n "$MD_PATH" ]]; then
    # Resolve relative paths against the script's parent directory, not CWD
    if [[ "$MD_PATH" != /* ]]; then
        MD_PATH="$PARENT_DIR/$MD_PATH"
    fi
    # Resolve to absolute path
    MD_PATH="$(cd "$(dirname "$MD_PATH")" && pwd)/$(basename "$MD_PATH")"
    if [[ ! -f "$MD_PATH" ]]; then
        red "[md2pdf] File not found: $MD_PATH"
        exit 1
    fi
    MD_FILES+=("$MD_PATH")
else
    while IFS= read -r -d '' f; do
        MD_FILES+=("$f")
    done < <(find "$PARENT_DIR" -maxdepth 1 -name "*.md" -print0)
    if [[ ${#MD_FILES[@]} -eq 0 ]]; then
        red "[md2pdf] No .md files found in $PARENT_DIR"
        exit 1
    fi
    cyan "[md2pdf] Found ${#MD_FILES[@]} .md file(s) in parent directory"
fi

# ── Convert each file ──

for MD_FILE in "${MD_FILES[@]}"; do
    DIR="$(dirname "$MD_FILE")"
    BASENAME="$(basename "$MD_FILE" .md)"
    PDF_FILE="$(next_pdf_path "$DIR" "$BASENAME")"
    PDF_BASENAME="$(basename "$PDF_FILE" .pdf)"
    HTML_FILE="$DIR/$PDF_BASENAME.html"
    PDF_NAME="$(basename "$PDF_FILE")"

    cyan "[md2pdf] Converting: $BASENAME.md -> $PDF_NAME"

    # Step 0: Generate SVGs from @chart YAML blocks
    MD2SVG="$SCRIPT_DIR/md2svg.py"
    if [[ -f "$MD2SVG" ]]; then
        cyan "[md2pdf] Scanning for @chart blocks..."
        python3 "$MD2SVG" "$MD_FILE"
    fi

    # Step 1: MD -> HTML via Python
    python3 -c "
import markdown, os, sys, re

md_path = sys.argv[1]
html_path = sys.argv[2]
css_path = sys.argv[3]
img_height = sys.argv[4]

with open(md_path, 'r', encoding='utf-8') as f:
    md_text = f.read()

# Scale images for PDF rendering
md_text = md_text.replace('height=\"300\"', f'height=\"{img_height}\"')

html_body = markdown.markdown(md_text, extensions=['tables', 'md_in_html', 'fenced_code'])

# Convert fenced mermaid code blocks to Mermaid-compatible divs
html_body = re.sub(
    r'<pre><code class=\"language-mermaid\">(.*?)</code></pre>',
    r'<pre class=\"mermaid\">\1</pre>',
    html_body, flags=re.DOTALL
)

with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

# Add Mermaid script if mermaid blocks are present
mermaid_script = ''
if '<pre class=\"mermaid\">' in html_body:
    mermaid_script = '<script src=\"https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js\"></script><script>mermaid.initialize({startOnLoad:true});</script>'

html = '<!DOCTYPE html><html><head><meta charset=\"utf-8\"><style>' + css + '</style>' + mermaid_script + '</head><body>' + html_body + '</body></html>'

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'HTML: {os.path.getsize(html_path)} bytes')
" "$MD_FILE" "$HTML_FILE" "$CSS_PATH" "$IMAGE_SCALE"

    # Step 2: HTML -> PDF via Playwright (local HTTP server + headless Chromium)
    HTML_NAME="$(basename "$HTML_FILE")"
    node -e "
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');

const dir = process.argv[1];
const htmlName = process.argv[2];
const pdfPath = process.argv[3];

const mimeTypes = {
    '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.svg': 'image/svg+xml'
};

const server = http.createServer((req, res) => {
    const filePath = path.join(dir, decodeURIComponent(req.url.replace(/^\//, '')));
    if (!fs.existsSync(filePath)) { res.writeHead(404); res.end(); return; }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
    fs.createReadStream(filePath).pipe(res);
});

(async () => {
    await new Promise(r => server.listen(0, '127.0.0.1', r));
    const port = server.address().port;
    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto('http://127.0.0.1:' + port + '/' + encodeURIComponent(htmlName), { waitUntil: 'networkidle' });
    await page.waitForFunction(() => {
        const els = document.querySelectorAll('.mermaid');
        return els.length === 0 || [...els].every(el => el.querySelector('svg'));
    }, { timeout: 15000 }).catch(() => {});
    await page.pdf({
        path: pdfPath, format: 'Letter', printBackground: true,
        margin: { top: '0.6in', bottom: '0.6in', left: '0.75in', right: '0.75in' }
    });
    await browser.close();
    server.close();
    console.log('PDF: ' + fs.statSync(pdfPath).size + ' bytes');
})();
" "$DIR" "$HTML_NAME" "$PDF_FILE"

    green "[md2pdf] Done: $PDF_FILE"
done
