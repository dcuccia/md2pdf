"""Shared pytest fixtures for md2pdf tests."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    """Path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_md(fixtures_dir):
    """Path to the sample Markdown test file."""
    return fixtures_dir / "sample.md"


@pytest.fixture
def sample_md_text(sample_md):
    """Contents of the sample Markdown test file."""
    return sample_md.read_text(encoding="utf-8")


@pytest.fixture
def themes_dir():
    """Path to the themes directory."""
    return Path(__file__).parent.parent / "themes"


@pytest.fixture
def default_css(themes_dir):
    """Path to the default CSS theme."""
    return themes_dir / "default.css"


@pytest.fixture
def tmp_output(tmp_path):
    """Temporary directory for test output files."""
    return tmp_path
