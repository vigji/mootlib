# mootlib

A library for scraping and analyzing forecasting markets.

## Requirements

- Python 3.11 or higher
- uv (for dependency management)

## Installation

### Local Development Installation

1. Clone the repository
```bash
git clone https://github.com/vigji/mootlib.git
cd mootlib
```

2. Install uv if you haven't already:
```bash
pip install uv
```

3. Create and activate a virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows
```

4. Install the package in editable mode with development dependencies:
```bash
uv pip install -e ".[dev]"
```

The virtual environment will be created in the `.venv` directory inside your project.

### Using pip (once published)

```bash
pip install mootlib
```

## Development

This project uses modern Python tooling for development:

- Ruff for formatting and linting (includes functionality from black, isort, flake8, and many other tools)
- MyPy for type checking
- Pytest for testing

### Running Tests

```bash
pytest
```

### Code Quality

We use Ruff as an all-in-one solution for code quality:

- Format code:
```bash
ruff format .
```

- Lint code (includes many checks like imports, style, complexity, etc.):
```bash
ruff check .
```

- Type checking with MyPy:
```bash
mypy mootlib tests
```

### Code Style

This project follows these code style guidelines:
- Maximum line length of 88 characters (enforced by Ruff)
- Double quotes for strings
- Type hints for all functions
- Google-style docstrings for complex functions
- Automatic import sorting with Ruff
- Strict linting rules enforced by Ruff
- Pathlib preferred over os.path for file operations
- Loops preferred over repeated operations
- Classes used sparingly and only for complex data structures

## License

This project is licensed under the MIT License - see the LICENSE file for details.
