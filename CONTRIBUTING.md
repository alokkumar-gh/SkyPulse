# Contributing to SkyPulse

Thank you for your interest in contributing to **SkyPulse — National Weather Big Data Analytics Platform for India**! We welcome contributions from developers, meteorological researchers, data engineers, and UI/UX designers.

---

## Code of Conduct

All contributors and maintainers are expected to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please report unacceptable behavior according to the instructions in that document.

---

## Development Workflow

### 1. Fork & Clone
```bash
git clone https://github.com/alokkumar-gh/SkyPulse.git
cd SkyPulse
```

### 2. Branch Naming Conventions
- `feature/<feature-name>`: New capabilities (e.g., `feature/imd-radar-connector`)
- `fix/<bug-name>`: Bug fixes (e.g., `fix/map-filter-latency`)
- `docs/<doc-topic>`: Documentation enhancements
- `refactor/<scope>`: Code cleanup or refactoring without behavior change
- `perf/<scope>`: Performance optimizations

### 3. Local Setup
Follow the step-by-step guides in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md):
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, SQLite/PostgreSQL
- **Frontend**: Node.js 18+, React 18, TypeScript, Vite

### 4. Code Standards
- **Python**: Follow PEP 8 guidelines. Type annotations are mandatory for all public functions and models. Use `ruff` or `flake8` for linting.
- **TypeScript/React**: Use functional components with strict TypeScript interfaces. Follow the design system tokens in `frontend/src/index.css`.
- **Commit Messages**: Use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`).

---

## Testing Requirements

Before opening a pull request:
1. **Frontend Tests**: Ensure all Vitest unit tests pass:
   ```bash
   cd frontend
   npm test
   ```
2. **Frontend Build**: Verify there are no TypeScript compile errors or bundle breaks:
   ```bash
   npm run build
   ```
3. **Backend Tests**: Run pytest test suites:
   ```bash
   pytest tests/
   ```

---

## Pull Request Guidelines

1. Ensure your branch is rebased on the latest `main`.
2. Provide a clear description of the problem solved and test steps taken.
3. Link relevant issues or discussions.
4. Keep pull requests focused on a single logical change.
5. Update or add corresponding documentation in `docs/` if modifying APIs, models, or data pipelines.

---

## Reporting Issues

When filing a bug report or feature request:
- Provide a clear and descriptive title.
- Include reproduction steps, environment details (OS, Node version, Python version), and log snippets where relevant.
- State whether the issue affects the frontend interface, backend ingestion, database, or specific connectors.
