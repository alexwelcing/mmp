# The Living World Engine

A game where the mechanics, the physics, the plot, the world and the characters are all small neural networks, joined through typed connections so that together they are one complete, type-safe game. It runs in Chrome on WebGPU, written with TypeGPU.

| Page | What it covers |
| --- | --- |
| [Architecture](architecture.md) | The idea, the principles, the five parts, the build order, the open bets |
| [Spec 1: Types and state](spec-1-types-and-state.md) | The six state tables and the three kinds of type that carry the guarantees |
| [Spec 2: The tick](spec-2-the-tick.md) | The seven phases, write order, random numbers, the recorder |
| [Spec 3: The networks](spec-3-the-networks.md) | Every network: reads, writes, size, rate, and how it is judged |
| [Spec 4: The factory](spec-4-the-factory.md) | How canon becomes trained networks |
| [Spec 5: Browser runtime](spec-5-browser-runtime.md) | Threads, loading, GPU resources, failure handling |

The code is in [`engine/`](../../engine/README.md). Its README says what is built and what is not.

Sizes, budgets and data amounts in these pages are proposed starting points. None is measured yet.
