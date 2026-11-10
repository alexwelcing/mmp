# Spec 1: Types and state

This spec defines every value that exists between ticks and every value that passes between networks. All other specs refer to the names defined here. The code is [`engine/src/schema.ts`](../../engine/src/schema.ts), [`engine/src/capacities.ts`](../../engine/src/capacities.ts) and [`engine/src/kinds.ts`](../../engine/src/kinds.ts).

## Conventions and capacities

Every table is stored column-wise on the GPU, one row per thing, and rows are addressed by a plain index.

- **Numbers.** Reals are 32-bit floats in the state. Network weights may be 16-bit where the device allows. Counts and identifiers are unsigned 32-bit whole numbers.
- **Identifiers.** An entity, a character, an item kind, a place and a beat are each an index into their own table. Index 0 means "none".
- **Codes.** A code is a short fixed list of floats that a network reads as a description: of a shape, a material, a person, a voice.
- **Position.** A position is a 64-metre cell plus an offset inside it, so precision is the same everywhere in a large world.

Capacities are fixed at build time so every buffer has a known size. The full-size numbers are proposed defaults. The code currently runs at the small development sizes in the last column.

| Capacity | Proposed default | In the code today |
| --- | --- | --- |
| Entities (bodies of any kind) | 16,384 | 64 |
| Characters | 1,024 | 8 |
| Contacts per tick | 32,768 | not capped |
| World facts (yes-or-no) | 4,096 | 32 |
| Count rows (owner, item kind, amount) | 65,536 | 64 owners by 4 item kinds |
| Story beats | 512 | 16 |
| Memory rows per character | 16 | 4 |
| Actions a character can choose from | 64 | 8 |
| Word pieces, plus slots | 4,096 plus 8 | 12 plus 4 |

## The state tables

The state is six tables. Together they are everything that exists between ticks.

### Body

One row per physical thing, from a goblet to a limb.

| Field | Type | Meaning |
| --- | --- | --- |
| cell, offset | 3 whole numbers, 3 floats | Position |
| orientation | 4 floats | Unit quaternion |
| momentum, spin | 3 floats each | Linear and angular momentum |
| mass, inertia | 1 float, 3 floats | Mass and principal inertia |
| radius | 1 float | Coarse size. A stand-in until shape codes carry it |
| shape | code of 16 | What the contact and sound networks read |
| material | code of 8 | Friction, bounce, ring, and surface look |
| parent, joint | identifier, 8 floats | For limbs: the body it hangs from and the joint's frame and limits. The joint fields are not built yet |
| flags | bit set | Asleep, held, part of a character, and so on |

### Facts

A bit set of yes-or-no facts about the world: the emperor is alive, the gate is open, this shrine was found.

### Counts

Rows of owner, item kind and amount. Health, stamina and gold are counts like any other.

### Story

| Field | Type | Meaning |
| --- | --- | --- |
| happened | bit set, one bit per beat | Beats already played |
| allowed | bit set, one bit per beat | Beats whose conditions hold now. Recomputed every tick |
| needs true, needs false | bit sets over the facts, per beat | The facts a beat requires |
| sets, clears | bit sets over the facts, per beat | The facts a beat changes when played |

### Character

One row per person or creature.

| Field | Type | Meaning |
| --- | --- | --- |
| identity | code of 16 | Who they are: read by mind, speech and face |
| voice | code of 16 | How they sound |
| style | code of 8 | How they move |
| mood | 4 floats | Current feeling |
| intent | Intent | What they are trying to do now |
| mind state | 32 floats (16 today) | The mind network's carried state |
| speech state | 1,024 floats (16 today) | The speech network's carried state while talking |
| memory | rows of floats, with a weight per row | What they remember |
| root | entity identifier | Their body |

### Region

One row per region of the world: the scene data to load, its bounds, and its light and weather state. Not built yet.

## The three kinds of type

Every network output is one of three kinds. Each kind fixes the network's last layer, and that layer is what makes an illegal value impossible.

| Kind | Value | Last layer | What it rules out |
| --- | --- | --- | --- |
| Choice of N | An index from 0 to N minus 1 | The network emits N scores. A mask marks the options allowed now. The highest-scoring allowed option wins, lowest index on a tie | Choosing something not on offer: a beat whose conditions fail, an item not held, a name not in the state |
| Move | A kind, two identifiers, an item kind and an amount | The kind is a Choice. Identifiers are Choices over the entities involved in the event. The amount is a Choice over a short ladder of whole numbers | Fractional gold, items from nowhere, a transfer between strangers to the event |
| Bounded | Floats inside a stated range | A fixed final step pulls the raw output into range | Overlapping solids, a force beyond a joint's strength, energy appearing from nothing |

Option 0 of every Choice means "none" and is always allowed, so a Choice always has a legal answer.

The move kinds are: none, transfer, damage, restore, set fact, clear fact, appear, vanish. The amount ladder is 0, 1, 2, 5, 10, 20, 50, 100.

A move is applied to the Counts and Facts tables by whole-number arithmetic ([`engine/src/commit.ts`](../../engine/src/commit.ts)). A transfer of more than the owner holds is void and is logged for the factory as a training error. Counts therefore never go negative.

The three bounding steps are:

- **Outside.** Push a point out of any solid along the contact direction until the distance is zero or more.
- **Within.** Scale a vector down to a stated maximum length, such as a joint's strength.
- **No gain.** Scale momenta so that total energy after the step does not exceed energy before it plus the work put in by characters.

## The definitions as code

Each type is written once as a [TypeGPU](https://docs.swmansion.com/TypeGPU/) schema. The same definition sizes the GPU buffer, types the TypeScript value and types the shader. This excerpt is from `engine/src/schema.ts`, written against TypeGPU 0.12.10.

```ts
import { d } from 'typegpu';

// Identifiers are indices into their tables. 0 means none.
export const EntityId = d.u32;

export const Move = d.struct({
  kind: d.u32,      // Choice of 8 move kinds
  giver: EntityId,
  taker: EntityId,
  item: d.u32,      // Choice of item kinds; for fact moves, the fact index
  amount: d.u32,    // Choice from the whole-number ladder
});

export const Contact = d.struct({
  a: EntityId,
  b: EntityId,
  point: d.vec3f,
  direction: d.vec3f, // unit vector from a to b
  impulse: d.f32,
});
```

A network is a typed function, and its signature is the contract:

```ts
// engine/src/parts/mechanics.ts
tgpu.fn([GameEvent, Party, Party], Move)((event, a, b) => {
  'use gpu';
  // layers, then the Move last layer
});
```

If the outcome network were handed an Intent where it expects a GameEvent, the TypeScript compiler would reject the build. That check is the type safety of the whole game.

### Names the shader language reserves

Schemas become shader structs, so field and function names must avoid words the shader language (WGSL) keeps for itself. Three were hit while building:

- `from` and `target` are reserved, so a move has a `giver` and a `taker`.
- `cast` is reserved, so the director's chosen character is the `actor`.
- `step` is a built-in function, so the physics step network is named `stepBody`.

## Versions, saves and compatibility

Types are checked twice: by the compiler when the game is built, and by a fingerprint when files are loaded.

- **Type fingerprint.** Each schema has a fingerprint computed from its field names, types and order. Changing a schema changes its fingerprint. Built: `fingerprint()` in `schema.ts`.
- **Network files.** Every network file states the fingerprints of its input and output types. The loader refuses a file whose fingerprints do not match the running build. Not built yet.
- **Saves.** A save holds the six state tables, the tick number, the random seed, and the name and version of every network. A save loads only against the networks it names. Not built yet.
- **Changing a type.** A changed type means retraining every network that touches it. The connection table in the [architecture](architecture.md) shows which those are.
