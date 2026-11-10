# engine

The Living World Engine: a game made only of small neural networks, one family per part of the game, joined by types. The design is in [`docs/engine/`](../docs/engine/README.md).

This directory is self-contained. It shares nothing with the asset pipeline in the rest of the repository.

## What is here: stage 1, "types and a full tick"

Stage 1 of the [build order](../docs/engine/architecture.md#build-order) proves that the parts compose and the types hold, before any network is trained.

- **The types** (`src/schema.ts`). Every value that passes between networks, written once as a TypeGPU schema, with a fingerprint per type.
- **The three last layers** (`src/kinds.ts`). Choice, Move and Bounded: the steps that make an illegal output impossible.
- **Ten stand-in networks** (`src/parts/`), covering all five parts: perception, mind, speech and body for characters; contact, impulse and step for physics; outcome for mechanics; director for plot; light for the world.
- **The tick** (`src/tick.ts`). All seven phases in order, with the commit (`src/commit.ts`) applying moves by whole-number arithmetic.
- **Counted randomness** (`src/rng.ts`) and **the recorder** (`src/recorder.ts`), which keeps the last 600 ticks of every connection and can replay any network against them.
- **A demo page** (`index.html`, `src/main.ts`) that runs the tick and checks that every network compiles on the GPU.

Each network is one TypeScript function. The same source runs as plain JavaScript in the tests and compiles to shader code (WGSL) for the GPU.

## What is not here yet

- **Trained networks.** Every network is a tiny stand-in with seeded random weights. Nothing behaves sensibly. What does hold, and is tested, is that every output is legal: counts never go negative, no beat plays unless its conditions hold, nothing sinks through the floor, physics never adds energy.
- **Running on the GPU.** The tick runs on the CPU. The GPU is only asked to compile the networks. Dispatching them over state buffers is the next step.
- **Networks with no stand-in yet:** voice, face, player input, cloth detail, impact sound, scene field, form, weather.
- **Saving,** the recorder's file format, the worker threads and audio.

## Commands

```bash
cd engine
npm install
npm test             # run the tests
npm run type-check   # the compiler check that every connection's types agree
npm run dev          # the demo page, in Chrome
npm run build        # type-check, then build the demo
```

The demo needs Chrome with WebGPU for the compile check. The tick itself runs anywhere.

## What the tests show

| Test file | Shows |
| --- | --- |
| `kinds.test.ts` | A Choice never picks a masked option; bounded values stay in range |
| `physics.test.ts` | Bodies stay above the floor and energy never rises without work |
| `commit.test.ts` | Counts never go negative, health never passes 100, overdrawn transfers are void |
| `tick.test.ts` | The same seed replays the same world; beats play only when allowed; speech refers only to what the mind chose to mention; replaying the recorder reproduces every output |
| `schema.test.ts` | A changed type changes its fingerprint |
| `smoke.test.ts` | Every network compiles to shader code that parses, and all five parts have a network |

## Notes for anyone adding a network

- TypeGPU is pinned to 0.12.10. It is before its 1.0 release, so upgrade deliberately.
- A network is a `tgpu.fn` whose body starts with `'use gpu'`. Give it input and output schemas from `schema.ts`, end it with one of the last layers in `kinds.ts`, and add it to `buildNetworks` in `src/networks.ts`.
- Field and function names must avoid words the shader language reserves. `from`, `target` and `cast` are reserved and `step` is a built-in, which is why the code says `giver`, `taker`, `actor` and `stepBody`.
- On unsigned numbers use `>>>`, not `>>`, and wrap whole-number constants in `d.u32(...)`.
- Weights live in a `tgpu.const` that the network's factory closes over. That is what lets one source run in both JavaScript and the shader.
