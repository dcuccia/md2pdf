"""
md2html — Convert Markdown to styled HTML with Mermaid support.

Reads a Markdown file, applies a CSS theme, converts fenced mermaid blocks
to Mermaid-compatible divs, and writes a standalone HTML file ready for
PDF rendering.

Usage:
    python md2html.py <input.md> <output.html> <theme.css> [--image-scale N]
"""

import markdown
import os
import re
import sys


def convert(md_path: str, html_path: str, css_path: str, image_scale: int = 350) -> int:
    """Convert a Markdown file to styled HTML.

    Returns the size of the generated HTML file in bytes.
    """
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Scale images for PDF rendering
    md_text = md_text.replace('height="300"', f'height="{image_scale}"')

    html_body = markdown.markdown(
        md_text, extensions=["tables", "md_in_html", "fenced_code"]
    )

    # Convert fenced mermaid code blocks to Mermaid-compatible divs
    html_body = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        r'<pre class="mermaid">\1</pre>',
        html_body,
        flags=re.DOTALL,
    )

    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Add Mermaid script if mermaid blocks are present
    mermaid_script = ""
    if '<pre class="mermaid">' in html_body:
        mermaid_script = (
            '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>'
            "<script>mermaid.initialize({startOnLoad:true});</script>"
        )

    html = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><style>"
        + css
        + "</style>"
        + mermaid_script
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
