# System Map (Human + AI Friendly)

## Components and responsibilities

- `services/ai-director`
  - `main.py`: HTTP API and models (`/generate`, `/status/{job_id}`)
  - `agents/orchestrator.py`: pipeline state machine and stage transitions
  - `agents/image_agent.py`: image draft/upscale/3DGS generation
  - `agents/evaluator_agent.py`: draft selection
  - `agents/audio_agent.py`: soundscape generation
  - `agents/web3_agent.py`: optional mint/splits operations
  - `state_store.py`: persisted job state backing store

- `frontend`
  - `src/hooks/useCharacterMint.ts`: API orchestration and polling
  - `src/components/CharacterCreation/*`: onboarding funnel UI
  - `src/types/character.ts`: frontend domain and API response types

- `contracts`
  - `src/CharacterNFT.sol`: mint logic and pricing
  - `src/AIDirectorPaymaster.sol`: sponsored gas control path
  - `src/CharacterSplits.sol`: immutable split contracts and factory
  - `test/*.ts`: functional and deploy smoke tests

- `infrastructure`
  - `terraform/`: core cloud resources
  - `kubernetes/`: runtime manifests and scaling

## Canonical API contract location

- `docs/api-contracts.md`

## Quality gates

- CI workflow: `.github/workflows/quality-gate.yml`
- Services checks: ruff + mypy + pytest
- Frontend checks: eslint + build + vitest
- Contract checks: solhint + compile + tests
