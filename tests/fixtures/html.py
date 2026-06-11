"""Fixtures for HTML tests."""

__all__ = [
    "sample_html_bytes",
    "sample_html_minimal_bytes",
    "sample_html_latin1_bytes",
]

import io
from typing import Any

import pytest


@pytest.fixture
def sample_html_bytes() -> bytes:
    """
    Generate a minimal HTML document in memory with various elements.
    Includes headings, paragraphs, links, lists, bold/italic, and a table.
    """
    html = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Main Title</h1>
    <p>This is a <strong>bold</strong> and <em>italic</em> paragraph.</p>
    <p>Visit <a href="https://example.com">our website</a> for more info.</p>
    <ul>
        <li>First item</li>
        <li>Second item</li>
    </ul>
    <ol>
        <li>Step one</li>
        <li>Step two</li>
    </ol>
    <table>
        <tr><th>Name</th><th>Value</th></tr>
        <tr><td>A</td><td>1</td></tr>
        <tr><td>B</td><td>2</td></tr>
    </table>
    <blockquote>
        <p>A quoted paragraph</p>
    </blockquote>
    <pre><code>def hello():\n    print("world")</code></pre>
    <hr>
    <p>Final paragraph with an <img src="image.png" alt="test image"> inline.</p>
</body>
</html>"""
    return html.encode("utf-8")


@pytest.fixture
def sample_html_minimal_bytes() -> bytes:
    """Generate a minimal HTML document with just a heading and paragraph."""
    html = """<!DOCTYPE html>
<html>
<body>
    <h1>Hello World</h1>
    <p>This is a simple paragraph.</p>
</body>
</html>"""
    return html.encode("utf-8")


@pytest.fixture
def sample_html_latin1_bytes() -> bytes:
    """Generate an HTML document encoded in Latin-1."""
    html = """<!DOCTYPE html>
<html>
<body>
    <h1>Document en français</h1>
    <p>Des caractères spéciaux : àéîôù</p>
</body>
</html>"""
    return html.encode("latin-1")
