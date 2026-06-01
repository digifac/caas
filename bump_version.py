"""Automatically increment the patch/release number in pyproject.toml.

Version formats supported:
  - a.b.c          (e.g., 1.0.11)
  - a.b-alpha.c    (e.g., 2.5-alpha.2589)
  - a.b-beta.c     (e.g., 2.0-beta.12)

Only the release number c is auto-incremented.

After bumping, the package is reinstalled in editable mode so that
the version is synchronized everywhere (Swagger UI, CLI, metadata).

Usage:
    python bump_version.py              # Increment and reinstall package
    python bump_version.py --check      # Just print the current version
    python bump_version.py --no-reinstall  # Increment without reinstalling
"""

import re
import subprocess
import sys
from pathlib import Path


PYPROJECT_PATH = Path(__file__).parent / "pyproject.toml"

# Pattern: version = "a.b.c" or version = "a.b-alpha.c" or version = "a.b-beta.c"
# Groups: 1=prefix (version = "), 2=major.minor, 3=optional pre-release tag (-alpha/-beta), 4=release number
VERSION_PATTERN = re.compile(
    r'^(version\s*=\s*")(\d+\.\d+)(-(?:alpha|beta))?\.(\d+)"', re.MULTILINE
)


def get_current_version() -> str:
    """Read the current version from pyproject.toml."""
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(content)
    if not match:
        raise ValueError(
            f"Version not found in {PYPROJECT_PATH}. "
            "Expected format: version = \"a.b.c\" or version = \"a.b-{alpha|beta}.c\""
        )
    major_minor = match.group(2)       # "a.b"
    pre_release = match.group(3) or ""  # "-alpha", "-beta", or ""
    release_num = match.group(4)        # "c"
    return f"{major_minor}{pre_release}.{release_num}"


def bump_version() -> str:
    """Increment the release number in pyproject.toml."""
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(content)
    if not match:
        raise ValueError(
            f"Version not found in {PYPROJECT_PATH}. "
            "Expected format: version = \"a.b.c\" or version = \"a.b-{alpha|beta}.c\""
        )

    major_minor = match.group(2)       # "a.b"
    pre_release = match.group(3) or ""  # "-alpha", "-beta", or ""
    release_num = int(match.group(4))   # c
    new_release_num = release_num + 1
    new_version = f"{major_minor}{pre_release}.{new_release_num}"

    new_content = VERSION_PATTERN.sub(
        f'version = "{new_version}"', content
    )
    PYPROJECT_PATH.write_text(new_content, encoding="utf-8")
    return new_version


def reinstall_package():
    """Reinstall the package in editable mode to sync version everywhere."""
    repo_root = PYPROJECT_PATH.parent
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(repo_root)],
            check=True,
            capture_output=True,
        )
        print("✅ Package reinstalled in editable mode — version synchronized")
    except subprocess.CalledProcessError as e:
        print(
            f"⚠️  Warning: failed to reinstall package ({e.returncode}). "
            "Run 'pip install -e .' manually to sync the version.",
            file=sys.stderr,
        )
    except FileNotFoundError:
        print(
            "⚠️  Warning: Python executable not found for reinstall. "
            "Run 'pip install -e .' manually to sync the version.",
            file=sys.stderr,
        )


def main():
    if "--check" in sys.argv:
        version = get_current_version()
        print(f"Current version: {version}")
        return

    no_reinstall = "--no-reinstall" in sys.argv

    try:
        old_version = get_current_version()
        new_version = bump_version()
        print(f"Version bumped: {old_version} → {new_version}")

        if not no_reinstall:
            reinstall_package()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
