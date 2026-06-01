# Contributing to CAAS

Thank you for your interest in contributing to **CAAS** (Conversion-as-a-Service)! This document will help you get started.

---

## 📋 Table of Contents

- [Code of Conduct](#-code-of-conduct)
- [Getting Started](#-getting-started)
- [Development Setup](#-development-setup)
- [Running Tests](#-running-tests)
- [Pull Request Process](#-pull-request-process)
- [Coding Guidelines](#-coding-guidelines)
- [Reporting Bugs](#-reporting-bugs)
- [Requesting Features](#-requesting-features)

---

## 🤝 Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code.

---

## 🚀 Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/caas.git
   cd caas
   ```
3. **Add** the upstream remote:
   ```bash
   git remote add upstream https://github.com/digifac/caas.git
   ```

---

## 🛠️ Development Setup

### Prerequisites

- **Python 3.12+**
- **pip** (bundled with Python)
- **Tesseract OCR** (optional, for scanned PDF support)
  - Windows: [tesseract-ocr.github.io](https://github.com/tesseract-ocr/tesseract/wiki)
  - Ubuntu/Debian: `sudo apt install tesseract-ocr`
  - macOS: `brew install tesseract`

### Virtual environment

```bash
python -m venv .venv
.venv/Scripts/Activate.ps1   # PowerShell (Windows)
# .venv/bin/activate          # Linux / macOS
```

### Install dependencies

```bash
# Install production and development dependencies
pip install -e ".[dev]"
```

### Configuration

Copy the example environment file and adjust as needed:

```bash
copy .env.example .env    # Windows
# cp .env.example .env    # Linux / macOS
```

All configuration variables are prefixed with `CAAS_`. See `.env.example` for available options and defaults.

---

## 🧪 Running Tests

### Run all tests

```bash
pytest tests/ -v
```

### Run with coverage

```bash
pytest tests/ -v --cov=app --cov-report=html
```

The coverage report will be generated in `htmlcov/`.

### Run a specific test file

```bash
pytest tests/test_validation.py -v
```

---

## 📝 Pull Request Process

1. **Sync** your fork with the latest `main` branch:

   ```bash
   git fetch upstream
   git checkout main
   git merge upstream/main
   ```

2. **Create a feature branch**:

   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes** and commit with clear, descriptive messages:

   ```bash
   git commit -m "feat: add support for XYZ format"
   ```

4. **Push** your branch:

   ```bash
   git push origin feature/your-feature-name
   ```

5. **Open a Pull Request** on GitHub against the `main` branch.

### PR Guidelines

- Keep PRs focused and small when possible.
- Include tests for new features or bug fixes.
- Ensure all tests pass before requesting a review.
- Update documentation if your change affects the user-facing API or behavior.
- Reference related issues in the PR description (e.g., `Closes #123`).

---

## 💻 Coding Guidelines

- **Python**: Follow [PEP 8](https://peps.python.org/pep-0008/).
- **Type hints**: Use type annotations where applicable.
- **Docstrings**: Write docstrings for public functions, classes, and modules.
- **Line length**: Keep lines under 88 characters (Black default).
- **Imports**: Group standard library, third-party, and local imports with blank lines between groups.

### Formatters and linters

The project uses **ruff** (linter + formatter) and **mypy** (type checking), enforced via **pre-commit** hooks.

#### Manual usage

```bash
# Format code
ruff format app/ tests/

# Lint code (with auto-fix)
ruff check --fix app/ tests/

# Type checking
mypy app/
```

#### Pre-commit hooks (recommended)

```bash
# Install hooks once
pre-commit install

# Run on all files
pre-commit run --all-files
```

Hooks will run automatically on `git commit`.

---

## 🐛 Reporting Bugs

1. Search existing issues to avoid duplicates.
2. Open a new issue with the **Bug** label.
3. Include:
   - A clear title and description.
   - Steps to reproduce the issue.
   - Expected vs. actual behavior.
   - Python version and OS.
   - Relevant logs or error traces.

---

## 💡 Requesting Features

1. Search existing issues to check if the feature was already discussed.
2. Open a new issue with the **Enhancement** label.
3. Describe the use case and expected behavior.

---

## 📚 Resources

- [README.md](README.md) — Project overview and usage
- [TODO.md](TODO.md) — Current roadmap and release checklist
- [LICENSE](LICENSE) — MIT License

---

Thank you for contributing to CAAS! 🎉
