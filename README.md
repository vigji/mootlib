# mootlib

A library for scraping and analyzing forecasting markets.

## Requirements

- Python 3.12 or higher
- uv (for dependency management)

## Installation

### Using pip

```bash
pip install mootlib
```

### From source

1. Clone the repository
```bash
git clone https://github.com/yourusername/mootlib.git
cd mootlib
```

2. Install uv if you haven't already:
```bash
pip install uv
```

3. Create virtual environment and install dependencies:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows

uv pip install -e ".[dev]"  # Install with development dependencies
```

The virtual environment will be created in the `.venv` directory inside your project.

## Development

This project uses uv for fast, reliable dependency management. All dependencies are managed in a local virtual environment within the project directory.

### Setup

1. Install uv if you haven't already:
```bash
pip install uv
```

2. Create virtual environment and install dependencies:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows

uv pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Quality

We use several tools to maintain code quality:

- Black for code formatting:
```bash
black .
```

- isort for import sorting:
```bash
isort .
```

- Flake8 for style guide enforcement:
```bash
flake8 .
```

- MyPy for type checking:
```bash
mypy mootlib tests
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
