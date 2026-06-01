"""Tests for utility functions (non-HTTP)."""

from unittest.mock import patch

from app.config import settings
from app.converter import _clean_lines, get_html_form


class TestCleanLines:
    """Tests for the _clean_lines function."""

    def test_removes_empty_lines(self):
        result = _clean_lines(["hello", "", "world", "  "])
        assert result == ["hello", "world"]

    def test_strips_whitespace(self):
        result = _clean_lines(["  hello  ", "  world  "])
        assert result == ["hello", "world"]

    def test_detects_numbered_heading(self):
        result = _clean_lines(["1. Introduction"])
        assert result == ["# 1. Introduction"]

    def test_detects_numbered_heading_parenthesis(self):
        result = _clean_lines(["1) Introduction"])
        assert result == ["# 1) Introduction"]

    def test_detects_markdown_heading(self):
        result = _clean_lines(["## Titre"])
        assert result == ["# ## Titre"]

    def test_detects_all_caps_heading(self):
        with patch.object(settings, "markdown_heading_detection", True):
            result = _clean_lines(["INTRODUCTION"])
            assert result == ["# INTRODUCTION"]

    def test_all_caps_disabled(self):
        with patch.object(settings, "markdown_heading_detection", False):
            result = _clean_lines(["INTRODUCTION"])
            assert result == ["INTRODUCTION"]

    def test_all_caps_with_punctuation_not_heading(self):
        """Text with punctuation should NOT be detected as a heading."""
        with patch.object(settings, "markdown_heading_detection", True):
            result = _clean_lines(["ATTENTION: LIRE AVANT D'UTILISER"])
            assert result == ["ATTENTION: LIRE AVANT D'UTILISER"]

    def test_all_caps_with_digits_not_heading(self):
        """Text with digits should NOT be detected as a heading."""
        with patch.object(settings, "markdown_heading_detection", True):
            result = _clean_lines(["VERSION 2.0"])
            assert result == ["VERSION 2.0"]

    def test_all_caps_too_long_not_heading(self):
        """Lines longer than 40 chars should NOT be detected as headings."""
        with patch.object(settings, "markdown_heading_detection", True):
            long_line = "CETTE LIGNE EST TROP LONGUE POUR ÊTRE UN TITRE"
            result = _clean_lines([long_line])
            assert result == [long_line]

    def test_all_caps_mixed_case_not_heading(self):
        """Mixed case should NOT be detected as a heading."""
        with patch.object(settings, "markdown_heading_detection", True):
            result = _clean_lines(["Introduction"])
            assert result == ["Introduction"]

    def test_preserves_bullet_list(self):
        result = _clean_lines(["* item 1", "- item 2", "• item 3"])
        assert result == ["* item 1", "- item 2", "• item 3"]

    def test_preserves_normal_text(self):
        result = _clean_lines(["Ceci est un paragraphe normal."])
        assert result == ["Ceci est un paragraphe normal."]

    def test_mixed_content(self):
        with patch.object(settings, "markdown_heading_detection", True):
            lines = [
                "INTRODUCTION",
                "",
                "* point A",
                "* point B",
                "Détails du contenu.",
            ]
            result = _clean_lines(lines)
            assert "# INTRODUCTION" in result
            assert "* point A" in result
            assert "Détails du contenu." in result
            assert "" not in result

    def test_empty_input(self):
        result = _clean_lines([])
        assert result == []

    def test_only_whitespace_lines(self):
        result = _clean_lines(["", "  ", "\t"])
        assert result == []


class TestGetHtmlForm:
    """Tests for the get_html_form function."""

    def test_returns_string(self):
        html = get_html_form()
        assert isinstance(html, str)

    def test_contains_doctype(self):
        html = get_html_form()
        assert "<!DOCTYPE html>" in html

    def test_contains_title(self):
        html = get_html_form()
        assert "CAAS" in html

    def test_contains_form_elements(self):
        html = get_html_form()
        assert "<form" in html or "upload" in html.lower() or "input" in html
