# Mootlib

A Python library for finding similar questions across prediction markets.

## Features

- Search for similar questions across multiple prediction market platforms
- Access historical market data and probabilities
- Compare questions using semantic similarity
- Automatic caching and data management
- Direct access to market data and embeddings

## Installation

```bash
pip install mootlib
```

## Environment Setup

### Required Environment Variables

The library requires several environment variables to function:

- `MOOTLIB_ENCRYPTION_KEY`: Required for decrypting market data
- `DEEPINFRA_TOKEN`: Required for computing embeddings
- `GJO_EMAIL` and `GJO_PASSWORD`: Optional, for Good Judgment Open access

You can set these up in two ways:

#### 1. Using a .env file (recommended for local development)

Create a `.env` file in your project root:

```bash
MOOTLIB_ENCRYPTION_KEY="your-key-here"
DEEPINFRA_TOKEN="your-token-here"
GJO_EMAIL="your-email@example.com"  # Optional
GJO_PASSWORD="your-password"        # Optional
```

Then in your Python code:
```python
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env

from mootlib import MootlibMatcher
matcher = MootlibMatcher()
```

#### 2. Setting environment variables directly

```bash
# Unix/macOS
export MOOTLIB_ENCRYPTION_KEY="your-key-here"
export DEEPINFRA_TOKEN="your-token-here"

# Windows PowerShell
$env:MOOTLIB_ENCRYPTION_KEY="your-key-here"
$env:DEEPINFRA_TOKEN="your-token-here"
```

#### 3. For GitHub Actions

Add these secrets in your repository's Settings → Secrets and Variables → Actions:

- `MOOTLIB_ENCRYPTION_KEY`
- `DEEPINFRA_TOKEN`
- `GJO_EMAIL` (optional)
- `GJO_PASSWORD` (optional)

Then use them in your workflow:
```yaml
env:
  MOOTLIB_ENCRYPTION_KEY: ${{ secrets.MOOTLIB_ENCRYPTION_KEY }}
  DEEPINFRA_TOKEN: ${{ secrets.DEEPINFRA_TOKEN }}
```

## Quick Start

```python
from mootlib import MootlibMatcher

# Initialize the matcher
matcher = MootlibMatcher()

# Find similar questions
similar = matcher.find_similar_questions(
    "Will Russia invade Moldova in 2024?",
    n_results=3,
    min_similarity=0.7
)

# Print the results
for question in similar:
    print(f"\n{question}")
```

## API Reference

### MootlibMatcher

The main interface for finding similar questions across prediction markets.

```python
matcher = MootlibMatcher(cache_duration_minutes=30)
```

Parameters:
- `cache_duration_minutes`: How long to keep downloaded data in cache (default: 30)

#### Properties

##### markets_df

Access the raw markets DataFrame containing all prediction market data:

```python
markets_df = matcher.markets_df
```

The DataFrame contains columns:
- `question`: The market question text
- `source_platform`: Platform where the market is from
- `formatted_outcomes`: Current probabilities/outcomes
- `url`: Link to the original market
- `n_forecasters`: Number of forecasters
- `volume`: Trading volume/liquidity
- `published_at`: Publication datetime

##### embeddings_df

Access the embeddings DataFrame containing question vectors:

```python
embeddings_df = matcher.embeddings_df
```

The DataFrame contains columns:
- `text`: The question text
- `embedding`: The numerical embedding vector

Note: Embeddings are computed on-demand and cached for future use.

#### find_similar_questions

```python
similar = matcher.find_similar_questions(
    query="Will Tesla stock reach $300 in 2024?",
    n_results=5,
    min_similarity=0.5
)
```

Parameters:
- `query`: The question to find similar matches for
- `n_results`: Number of similar questions to return (default: 5)
- `min_similarity`: Minimum similarity score 0-1 (default: 0.5)

Returns a list of `SimilarQuestion` objects with the following attributes:
- `question`: The text of the prediction market question
- `similarity_score`: How similar this question is to the query (0-1)
- `source_platform`: The platform where this question was found
- `formatted_outcomes`: String representation of possible outcomes and probabilities
- `url`: URL to the original market (optional)
- `n_forecasters`: Number of people who made predictions (optional)
- `volume`: Trading volume or liquidity (optional)
- `published_at`: When the market was published (optional)

## Examples

### Finding Similar Market Questions

```python
from mootlib import MootlibMatcher

matcher = MootlibMatcher()

# Search for AI-related questions
ai_questions = matcher.find_similar_questions(
    "Will AGI be achieved by 2025?",
    n_results=3,
    min_similarity=0.7
)

# Search for geopolitical questions
geo_questions = matcher.find_similar_questions(
    "Will China invade Taiwan in 2024?",
    n_results=3,
    min_similarity=0.7
)

# Print results
for q in ai_questions + geo_questions:
    print(f"\n{q}\n{'=' * 80}")
```

### Accessing Market Details

```python
from mootlib import MootlibMatcher

matcher = MootlibMatcher()

# Find similar questions and access their details
similar = matcher.find_similar_questions("Will SpaceX reach Mars by 2025?")

for q in similar:
    print(f"\nQuestion: {q.question}")
    print(f"Platform: {q.source_platform}")
    print(f"Current Probabilities: {q.formatted_outcomes}")
    if q.url:
        print(f"Market URL: {q.url}")
    if q.n_forecasters:
        print(f"Number of Forecasters: {q.n_forecasters}")
    print("-" * 80)
```

### Accessing Raw Data

```python
from mootlib import MootlibMatcher

matcher = MootlibMatcher()

# Get all market data
markets_df = matcher.markets_df
print(f"Total markets: {len(markets_df)}")
print("\nMarkets by platform:")
print(markets_df["source_platform"].value_counts())

# Get question embeddings
embeddings_df = matcher.embeddings_df
print(f"\nTotal questions with embeddings: {len(embeddings_df)}")

# Filter markets by platform
manifold_markets = markets_df[markets_df["source_platform"] == "Manifold"]
print(f"\nManifold markets: {len(manifold_markets)}")

# Get high-volume markets
high_volume = markets_df[markets_df["volume"] > 1000]
print(f"\nHigh volume markets: {len(high_volume)}")
```

## Development

### Local Setup

1. Clone the repository
```bash
git clone https://github.com/vigji/mootlib.git
cd mootlib
```

2. Install dependencies with uv
```bash
pip install uv
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows
uv pip install -e ".[dev]"
```

### Code Quality

We use [Ruff](https://github.com/astral-sh/ruff) for all Python linting and formatting:

```bash
# Format code
ruff format .

# Run linter
ruff check .

# Run linter with automatic fixes
ruff check --fix .
```

### Repository Maintenance

#### Versioning and Releases

We use Git tags for versioning. The version number is automatically derived from the latest tag using `hatch-vcs`.

To create a new release, you have two options:

1. **Quick Release (via Git tag)**:
```bash
# Create and push a new version tag (e.g., v0.1.1)
git tag -a v0.1.1 -m "Description of changes"
git push origin v0.1.1
```
This will automatically trigger the release workflow.

2. **Full Release (via GitHub UI)**:
   - Create and push a tag as above
   - Go to GitHub -> Releases -> Create a new release
   - Choose the tag you just pushed
   - Add detailed release notes
   - Click "Publish release"

In both cases, the release workflow will automatically:
   - Run all tests
   - If tests pass, build the package
   - Publish to PyPI using trusted publishing

Note: Using the GitHub UI method allows you to add more detailed release notes and attachments, but both methods will publish to PyPI.

#### Pre-commit Hooks

We use pre-commit hooks to ensure code quality. Install them with:

```bash
pre-commit install
```

This will automatically run Ruff and other checks before each commit.

### Code Style Guidelines

- Maximum line length: 88 characters (enforced by Ruff)
- Use pathlib over os.path
- Use functions only where you see opportunity for code reuse
- Use classes sparingly and when it makes sense over functions
- Use loops to streamline operations repeated more than once
- Document briefly middle-length functions, fully annotate only complex ones

### Running Tests

```bash
pytest
```

### Type Checking

```bash
mypy mootlib tests
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
