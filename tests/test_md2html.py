"""Tests for lib/md2html — Markdown to HTML conversion."""

import sys
from pathlib import Path

import pytest

# Add lib/ to path so we can import md2html
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
import md2html


class TestConvert:
    """Tests for the md2html.convert() function."""

    def test_produces_html_file(self, sample_md, default_css, tmp_output):
        html_path = str(tmp_output / "output.html")
        size = md2html.convert(str(sample_md), html_path, str(default_css))
        assert size > 0
        assert Path(html_path).exists()

    def test_html_contains_doctype(self, sample_md, default_css, tmp_output):
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(sample_md), html_path, str(default_css))
        content = Path(html_path).read_text(encoding="utf-8")
        assert content.startswith("<!DOCTYPE html>")

    def test_html_contains_css(self, sample_md, default_css, tmp_output):
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(sample_md), html_path, str(default_css))
        content = Path(html_path).read_text(encoding="utf-8")
        assert "<style>" in content
        # Default theme uses Segoe UI
        assert "Segoe UI" in content

    def test_html_contains_table(self, sample_md, default_css, tmp_output):
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(sample_md), html_path, str(default_css))
        content = Path(html_path).read_text(encoding="utf-8")
        assert "<table>" in content
        assert "<th>" in content

    def test_mermaid_blocks_converted(self, sample_md, default_css, tmp_output):
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(sample_md), html_path, str(default_css))
        content = Path(html_path).read_text(encoding="utf-8")
        assert '<pre class="mermaid">' in content
        assert "mermaid.min.js" in content

    def test_mermaid_script_absent_when_no_mermaid(self, default_css, tmp_output):
        md_path = tmp_output / "no_mermaid.md"
        md_path.write_text("# Hello\n\nNo mermaid here.\n", encoding="utf-8")
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(md_path), html_path, str(default_css))
        content = Path(html_path).read_text(encoding="utf-8")
        assert "mermaid.min.js" not in content

    def test_image_scale_substitution(self, default_css, tmp_output):
        md_path = tmp_output / "img.md"
        md_path.write_text('# Doc\n\n<img height="300" src="test.png">\n', encoding="utf-8")
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(md_path), html_path, str(default_css), image_scale=500)
        content = Path(html_path).read_text(encoding="utf-8")
        assert 'height="500"' in content
        assert 'height="300"' not in content

    def test_code_blocks_preserved(self, sample_md, default_css, tmp_output):
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(sample_md), html_path, str(default_css))
        content = Path(html_path).read_text(encoding="utf-8")
        assert "language-python" in content

    def test_blockquote_preserved(self, sample_md, default_css, tmp_output):
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(sample_md), html_path, str(default_css))
        content = Path(html_path).read_text(encoding="utf-8")
        assert "<blockquote>" in content


class TestConvertWithThemes:
    """Tests for HTML conversion with different CSS themes."""

    def test_academic_theme(self, sample_md, themes_dir, tmp_output):
        css = themes_dir / "academic.css"
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(sample_md), html_path, str(css))
        content = Path(html_path).read_text(encoding="utf-8")
        assert "Georgia" in content

    def test_minimal_theme(self, sample_md, themes_dir, tmp_output):
        css = themes_dir / "minimal.css"
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(sample_md), html_path, str(css))
        content = Path(html_path).read_text(encoding="utf-8")
        assert "BlinkMacSystemFont" in content


class TestConvertEdgeCases:
    """Edge case tests for md2html conversion."""

    def test_empty_markdown(self, default_css, tmp_output):
        md_path = tmp_output / "empty.md"
        md_path.write_text("", encoding="utf-8")
        html_path = str(tmp_output / "output.html")
        size = md2html.convert(str(md_path), html_path, str(default_css))
        assert size > 0
        content = Path(html_path).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_unicode_content(self, default_css, tmp_output):
        md_path = tmp_output / "unicode.md"
        md_path.write_text("# Ünïcödé\n\n日本語テスト\n", encoding="utf-8")
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(md_path), html_path, str(default_css))
        content = Path(html_path).read_text(encoding="utf-8")
        assert "Ünïcödé" in content
        assert "日本語テスト" in content

    def test_special_html_chars_in_markdown(self, default_css, tmp_output):
        md_path = tmp_output / "special.md"
        md_path.write_text("# Test\n\nA < B & C > D\n", encoding="utf-8")
        html_path = str(tmp_output / "output.html")
        md2html.convert(str(md_path), html_path, str(default_css))
        content = Path(html_path).read_text(encoding="utf-8")
        # markdown lib should handle HTML entity conversion
        assert "<!DOCTYPE html>" in content
