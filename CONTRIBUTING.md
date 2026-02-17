# Contributing to Contactly

Thank you for considering contributing to Contactly! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow. Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before contributing.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the behavior
- **Expected behavior** vs what actually happened
- **Environment details**: OS, Python version, deployment method (Docker/native)
- **Logs and error messages** if applicable
- **Configuration** (sanitized, without credentials)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- Use a **clear and descriptive title**
- Provide a **detailed description** of the proposed functionality
- Explain **why this enhancement would be useful**
- List any **alternative solutions** you've considered

### Your First Code Contribution

Unsure where to begin? Look for issues tagged with:

- `good first issue` - Simple issues for newcomers
- `help wanted` - Issues where we need community help
- `documentation` - Documentation improvements

### Pull Requests

- Fill in the pull request template
- Follow the coding standards
- Include tests for new functionality
- Update documentation as needed
- Ensure all tests pass

## Development Setup

### Prerequisites

- Python 3.9 or higher
- MySQL/MariaDB (or use Docker)
- Google OAuth credentials (for testing Google sync)
- iCloud credentials (for testing iCloud sync)

### Local Development Setup

1. **Clone the repository**

```bash
git clone https://github.com/aayusharyan/contactly.git
cd contactly
```

2. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Set up environment variables**

```bash
cp .env.example .env
# Edit .env with your credentials
```

5. **Run tests**

```bash
python -m pytest tests/
```

See [SETUP.md](SETUP.md) for detailed development setup instructions.

### Docker Development

```bash
docker-compose up -d
docker-compose logs -f
```

## Pull Request Process

1. **Fork the repository** and create your branch from `main`

```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes**
   - Follow coding standards
   - Add tests for new functionality
   - Update documentation

3. **Test your changes**

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_normalizer.py

# Run with coverage
python -m pytest --cov=src tests/
```

4. **Commit your changes**

Use clear, descriptive commit messages:

```bash
git commit -m "Add support for custom phone number regions"
```

Good commit message format:
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and PRs when relevant

5. **Push to your fork**

```bash
git push origin feature/your-feature-name
```

6. **Open a Pull Request**

- Fill in the PR template completely
- Link to any related issues
- Request review from maintainers

### PR Review Process

- Maintainers will review your PR within a few days
- Address any requested changes
- Once approved, a maintainer will merge your PR

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length**: 100 characters (not 79)
- **Indentation**: 4 spaces
- **Imports**: Organized in three groups (standard library, third-party, local)
- **Naming conventions**:
  - Classes: `PascalCase`
  - Functions/methods: `snake_case`
  - Constants: `UPPER_CASE`
  - Private methods: `_leading_underscore`

### Code Organization

```python
# Standard library imports
import os
from datetime import datetime

# Third-party imports
from sqlalchemy import create_engine
import phonenumbers

# Local imports
from src.normalize.normalizer import ContactNormalizer
```

### Documentation Standards

- **Module docstrings**: High-level overview at the top of each file
- **Function docstrings**: Explain purpose, parameters, return values, and exceptions
- **Inline comments**: For complex logic, not obvious code
- **Maximum comment length**: 5 lines, ideally 2-3
- **No section dividers**: Avoid `-----` or `========` in comments

Example:

```python
def normalize_phone_number(phone: str, region: str = "US") -> str:
    """
    Converts a phone number to E.164 format.

    Args:
        phone: Raw phone number string
        region: ISO country code for parsing (default: US)

    Returns:
        E.164 formatted phone number (e.g., +14155552671)

    Raises:
        NumberParseException: If phone number cannot be parsed
    """
    # Complex logic here deserves a comment
    parsed = phonenumbers.parse(phone, region)
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
```

### Type Hints

Use type hints for all function signatures:

```python
from typing import List, Dict, Optional

def merge_contacts(contacts: List[Dict], strategy: str = "latest") -> Dict:
    pass
```

### Error Handling

- Use specific exceptions, not bare `except:`
- Log errors with appropriate severity
- Include context in error messages

```python
try:
    result = api_call()
except requests.HTTPError as e:
    logger.error(f"API call failed: {e}")
    raise
```

## Testing

### Test Structure

- Tests are located in `tests/` directory
- Mirror the `src/` directory structure
- Name test files `test_<module>.py`

### Writing Tests

- Use descriptive test names: `test_normalize_phone_number_with_country_code`
- Test happy path, edge cases, and error conditions
- Use fixtures for common setup
- Mock external services (Google API, iCloud)

Example:

```python
def test_normalize_phone_number_with_us_format():
    """Test that US phone numbers are normalized to E.164 format"""
    normalizer = ContactNormalizer()
    result = normalizer.normalize_phone("+1 (415) 555-2671")
    assert result == "+14155552671"
```

### Test Coverage

- Aim for at least 80% code coverage
- Critical paths (phone normalization, merging) should have 95%+ coverage
- Check coverage with: `pytest --cov=src tests/`

## Documentation

### When to Update Documentation

Update documentation when you:

- Add new features or functionality
- Change existing behavior
- Fix bugs that affect documented behavior
- Add new configuration options

### Documentation Files

- **README.md**: High-level overview and quick start
- **ARCHITECTURE.md**: Technical design and internals
- **GETTING_STARTED.md**: Detailed setup instructions
- **DEPLOY.md**: Production deployment guide
- **TESTING.md**: Testing procedures and validation
- **GOOGLE_OAUTH_SETUP.md**: Google OAuth configuration

### Documentation Style

- Use clear, concise language
- Include code examples where helpful
- Use proper markdown formatting
- Test all commands and code snippets

## Questions?

If you have questions about contributing:

- Open an issue with the `question` label
- Check existing issues and discussions
- Contact the maintainer: [@aayusharyan](https://github.com/aayusharyan)

## Recognition

Contributors will be recognized in:

- GitHub contributors page
- Release notes for significant contributions
- The project README (for major features)

Thank you for contributing to Contactly!
