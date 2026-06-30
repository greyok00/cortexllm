# Contributing to CortexLLM

Thank you for your interest in contributing to CortexLLM!

## Development Setup

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/cortexllm.git
cd cortexllm
```

2. **Create a virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install in development mode:**
```bash
pip install -e ".[dev]"
```

## Project Structure

```
cortexllm/
├── cortexllm/
│   ├── __init__.py           # Main exports
│   ├── heartbeat_service.py  # Session heartbeat
│   ├── memory_manager.py     # Memory persistence
│   ├── anti_hallucination.py # Verification system
│   ├── loop_guard.py         # Failure loop detection
│   ├── model_router.py       # Worker delegation
│   └── mcp_server.py         # MCP server
├── tests/                    # Test suite
├── README.md
├── setup.py
└── LICENSE
```

## How to Contribute

### Reporting Bugs

- Check if the bug has already been reported
- Include Python version and OS information
- Provide minimal code to reproduce the issue
- Include error messages and stack traces

### Suggesting Features

- Open an issue describing the feature
- Explain the use case and benefits
- Be open to discussion and feedback

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `pytest`
6. Commit with clear messages
7. Push to your fork and submit a PR

## Code Style

- Follow PEP 8
- Use type hints where appropriate
- Document functions with docstrings
- Keep functions focused and small

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cortexllm

# Run specific test
pytest tests/test_heartbeat.py -v
```

## Commit Message Guidelines

- Use present tense ("Add feature" not "Added feature")
- First line is 72 characters or less
- Reference issues when applicable

Example:
```
Add support for custom worker timeouts

Implements timeout configuration for custom workers
with sensible defaults. Fixes #123
```

## Code of Conduct

Be respectful and constructive. We're all here to build something useful.

## Questions?

Open an issue or reach out to maintainers.

Thank you for contributing!
