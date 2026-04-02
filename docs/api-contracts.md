# API Contracts (Canonical)

This document is the canonical contract for the right-now happy path:

1. `POST /generate`
2. `GET /status/{job_id}`
3. frontend reveal from completed status payload

## `POST /generate`

Request:

```json
{
  "user_id": "user_123",
  "preferences": {
    "role": "warrior",
    "aesthetic": "fantasy",
    "prompt_override": "optional prompt text"
  },
  "mint_on_chain": false,
  "wallet_address": null
}
```

Response (`202`):

```json
{
  "job_id": "uuid",
  "status": "queued",
  "message": "Character generation started. Poll /status/{job_id} for updates."
}
```

## `GET /status/{job_id}`

Response (`200`):

```json
{
  "job_id": "uuid",
  "mode": "mock",
  "stage": "complete",
  "draft_urls": ["mock://draft/warrior-fantasy-0.png"],
  "selected_draft_url": "mock://draft/warrior-fantasy-0.png",
  "upscaled_url": "mock://upscaled/warrior-fantasy-0.png",
  "threedgs_url": "mock://3dgs/warrior-fantasy-0.splat",
  "audio_url": "mock://audio/warrior.wav",
  "nft_token_id": null,
  "error": null,
  "stage_durations_ms": {
    "drafting": 32,
    "evaluating": 2
  },
  "created_at_ms": 1712000000000,
  "updated_at_ms": 1712000000150
}
```

### Stage values

- `queued`
- `drafting`
- `evaluating`
- `upscaling`
- `generating_3dgs`
- `generating_audio`
- `minting`
- `complete`
- `failed`

## Character metadata contract (right now)

Right now, the frontend reveal uses status payload URLs directly plus deterministic display defaults:

- `name`: deterministic from `job_id`
- `traits`: placeholder defaults (`Warrior/Fantasy/Common`) until on-chain metadata/traits integration is complete
- `imageUrl`: `upscaled_url` (fallback `selected_draft_url`)
- `threedgsUrl`: `threedgs_url`
- `audioUrl`: `audio_url`
- `tokenId`: `nft_token_id` if present

## Asset manifest contract (right now)

The status payload doubles as the canonical asset manifest:

- Draft set: `draft_urls[]`
- Selected draft: `selected_draft_url`
- Reveal image: `upscaled_url`
- 3D asset: `threedgs_url`
- Audio: `audio_url`

`mode` tells consumers whether these are mock URIs (`mock://...`) or integration URIs (HTTP/object-store).
