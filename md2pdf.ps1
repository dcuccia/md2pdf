<#
.SYNOPSIS
    Converts a Markdown file to PDF via styled HTML intermediate.

.DESCRIPTION
    Uses Python 'markdown' library for MD->HTML conversion with a bundled CSS
    theme, then Playwright (headless Chromium) for HTML->PDF rendering.
    Idempotent: installs required tools on first run if missing.
    Never overwrites existing PDFs — auto-increments the filename suffix.

.PARAMETER Path
    Path to the .md file to convert. Defaults to all .md files in the parent directory.

.PARAMETER ImageScale
    Scale factor for header images (height in px). Default: 350.

.PARAMETER Theme
    Path to a CSS theme file. Default: themes/default.css (relative to script directory).

.EXAMPLE
    .\md2pdf.ps1 "..\My Document.md"

.EXAMPLE
    .\md2pdf.ps1 -Theme themes/academic.css
    # Converts using the academic theme
#>
param(
    [Parameter(Position = 0)]
    [string]$Path,

    [int]$ImageScale = 350,

    [string]$Theme
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Resolve theme CSS path
if ($Theme) {
    if (-not [System.IO.Path]::IsPathRooted($Theme)) {
        $CssPath = Join-Path $ScriptDir $Theme
    } else {
        $CssPath = $Theme
    }
} else {
    $CssPath = Join-Path $ScriptDir "themes\default.css"
}
if (-not (Test-Path $CssPath)) { throw "Theme not found: $CssPath" }

# --- Dependency checks (idempotent) ---

function Ensure-PythonMarkdown {
    $check = python -c "import markdown; print('ok')" 2>&1
    if ($check -ne "ok") {
        Write-Host "[md2pdf] Installing Python 'markdown' library..." -ForegroundColor Yellow
        pip install markdown --quiet
        if ($LASTEXITCODE -ne 0) { throw "Failed to install Python markdown library" }
    }
}

function Ensure-PyYAML {
    $check = python -c "import yaml; print('ok')" 2>&1
    if ($check -ne "ok") {
        Write-Host "[md2pdf] Installing Python 'pyyaml' library..." -ForegroundColor Yellow
        pip install pyyaml --quiet
        if ($LASTEXITCODE -ne 0) { throw "Failed to install Python pyyaml library" }
    }
}

function Ensure-Playwright {
    $localModules = Join-Path $ScriptDir "node_modules"
    $pwLib = Join-Path $localModules "playwright"
    if (-not (Test-Path $pwLib)) {
        Write-Host "[md2pdf] Installing Playwright locally..." -ForegroundColor Yellow
        Push-Location $ScriptDir
        npm install playwright 2>&1 | Out-Null
        npx playwright install chromium 2>&1 | Out-Null
        Pop-Location
        if (-not (Test-Path $pwLib)) { throw "Failed to install Playwright" }
    }
}

Write-Host "[md2pdf] Checking dependencies..." -ForegroundColor Cyan
Ensure-PythonMarkdown
Ensure-PyYAML
Ensure-Playwright

# Point Node at the local node_modules so require('playwright') works
$env:NODE_PATH = Join-Path $ScriptDir "node_modules"

# --- Resolve input files ---

if ($Path) {
    # Resolve relative paths against the script's parent directory, not CWD
    if (-not [System.IO.Path]::IsPathRooted($Path)) {
        $Path = Join-Path (Split-Path -Parent $ScriptDir) $Path
    }
    $MdFiles = @(Resolve-Path $Path)
}
else {
    $ParentDir = Split-Path -Parent $ScriptDir
    $MdFiles = @(Get-ChildItem -Path $ParentDir -Filter "*.md" | Select-Object -ExpandProperty FullName)
    if ($MdFiles.Count -eq 0) {
        Write-Host "[md2pdf] No .md files found in $ParentDir" -ForegroundColor Red
        exit 1
    }
    Write-Host "[md2pdf] Found $($MdFiles.Count) .md file(s) in parent directory" -ForegroundColor Cyan
}

# --- Auto-increment helper: never overwrite an existing PDF ---

function Get-NextPdfPath {
    param([string]$Dir, [string]$BaseName)
    $candidate = Join-Path $Dir "$BaseName.pdf"
    if (-not (Test-Path $candidate)) { return $candidate }
    $counter = 1
    do {
        $candidate = Join-Path $Dir "${BaseName}_${counter}.pdf"
        $counter++
    } while (Test-Path $candidate)
    return $candidate
}

# --- Convert each file ---

foreach ($MdFile in $MdFiles) {
    $MdFile = [string]$MdFile
    $Dir = Split-Path -Parent $MdFile
    $BaseName = [System.IO.Path]::GetFileNameWithoutExtension($MdFile)
    $PdfFile = Get-NextPdfPath -Dir $Dir -BaseName $BaseName
    $PdfBaseName = [System.IO.Path]::GetFileNameWithoutExtension($PdfFile)
    $HtmlFile = Join-Path $Dir "$PdfBaseName.html"
    $PdfName = [System.IO.Path]::GetFileName($PdfFile)

    Write-Host "[md2pdf] Converting: $BaseName.md -> $PdfName" -ForegroundColor Cyan

    # Step 0: Generate SVGs from @chart YAML blocks
    $md2svgPath = Join-Path $ScriptDir "md2svg.py"
    if (Test-Path $md2svgPath) {
        Write-Host "[md2pdf] Scanning for @chart blocks..." -ForegroundColor DarkCyan
        python $md2svgPath $MdFile
    }

    # Step 1: MD -> HTML via Python
    $pyScript = @"
import markdown, os, sys, re

md_path = sys.argv[1]
html_path = sys.argv[2]
css_path = sys.argv[3]
img_height = sys.argv[4]

with open(md_path, 'r', encoding='utf-8') as f:
    md_text = f.read()

# Scale images for PDF rendering
md_text = md_text.replace('height="300"', f'height="{img_height}"')

html_body = markdown.markdown(md_text, extensions=['tables', 'md_in_html', 'fenced_code'])

# Convert fenced mermaid code blocks to Mermaid-compatible divs
html_body = re.sub(
    r'<pre><code class="language-mermaid">(.*?)</code></pre>',
    r'<pre class="mermaid">\1</pre>',
    html_body, flags=re.DOTALL
)

with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

# Add Mermaid script if mermaid blocks are present
mermaid_script = ''
if '<pre class="mermaid">' in html_body:
    mermaid_script = '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script><script>mermaid.initialize({startOnLoad:true});</script>'

html = '<!DOCTYPE html><html><head><meta charset="utf-8"><style>' + css + '</style>' + mermaid_script + '</head><body>' + html_body + '</body></html>'

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'HTML: {os.path.getsize(html_path)} bytes')
"@

    $pyTempFile = Join-Path $env:TEMP "md2pdf_convert.py"
    $pyScript | Set-Content -Path $pyTempFile -Encoding UTF8
    python $pyTempFile $MdFile $HtmlFile $CssPath $ImageScale
    if ($LASTEXITCODE -ne 0) { throw "HTML generation failed for $BaseName" }

    # Step 2: HTML -> PDF via Playwright (local HTTP server + headless Chromium)
    $jsScript = @"
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');

const dir = process.argv[2];
const htmlName = process.argv[3];
const pdfPath = process.argv[4];

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
"@

    $jsTempFile = Join-Path $env:TEMP "md2pdf_print.js"
    $jsScript | Set-Content -Path $jsTempFile -Encoding UTF8
    $HtmlName = [System.IO.Path]::GetFileName($HtmlFile)
    node $jsTempFile $Dir $HtmlName $PdfFile
    if ($LASTEXITCODE -ne 0) { throw "PDF generation failed for $BaseName" }

    Write-Host "[md2pdf] Done: $PdfFile" -ForegroundColor Green
}
