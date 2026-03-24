

#### Generate Requirements File

Make pyproject.toml the source of truth
Ditch requirements.txt entirely and generate it from pyproject.toml when needed:

    pip install pip-tools uv

    uv pip compile pyproject.toml -o requirements.txt
    uv pip compile pyproject.toml --extra dev -o requirements-dev.txt


#### Linting & Formatting

    # Install dev dependencies
    pip install -e ".[dev]"
    
    # Format with Black
    black .
    
    # Sort imports
    isort .
    
    # Lint and auto-fix with Ruff
    ruff check . --fix
    
    # Format with Ruff (alternative to Black, if you prefer one tool)
    ruff format .
    
    # Run tests
    pytest
