"""Tests for md2svg — chart scanning and SVG generation."""

import sys
from pathlib import Path

import pytest

# Add lib/ to path so we can import md2svg
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
import md2svg


# ═══════════════════════════════════════════════════════════════════════
# scan_charts
# ═══════════════════════════════════════════════════════════════════════


class TestScanCharts:
    """Tests for the Markdown @chart block scanner."""

    def test_finds_yaml_chart_blocks(self, sample_md_text):
        specs = md2svg.scan_charts(sample_md_text)
        filenames = [s["_filename"] for s in specs]
        assert "test-bar.svg" in filenames
        assert "test-hbar.svg" in filenames
        assert "test-pie.svg" in filenames
        assert "test-donut.svg" in filenames
        assert "test-sunburst.svg" in filenames

    def test_finds_pipe_table_chart(self, sample_md_text):
        specs = md2svg.scan_charts(sample_md_text)
        filenames = [s["_filename"] for s in specs]
        assert "test-pipe.svg" in filenames

    def test_total_chart_count(self, sample_md_text):
        specs = md2svg.scan_charts(sample_md_text)
        assert len(specs) == 6

    def test_chart_types_parsed_correctly(self, sample_md_text):
        specs = md2svg.scan_charts(sample_md_text)
        types = {s["_filename"]: s.get("type", "bar") for s in specs}
        assert types["test-bar.svg"] == "bar"
        assert types["test-hbar.svg"] == "hbar"
        assert types["test-pie.svg"] == "pie"
        assert types["test-donut.svg"] == "donut"
        assert types["test-sunburst.svg"] == "sunburst"
        assert types["test-pipe.svg"] == "hbar"

    def test_chart_data_parsed(self, sample_md_text):
        specs = md2svg.scan_charts(sample_md_text)
        bar_spec = next(s for s in specs if s["_filename"] == "test-bar.svg")
        assert bar_spec["data"]["Alpha"] == 40
        assert bar_spec["data"]["Beta"] == 30

    def test_no_charts_in_plain_markdown(self):
        md = "# Hello\n\nJust some text.\n"
        specs = md2svg.scan_charts(md)
        assert specs == []

    def test_ignores_nested_code_fences(self):
        """Chart blocks inside 4+ backtick fences should be ignored."""
        md = '````\n```yaml\n# @chart → fake.svg\ntype: bar\ndata:\n  X: 1\n```\n````\n'
        specs = md2svg.scan_charts(md)
        assert len(specs) == 0

    def test_sunburst_nested_data(self, sample_md_text):
        specs = md2svg.scan_charts(sample_md_text)
        sb = next(s for s in specs if s["_filename"] == "test-sunburst.svg")
        assert isinstance(sb["data"]["Group A"], dict)
        assert sb["data"]["Group A"]["Sub 1"] == 30


# ═══════════════════════════════════════════════════════════════════════
# _parse_pipe_table
# ═══════════════════════════════════════════════════════════════════════


class TestParsePipeTable:
    """Tests for pipe table parsing."""

    def test_basic_table(self):
        table = "| Name | Value |\n|------|-------|\n| Foo | 10 |\n| Bar | 20 |\n"
        result = md2svg._parse_pipe_table(table)
        assert result == {"Foo": 10.0, "Bar": 20.0}

    def test_empty_table(self):
        table = "| Name | Value |\n|------|-------|\n"
        result = md2svg._parse_pipe_table(table)
        assert result == {}

    def test_non_numeric_values_skipped(self):
        table = "| Name | Value |\n|------|-------|\n| Foo | abc |\n| Bar | 20 |\n"
        result = md2svg._parse_pipe_table(table)
        assert result == {"Bar": 20.0}

    def test_float_values(self):
        table = "| Name | Value |\n|------|-------|\n| Pi | 3.14 |\n"
        result = md2svg._parse_pipe_table(table)
        assert result == {"Pi": 3.14}

    def test_too_few_lines(self):
        table = "| Name | Value |\n"
        result = md2svg._parse_pipe_table(table)
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════
# Chart Generators
# ═══════════════════════════════════════════════════════════════════════


class TestGenerateBar:
    """Tests for vertical bar chart generation."""

    def test_produces_valid_svg(self):
        spec = {"title": "Test", "data": {"A": 10, "B": 20}}
        svg = md2svg.generate_bar(spec)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert "xmlns" in svg

    def test_contains_title(self):
        spec = {"title": "My Title", "data": {"A": 10}}
        svg = md2svg.generate_bar(spec)
        assert "My Title" in svg

    def test_contains_all_labels(self):
        spec = {"title": "", "data": {"Alpha": 10, "Beta": 20, "Gamma": 30}}
        svg = md2svg.generate_bar(spec)
        assert "Alpha" in svg
        assert "Beta" in svg
        assert "Gamma" in svg

    def test_empty_data_returns_empty(self):
        spec = {"title": "Empty", "data": {}}
        svg = md2svg.generate_bar(spec)
        assert svg == ""

    def test_escapes_special_characters(self):
        spec = {"title": "A & B", "data": {"<val>": 10}}
        svg = md2svg.generate_bar(spec)
        assert "&amp;" in svg
        assert "&lt;val&gt;" in svg


class TestGenerateHBar:
    """Tests for horizontal bar chart generation."""

    def test_produces_valid_svg(self):
        spec = {"title": "Test", "data": {"A": 10, "B": 20}}
        svg = md2svg.generate_hbar(spec)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")

    def test_contains_labels_and_values(self):
        spec = {"title": "", "data": {"Foo": 50, "Bar": 30}}
        svg = md2svg.generate_hbar(spec)
        assert "Foo" in svg
        assert "Bar" in svg
        assert "50" in svg
        assert "30" in svg

    def test_empty_data_returns_empty(self):
        spec = {"title": "", "data": {}}
        assert md2svg.generate_hbar(spec) == ""


class TestGeneratePie:
    """Tests for pie/donut chart generation."""

    def test_produces_valid_svg(self):
        spec = {"title": "Test", "data": {"A": 60, "B": 40}}
        svg = md2svg.generate_pie(spec)
        assert svg.startswith("<svg")
        assert "<path" in svg

    def test_donut_mode(self):
        spec = {"title": "Test", "data": {"A": 60, "B": 40}, "donut": True}
        svg = md2svg.generate_pie(spec)
        assert svg.startswith("<svg")

    def test_legend_includes_labels(self):
        spec = {"title": "", "data": {"Slice A": 50, "Slice B": 50}}
        svg = md2svg.generate_pie(spec)
        assert "Slice A" in svg
        assert "Slice B" in svg

    def test_empty_data_returns_empty(self):
        spec = {"title": "", "data": {}}
        assert md2svg.generate_pie(spec) == ""


class TestGenerateSunburst:
    """Tests for sunburst chart generation."""

    def test_produces_valid_svg(self):
        spec = {
            "title": "Test",
            "data": {"Group": {"Sub1": 10, "Sub2": 20}},
        }
        svg = md2svg.generate_sunburst(spec)
        assert svg.startswith("<svg")
        assert "<path" in svg

    def test_contains_labels(self):
        spec = {
            "title": "Nested",
            "data": {"Outer": {"Inner1": 30, "Inner2": 20}},
        }
        svg = md2svg.generate_sunburst(spec)
        assert "Outer" in svg

    def test_empty_data_returns_empty(self):
        spec = {"title": "", "data": {}}
        assert md2svg.generate_sunburst(spec) == ""


# ═══════════════════════════════════════════════════════════════════════
# Chart Dispatcher
# ═══════════════════════════════════════════════════════════════════════


class TestChartDispatcher:
    """Tests for the CHART_GENERATORS dispatch table."""

    def test_all_types_registered(self):
        expected = {"bar", "hbar", "pie", "donut", "sunburst"}
        assert set(md2svg.CHART_GENERATORS.keys()) == expected

    def test_donut_delegates_to_pie(self):
        spec = {"title": "Donut", "data": {"A": 60, "B": 40}}
        svg = md2svg.CHART_GENERATORS["donut"](spec)
        assert svg.startswith("<svg")


# ═══════════════════════════════════════════════════════════════════════
# generate_charts (integration)
# ═══════════════════════════════════════════════════════════════════════


class TestGenerateCharts:
    """Integration tests for full chart generation from a Markdown file."""

    def test_generates_all_svg_files(self, sample_md, tmp_output):
        import shutil

        # Copy fixture to temp dir so SVGs are written there
        dest = tmp_output / "sample.md"
        shutil.copy(sample_md, dest)
        results = md2svg.generate_charts(dest)
        assert len(results) == 6
        for name in results:
            assert (tmp_output / name).exists()
            content = (tmp_output / name).read_text(encoding="utf-8")
            assert content.startswith("<svg")

    def test_list_only_does_not_create_files(self, sample_md, tmp_output):
        import shutil

        dest = tmp_output / "sample.md"
        shutil.copy(sample_md, dest)
        results = md2svg.generate_charts(dest, list_only=True)
        assert len(results) == 6
        for name in results:
            assert not (tmp_output / name).exists()


# ═══════════════════════════════════════════════════════════════════════
# SVG Primitives
# ═══════════════════════════════════════════════════════════════════════


class TestSvgPrimitives:
    """Tests for low-level SVG helper functions."""

    def test_esc_ampersand(self):
        assert md2svg._esc("A & B") == "A &amp; B"

    def test_esc_angle_brackets(self):
        assert md2svg._esc("<tag>") == "&lt;tag&gt;"

    def test_esc_quotes(self):
        assert md2svg._esc('"hello"') == "&quot;hello&quot;"

    def test_polar_to_cart_north(self):
        x, y = md2svg._polar_to_cart(100, 100, 50, 0)
        assert abs(x - 100) < 0.1
        assert abs(y - 50) < 0.1  # 50 units up from center

    def test_polar_to_cart_east(self):
        x, y = md2svg._polar_to_cart(100, 100, 50, 90)
        assert abs(x - 150) < 0.1
        assert abs(y - 100) < 0.1
