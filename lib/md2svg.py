"""
md2svg — Extract YAML @chart blocks from Markdown and generate SVG files.

Scans a Markdown file for fenced ```yaml blocks whose first line is a
# @chart → filename.svg comment.  Parses the YAML data and dispatches to
the appropriate chart generator.

Also scans for HTML-comment-tagged pipe tables:
    <!-- @chart: type → filename.svg -->
    | Col1 | Col2 |
    |------|------|
    | a    | 1    |

Supported chart types: bar, hbar, pie, sunburst

Usage:
    python md2svg.py path/to/document.md          # generate SVGs next to .md
    python md2svg.py path/to/document.md --list    # list @chart blocks only
"""

import math
import re
import sys
import yaml
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════
# SVG Primitives
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_FONT = "Segoe UI, Helvetica, Arial, sans-serif"
MONO_FONT = "Consolas, monospace"

# Qualitative palette (color-blind friendly, based on Tableau 10)
PALETTE = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
]


def _esc(text: str) -> str:
    """Escape text for SVG XML."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _polar_to_cart(cx: float, cy: float, r: float, angle_deg: float) -> tuple[float, float]:
    """Convert polar to cartesian.  0° = 12 o'clock, clockwise."""
    rad = math.radians(angle_deg - 90)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def _arc_path(cx: float, cy: float, r_in: float, r_out: float,
              start: float, end: float) -> str:
    """SVG path for an annular sector."""
    sweep = end - start
    large = 1 if sweep > 180 else 0
    ox1, oy1 = _polar_to_cart(cx, cy, r_out, start)
    ox2, oy2 = _polar_to_cart(cx, cy, r_out, end)
    ix1, iy1 = _polar_to_cart(cx, cy, r_in, end)
    ix2, iy2 = _polar_to_cart(cx, cy, r_in, start)
    if r_in < 1:
        return (f"M {cx:.1f},{cy:.1f} L {ox1:.1f},{oy1:.1f} "
                f"A {r_out:.1f},{r_out:.1f} 0 {large},1 {ox2:.1f},{oy2:.1f} Z")
    return (f"M {ox1:.1f},{oy1:.1f} "
            f"A {r_out:.1f},{r_out:.1f} 0 {large},1 {ox2:.1f},{oy2:.1f} "
            f"L {ix1:.1f},{iy1:.1f} "
            f"A {r_in:.1f},{r_in:.1f} 0 {large},0 {ix2:.1f},{iy2:.1f} Z")


def _arc_label_pos(cx, cy, r, start, end):
    mid = (start + end) / 2
    return _polar_to_cart(cx, cy, r, mid)


# ═══════════════════════════════════════════════════════════════════════
# Chart Generators
# ═══════════════════════════════════════════════════════════════════════

def generate_bar(spec: dict) -> str:
    """Vertical bar chart from flat key:value data."""
    title = spec.get("title", "")
    data = spec.get("data", {})
    if not data:
        return ""
    items = list(data.items())
    n = len(items)
    max_val = max(v for _, v in items)

    W, H = 600, 400
    margin_l, margin_r, margin_t, margin_b = 70, 30, 60, 60
    chart_w = W - margin_l - margin_r
    chart_h = H - margin_t - margin_b
    bar_w = chart_w / n * 0.65
    gap = chart_w / n

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
             f'<rect width="{W}" height="{H}" fill="white"/>']

    if title:
        parts.append(f'<text x="{W/2}" y="35" text-anchor="middle" font-size="16" '
                     f'font-weight="700" fill="#333" font-family="{DEFAULT_FONT}">{_esc(title)}</text>')
    # Y-axis gridlines
    for i in range(5):
        y = margin_t + chart_h - (i / 4) * chart_h
        val = max_val * i / 4
        parts.append(f'<line x1="{margin_l}" y1="{y:.0f}" x2="{W - margin_r}" y2="{y:.0f}" '
                     f'stroke="#E0E0E0" stroke-width="0.5"/>')
        parts.append(f'<text x="{margin_l - 8}" y="{y + 4:.0f}" text-anchor="end" font-size="10" '
                     f'fill="#666" font-family="{DEFAULT_FONT}">{val:g}</text>')

    # Bars
    for i, (label, val) in enumerate(items):
        x = margin_l + i * gap + (gap - bar_w) / 2
        bar_h = (val / max_val) * chart_h if max_val else 0
        y = margin_t + chart_h - bar_h
        color = PALETTE[i % len(PALETTE)]
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                     f'rx="3" fill="{color}" opacity="0.85"/>')
        # Value label above bar
        parts.append(f'<text x="{x + bar_w/2:.1f}" y="{y - 6:.1f}" text-anchor="middle" '
                     f'font-size="10" font-weight="600" fill="#333" font-family="{DEFAULT_FONT}">{val}</text>')
        # Category label below
        parts.append(f'<text x="{x + bar_w/2:.1f}" y="{margin_t + chart_h + 18:.0f}" text-anchor="middle" '
                     f'font-size="10" fill="#444" font-family="{DEFAULT_FONT}">{_esc(label)}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


def generate_hbar(spec: dict) -> str:
    """Horizontal bar chart from flat key:value data."""
    title = spec.get("title", "")
    data = spec.get("data", {})
    if not data:
        return ""
    items = list(data.items())
    n = len(items)
    max_val = max(v for _, v in items)

    label_w = 120
    W = 600
    margin_r, margin_t = 30, 60
    bar_h_unit = 28
    gap = 36
    chart_h = n * gap
    H = margin_t + chart_h + 40

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
             f'<rect width="{W}" height="{H}" fill="white"/>']

    if title:
        parts.append(f'<text x="{W/2}" y="35" text-anchor="middle" font-size="16" '
                     f'font-weight="700" fill="#333" font-family="{DEFAULT_FONT}">{_esc(title)}</text>')

    chart_w = W - label_w - margin_r
    for i, (label, val) in enumerate(items):
        y = margin_t + i * gap
        bar_w_px = (val / max_val) * chart_w if max_val else 0
        color = PALETTE[i % len(PALETTE)]
        # Label
        parts.append(f'<text x="{label_w - 8}" y="{y + bar_h_unit/2 + 4:.0f}" text-anchor="end" '
                     f'font-size="11" fill="#444" font-family="{DEFAULT_FONT}">{_esc(label)}</text>')
        # Bar
        parts.append(f'<rect x="{label_w}" y="{y:.0f}" width="{bar_w_px:.1f}" height="{bar_h_unit}" '
                     f'rx="3" fill="{color}" opacity="0.85"/>')
        # Value
        parts.append(f'<text x="{label_w + bar_w_px + 6:.1f}" y="{y + bar_h_unit/2 + 4:.0f}" '
                     f'font-size="10" font-weight="600" fill="#333" font-family="{DEFAULT_FONT}">{val}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


def generate_pie(spec: dict) -> str:
    """Pie/donut chart from flat key:value data."""
    title = spec.get("title", "")
    data = spec.get("data", {})
    donut = spec.get("donut", False)
    if not data:
        return ""
    items = list(data.items())
    total = sum(v for _, v in items)

    W, H = 500, 400
    cx, cy = 200, 220
    r_out = 140
    r_in = 70 if donut else 0
    gap = 0.8

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
             f'<rect width="{W}" height="{H}" fill="white"/>']

    if title:
        parts.append(f'<text x="{W/2}" y="35" text-anchor="middle" font-size="16" '
                     f'font-weight="700" fill="#333" font-family="{DEFAULT_FONT}">{_esc(title)}</text>')

    angle = 0
    legend_y = 80
    for i, (label, val) in enumerate(items):
        sweep = (val / total) * 360 if total else 0
        s, e = angle + gap / 2, angle + sweep - gap / 2
        color = PALETTE[i % len(PALETTE)]
        if e > s:
            parts.append(f'<path d="{_arc_path(cx, cy, r_in, r_out, s, e)}" '
                         f'fill="{color}" stroke="white" stroke-width="1.5" opacity="0.9"/>')
            if sweep > 18:
                lx, ly = _arc_label_pos(cx, cy, (r_in + r_out) / 2, s, e)
                pct = val / total * 100
                parts.append(f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" '
                             f'dominant-baseline="central" font-size="10" font-weight="600" '
                             f'fill="white" font-family="{DEFAULT_FONT}">{pct:.0f}%</text>')
        # Legend
        ly = legend_y + i * 22
        parts.append(f'<rect x="380" y="{ly}" width="14" height="14" rx="2" fill="{color}"/>')
        pct = val / total * 100 if total else 0
        parts.append(f'<text x="400" y="{ly + 11}" font-size="10" fill="#444" '
                     f'font-family="{DEFAULT_FONT}">{_esc(label)} ({pct:.0f}%)</text>')
        angle += sweep

    parts.append('</svg>')
    return "\n".join(parts)


def _sunburst_recursive(parts, labels, cx, cy, data, total, start_angle,
                        sweep_total, ring, ring_radii, gap, depth_limit):
    """Recursively render sunburst rings."""
    if ring >= len(ring_radii) or ring >= depth_limit:
        return
    r_in, r_out = ring_radii[ring]
    angle = start_angle
    for i, (label, node) in enumerate(data.items()):
        val = node if isinstance(node, (int, float)) else sum(
            v if isinstance(v, (int, float)) else 0 for v in node.values()) if isinstance(node, dict) else 0
        sweep = (val / total) * sweep_total if total else 0
        s, e = angle + gap / 2, angle + sweep - gap / 2
        color = PALETTE[(ring * 5 + i) % len(PALETTE)]
        opacity = max(0.6, 0.95 - ring * 0.1)
        if e > s:
            parts.append(f'<path d="{_arc_path(cx, cy, r_in, r_out, s, e)}" '
                         f'fill="{color}" stroke="white" stroke-width="1" opacity="{opacity}"/>')
            if sweep > 12:
                lx, ly = _arc_label_pos(cx, cy, (r_in + r_out) / 2, s, e)
                fs = max(8, 12 - ring * 2)
                parts.append(f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" '
                             f'dominant-baseline="central" font-size="{fs}" font-weight="600" '
                             f'fill="white" font-family="{DEFAULT_FONT}">{_esc(str(label))}</text>')
        # Recurse into children
        if isinstance(node, dict):
            _sunburst_recursive(parts, labels, cx, cy, node, val, angle,
                                sweep, ring + 1, ring_radii, gap, depth_limit)
        angle += sweep


def generate_sunburst(spec: dict) -> str:
    """Sunburst chart from nested key:value data."""
    title = spec.get("title", "")
    data = spec.get("data", {})
    if not data:
        return ""

    # Determine max depth
    def _depth(d):
        if not isinstance(d, dict):
            return 0
        return 1 + max((_depth(v) for v in d.values()), default=0)

    max_d = min(_depth(data), 5)
    W, H = 600, 500
    cx, cy = 260, 270

    ring_radii = []
    r = 0
    for i in range(max_d):
        r_in = r
        r_out = r + max(50, 100 - i * 15)
        ring_radii.append((r_in, r_out))
        r = r_out + 5

    # Compute total from top-level
    def _val(node):
        if isinstance(node, (int, float)):
            return node
        if isinstance(node, dict):
            return sum(_val(v) for v in node.values())
        return 0

    total = sum(_val(v) for v in data.values())

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
             f'<rect width="{W}" height="{H}" fill="white"/>']
    if title:
        parts.append(f'<text x="{W/2}" y="35" text-anchor="middle" font-size="16" '
                     f'font-weight="700" fill="#333" font-family="{DEFAULT_FONT}">{_esc(title)}</text>')

    labels = []
    _sunburst_recursive(parts, labels, cx, cy, data, total, 0, 360,
                        0, ring_radii, 0.8, max_d)

    # Legend (top-level items)
    legend_x, legend_y = W - 130, 70
    for i, label in enumerate(data.keys()):
        ly = legend_y + i * 22
        color = PALETTE[i % len(PALETTE)]
        val = _val(data[label])
        pct = val / total * 100 if total else 0
        parts.append(f'<rect x="{legend_x}" y="{ly}" width="14" height="14" rx="2" fill="{color}"/>')
        parts.append(f'<text x="{legend_x + 20}" y="{ly + 11}" font-size="10" fill="#444" '
                     f'font-family="{DEFAULT_FONT}">{_esc(str(label))} ({pct:.0f}%)</text>')

    parts.append('</svg>')
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# Chart dispatcher
# ═══════════════════════════════════════════════════════════════════════

CHART_GENERATORS = {
    "bar": generate_bar,
    "hbar": generate_hbar,
    "pie": generate_pie,
    "donut": lambda spec: generate_pie({**spec, "donut": True}),
    "sunburst": generate_sunburst,
}


# ═══════════════════════════════════════════════════════════════════════
# Markdown Scanner
# ═══════════════════════════════════════════════════════════════════════

# Pattern: ```yaml block starting with # @chart → filename.svg
# Uses non-greedy match and requires closing ``` on its own line (not ```yaml etc.)
YAML_CHART_RE = re.compile(
    r"^```ya?ml\s*\n"
    r"\s*#\s*@chart\s*→\s*([^\n]+\.svg)\s*\n"
    r"(.*?)"
    r"^```\s*$",
    re.DOTALL | re.MULTILINE,
)

# Pattern: <!-- @chart: type → filename.svg --> followed by a pipe table
TABLE_CHART_RE = re.compile(
    r"<!--\s*@chart:\s*(\w+)\s*→\s*(.+\.svg)\s*-->\s*\n"
    r"((?:\|.+\|\s*\n)+)",
    re.DOTALL,
)


def _parse_pipe_table(table_text: str) -> dict:
    """Parse a pipe table into {col1_val: col2_val} dict."""
    lines = [l.strip() for l in table_text.strip().split("\n") if l.strip()]
    if len(lines) < 3:
        return {}
    # Skip header row and separator row
    data = {}
    for line in lines[2:]:
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= 2:
            try:
                data[cells[0]] = float(cells[1])
            except ValueError:
                continue
    return data


def scan_charts(md_text: str) -> list[dict]:
    """Scan markdown text for @chart blocks.  Returns list of specs."""
    specs = []

    # Strip content inside 4+ backtick fences to avoid matching nested examples
    stripped = re.sub(r"^[`]{4,}.*?^[`]{4,}", "", md_text, flags=re.DOTALL | re.MULTILINE)

    # YAML fenced blocks
    for m in YAML_CHART_RE.finditer(stripped):
        filename = m.group(1).strip()
        yaml_body = m.group(2)
        try:
            parsed = yaml.safe_load(yaml_body)
        except yaml.YAMLError as e:
            print(f"  [!] YAML parse error for {filename}: {e}", file=sys.stderr)
            continue
        if not isinstance(parsed, dict):
            continue
        parsed["_filename"] = filename
        specs.append(parsed)

    # HTML comment + pipe table (strip ALL code fences first to avoid matching examples)
    no_fences = re.sub(r"^```.*?^```", "", stripped, flags=re.DOTALL | re.MULTILINE)
    for m in TABLE_CHART_RE.finditer(no_fences):
        chart_type = m.group(1).strip()
        filename = m.group(2).strip()
        table_text = m.group(3)
        data = _parse_pipe_table(table_text)
        if data:
            specs.append({"type": chart_type, "data": data, "_filename": filename})

    return specs


def generate_charts(md_path: str | Path, *, list_only: bool = False) -> list[str]:
    """Scan a .md file and generate SVG files.  Returns list of generated filenames."""
    md_path = Path(md_path)
    md_text = md_path.read_text(encoding="utf-8")
    specs = scan_charts(md_text)

    if not specs:
        print(f"  No @chart blocks found in {md_path.name}")
        return []

    output_dir = md_path.parent
    generated = []

    for spec in specs:
        filename = spec.pop("_filename")
        chart_type = spec.get("type", "bar")

        if list_only:
            print(f"  [chart] {filename} (type: {chart_type})")
            generated.append(filename)
            continue

        gen_fn = CHART_GENERATORS.get(chart_type)
        if not gen_fn:
            print(f"  [!] Unknown chart type '{chart_type}' for {filename} "
                  f"(available: {', '.join(CHART_GENERATORS)})", file=sys.stderr)
            continue

        svg = gen_fn(spec)
        if not svg:
            print(f"  [!] No data for {filename}", file=sys.stderr)
            continue

        out_path = output_dir / filename
        out_path.write_text(svg, encoding="utf-8")
        size_kb = out_path.stat().st_size / 1024
        print(f"  [ok] {filename} ({size_kb:.1f} KB)")
        generated.append(filename)

    return generated


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python md2svg.py <file.md> [--list]")
        sys.exit(1)

    md_file = sys.argv[1]
    list_only = "--list" in sys.argv

    print(f"[md2svg] Scanning: {md_file}")
    results = generate_charts(md_file, list_only=list_only)
    if results:
        print(f"[md2svg] {'Listed' if list_only else 'Generated'}: {len(results)} chart(s)")
    else:
        print("[md2svg] No charts found or generated")
