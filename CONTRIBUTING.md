# Contributing to PyCron

Thank you for your interest in contributing to PyCron!

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pycron.git
cd pycron
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install development dependencies:
```bash
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

With coverage:
```bash
pytest --cov=pycron --cov-report=html
```

## Code Style

We use `black` for formatting and `ruff` for linting:

```bash
black src/ tests/
ruff check src/ tests/
```

Type checking with mypy:
```bash
mypy src/
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and ensure they pass
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Reporting Issues

Please use GitHub Issues to report bugs or request features. Include:

- Python version
- Operating system
- Steps to reproduce
- Expected behavior
- Actual behavior

## Code of Conduct

Be respectful and constructive in all interactions.
