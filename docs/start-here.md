# Start Here

If you are new to this repository, start with this order:

1. `README.md` for scope and current maturity
2. `docs/architecture.md` for system flow
3. `docs/api-contracts.md` for the canonical happy-path interfaces
4. `docs/system-map.md` for key files and responsibilities

## Right-now objective

Deliver one reliable happy path:

- generate character
- poll status
- reveal character
- optional mint path

Use `execution_mode=mock` for deterministic local demos and tests.

## Local checks

- AI Director:
  - `cd services/ai-director`
  - `ruff check .`
  - `mypy .`
  - `pytest -q`
- Frontend:
  - `cd frontend`
  - `npm install`
  - `npm run lint`
  - `npm run build`
  - `npm run test`
- Contracts:
  - `cd contracts`
  - `npm install`
  - `npm run lint`
  - `npm run compile`
  - `npm test`
