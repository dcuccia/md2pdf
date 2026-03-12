"""
md2html — Convert Markdown to styled HTML with a transform pipeline.

Reads a Markdown file, applies a CSS theme, and runs a series of transforms
to support Mermaid diagrams, GitHub-style alerts, math (KaTeX), syntax
highlighting, task lists, and page breaks.

Each transform follows the same interface:
    def transform_feature(html: str) -> tuple[str, list[str], list[str]]
    Returns (modified_html, scripts_to_inject, styles_to_inject)

Usage:
    python md2html.py <input.md> <output.html> <theme.css> [--image-scale N]
"""

import markdown
import os
import re
import sys
import yaml


# ═══════════════════════════════════════════════════════════════════════
# Frontmatter
# ═══════════════════════════════════════════════════════════════════════

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(md_text: str) -> tuple[str, dict]:
    """Extract YAML frontmatter from markdown text.

    Returns (remaining_markdown, frontmatter_dict). If no frontmatter
    is found, returns the original text and an empty dict.

    Supported frontmatter keys:
        title, author, date, theme, image_scale,
        margin_top, margin_bottom, margin_left, margin_right
    """
    m = FRONTMATTER_RE.match(md_text)
    if not m:
        return md_text, {}
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return md_text, {}
    if not isinstance(meta, dict):
        return md_text, {}
    return md_text[m.end():], meta


# ═══════════════════════════════════════════════════════════════════════
# Transforms — each returns (html, scripts[], styles[])
# ═══════════════════════════════════════════════════════════════════════

def transform_mermaid(html: str) -> tuple[str, list[str], list[str]]:
    """Convert fenced mermaid code blocks to Mermaid-compatible divs."""
    html = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        r'<pre class="mermaid">\1</pre>',
        html,
        flags=re.DOTALL,
    )
    scripts = []
    if '<pre class="mermaid">' in html:
        scripts.append(
            '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>'
            "<script>mermaid.initialize({startOnLoad:true});</script>"
        )
    return html, scripts, []


# GitHub alert types and their default labels/icons
_ALERT_TYPES = {
    "NOTE": ("ℹ️", "note"),
    "TIP": ("💡", "tip"),
    "IMPORTANT": ("❗", "important"),
    "WARNING": ("⚠️", "warning"),
    "CAUTION": ("🔴", "caution"),
}

# Matches a blockquote whose first line is [!TYPE]
_ALERT_RE = re.compile(
    r"<blockquote>\s*<p>\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*\n?(.*?)</p>\s*</blockquote>",
    re.DOTALL | re.IGNORECASE,
)


def transform_alerts(html: str) -> tuple[str, list[str], list[str]]:
    """Convert GitHub-style alerts to styled callout divs.

    Transforms:
        > [!NOTE]
        > This is a note.

    Into styled divs with icon, title, and body.
    """
    def _replace_alert(m: re.Match) -> str:
        alert_type = m.group(1).upper()
        body = m.group(2).strip()
        icon, css_class = _ALERT_TYPES.get(alert_type, ("", "note"))
        title = alert_type.capitalize()
        return (
            f'<div class="md2pdf-alert md2pdf-alert-{css_class}">'
            f'<p class="md2pdf-alert-title">{icon} {title}</p>'
            f"<p>{body}</p></div>"
        )

    html = _ALERT_RE.sub(_replace_alert, html)
    return html, [], []


def transform_task_lists(html: str) -> tuple[str, list[str], list[str]]:
    """Convert task list markers to HTML checkboxes.

    Transforms [ ] and [x] at the start of list items into styled checkboxes.
    """
    html = re.sub(
        r"<li>\s*\[ \]\s*",
        '<li class="md2pdf-task"><input type="checkbox" disabled> ',
        html,
    )
    html = re.sub(
        r"<li>\s*\[x\]\s*",
        '<li class="md2pdf-task md2pdf-task-done"><input type="checkbox" checked disabled> ',
        html,
        flags=re.IGNORECASE,
    )
    return html, [], []


def transform_syntax_highlight(html: str) -> tuple[str, list[str], list[str]]:
    """Inject Highlight.js for syntax-highlighted code blocks.

    Detects fenced code blocks with language tags (class="language-*")
    and adds the Highlight.js CDN for client-side highlighting.
    """
    scripts = []
    styles = []
    if re.search(r'class="language-', html):
        styles.append(
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github.min.css">'
        )
        scripts.append(
            '<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/highlight.min.js"></script>'
            "<script>hljs.highlightAll();</script>"
        )
    return html, scripts, styles


def transform_math(html: str) -> tuple[str, list[str], list[str]]:
    """Render LaTeX math expressions via KaTeX.

    Supports $inline$ and $$block$$ math. The KaTeX auto-render extension
    handles delimiter detection client-side.
    """
    scripts = []
    styles = []
    # Check for math delimiters in the raw HTML
    has_math = bool(re.search(r"\$\$.*?\$\$", html, re.DOTALL)) or bool(
        re.search(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", html)
    )
    if has_math:
        styles.append(
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.css">'
        )
        scripts.append(
            '<script src="https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.js"></script>'
            '<script src="https://cdn.jsdelivr.net/npm/katex@0.16/dist/contrib/auto-render.min.js"></script>'
            "<script>document.addEventListener('DOMContentLoaded',function(){"
            "renderMathInElement(document.body,{delimiters:["
            "{left:'$$',right:'$$',display:true},"
            "{left:'$',right:'$',display:false}"
            "]})});</script>"
        )
    return html, scripts, styles


def transform_page_breaks(html: str) -> tuple[str, list[str], list[str]]:
    """Convert <!-- pagebreak --> comments to CSS page breaks."""
    html = re.sub(
        r"<!--\s*pagebreak\s*-->",
        '<div class="md2pdf-pagebreak"></div>',
        html,
        flags=re.IGNORECASE,
    )
    return html, [], []


# ═══════════════════════════════════════════════════════════════════════
# Transform Pipeline
# ═══════════════════════════════════════════════════════════════════════

TRANSFORMS = [
    transform_mermaid,
    transform_alerts,
    transform_task_lists,
    transform_syntax_highlight,
    transform_math,
    transform_page_breaks,
]


def run_transforms(html: str) -> tuple[str, list[str], list[str]]:
    """Run all transforms on HTML body.

    Returns (transformed_html, all_scripts, all_styles).
    """
    all_scripts: list[str] = []
    all_styles: list[str] = []
    for transform in TRANSFORMS:
        html, scripts, styles = transform(html)
        all_scripts.extend(scripts)
        all_styles.extend(styles)
    return html, all_scripts, all_styles


# ═══════════════════════════════════════════════════════════════════════
# Conversion
# ═══════════════════════════════════════════════════════════════════════

def convert(md_path: str, html_path: str, css_path: str, image_scale: int = 350) -> int:
    """Convert a Markdown file to styled HTML.

    Returns the size of the generated HTML file in bytes.
    """
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Extract frontmatter (if present)
    md_text, meta = parse_frontmatter(md_text)

    # Apply frontmatter overrides
    image_scale = meta.get("image_scale", image_scale)

    # Scale images for PDF rendering
    md_text = md_text.replace('height="300"', f'height="{image_scale}"')

    html_body = markdown.markdown(
        md_text, extensions=["tables", "md_in_html", "fenced_code"]
    )

    # Run transform pipeline
    html_body, scripts, styles = run_transforms(html_body)

    # Load theme CSS
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Assemble HTML document
    head_parts = ['<meta charset="utf-8">', f"<style>{css}</style>"]
    head_parts.extend(styles)
    head_parts.extend(scripts)

    if meta.get("title"):
        head_parts.append(f"<title>{meta['title']}</title>")

    html = (
        "<!DOCTYPE html><html><head>"
        + "".join(head_parts)
        + "</head><body>"
        + html_body
        + "</body></html>"
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return os.path.getsize(html_path)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python md2html.py <input.md> <output.html> <theme.css> [--image-scale N]")
        sys.exit(1)

    md_file = sys.argv[1]
    html_file = sys.argv[2]
    css_file = sys.argv[3]

    scale = 350
    if "--image-scale" in sys.argv:
        idx = sys.argv.index("--image-scale")
        scale = int(sys.argv[idx + 1])

    size = convert(md_file, html_file, css_file, image_scale=scale)
    print(f"HTML: {size} bytes")
