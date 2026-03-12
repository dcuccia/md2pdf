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
    $md2svgPath = Join-Path $ScriptDir "lib\md2svg.py"
    if (Test-Path $md2svgPath) {
        Write-Host "[md2pdf] Scanning for @chart blocks..." -ForegroundColor DarkCyan
        python $md2svgPath $MdFile
    }

    # Step 1: MD -> HTML via Python
    $md2htmlPath = Join-Path $ScriptDir "lib\md2html.py"
    python $md2htmlPath $MdFile $HtmlFile $CssPath --image-scale $ImageScale
    if ($LASTEXITCODE -ne 0) { throw "HTML generation failed for $BaseName" }

    # Step 2: HTML -> PDF via Playwright (headless Chromium)
    $html2pdfPath = Join-Path $ScriptDir "lib\html2pdf.js"
    $HtmlName = [System.IO.Path]::GetFileName($HtmlFile)
    node $html2pdfPath $Dir $HtmlName $PdfFile
    if ($LASTEXITCODE -ne 0) { throw "PDF generation failed for $BaseName" }

    Write-Host "[md2pdf] Done: $PdfFile" -ForegroundColor Green
}
