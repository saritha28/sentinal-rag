# ADR-0002: Python tooling — uv + ruff + pyright + pre-commit

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** tooling, python, dx

## Context

A 2026 Python codebase has three legitimate toolchain choices:

- **Package management:** pip, poetry, pdm, rye, **uv**
- **Linter/formatter:** flake8+black+isort, **ruff**
- **Type checker:** mypy, **pyright**, pyre

The wrong choice here doesn't break the product but signals "not current" to senior reviewers and slows every PR.

## Decision

- **uv** (Astral) for package management, virtualenvs, and workspace.
- **ruff** for linting AND formatting (replaces flake8, black, isort, pyflakes, pyupgrade, pep8-naming, several others).
- **pyright** in `strict` mode for type checking (Pylance is built on it; better incremental performance than mypy).
- **pre-commit** hooks running `ruff format`, `ruff check --fix`, `pyright`, `check-merge-conflict`, `check-yaml`, `check-toml`.
- **Python 3.12** as the floor (3.13 is too fresh in early 2026 for libraries we depend on; 3.14 — which the existing `.venv` was built with — has even worse compat).

## Consequences

### Positive

- `uv sync` is 10–100× faster than `pip install -r requirements.txt`.
- `ruff` is 10–100× faster than the flake8/black/isort stack and produces more consistent output.
- pyright's incremental mode keeps full-repo typecheck under 5 seconds.
- Tooling is the same across services (one config, applied workspace-wide).

### Negative

- Three Astral-controlled tools (uv + ruff). Vendor concentration risk if Astral changes their licensing or pricing model.
- pyright's strict mode requires careful Optional/Any handling — engineers fighting the type checker is real.
- Some libraries (older ML tooling) lack stubs; we'll need `# type: ignore[import-untyped]` annotations.

### Neutral

- Engineers used to mypy will need ~1 day to adapt to pyright's error messages.

## Alternatives considered

### Option A — Poetry + flake8 + mypy
- **Pros:** Battle-tested, well-known.
- **Cons:** Slow. Poetry's resolver is the chronic bottleneck on large dependency trees. flake8/black/isort have overlapping responsibilities and inconsistent output.
- **Rejected because:** Speed and signal both lose.

### Option B — pip + tox + black
- **Pros:** Maximally portable.
- **Cons:** Manual venv management; no lockfile semantics by default; tox is 2017-vintage tooling.
- **Rejected because:** Below the bar for a 2026 portfolio.

## Trade-off summary

| Dimension | uv+ruff+pyright | Poetry+flake8+mypy |
|---|---|---|
| Setup time | Low | Medium |
| CI duration (lint+typecheck) | <30s | 2–3 min |
| Vendor concentration | Astral controls 2 tools | Distributed |
| Recruiter signal | Strong (current) | Conventional |
| Adoption rate (2026) | High and rising | High and falling |

## References

- [uv](https://docs.astral.sh/uv/)
- [ruff](https://docs.astral.sh/ruff/)
- [pyright](https://microsoft.github.io/pyright/)
