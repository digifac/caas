"""Pytest configuration - import all fixtures from the fixtures package."""

# Importing the fixtures package makes all fixtures available to pytest.
# The fixtures are defined in tests/fixtures/common.py and format-specific modules.
from tests.fixtures import *  # noqa: F401, F403
