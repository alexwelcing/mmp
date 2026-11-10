/**
 * The typed state: everything that exists between ticks.
 *
 * This is the CPU reference form used by the tests and the demo page. Each row
 * is a value of a schema from schema.ts, so the same data can be written to
 * GPU buffers without conversion. A tick never changes a world in place: it
 * reads one World and returns the next. See Spec 2, "Read old, write new".
 */
import { d } from 'typegpu';
import { CAP, CELL_SIZE, FLAG, ITEM } from './capacities.ts';
import { mulberry32 } from './rng.ts';
import { Body, Intent, WIDTH } from './schema.ts';
import type { Contact } from './schema.ts';

/** A story beat: the facts it needs and the facts it changes. */
export interface Beat {
  name: string;
  needsTrue: number;
  needsFalse: number;
  sets: number;
  clears: number;
}

export interface MemoryRow {
  row: number[];
  weight: number;
}

/** One person or creature. Index 0 of the table is "none". */
export interface CharacterRow {
  name: string;
  identity: number[];
  mood: d.v4f;
  intent: Intent;
  mindState: number[];
  speechState: number[];
  memory: MemoryRow[];
  /** The entity that is this character's body. */
  root: number;
  /** The force its body network last asked for. */
  force: d.v3f;
  /** References the mind handed to speech. */
  say: number[];
  speaking: boolean;
  lastPiece: number;
  /** What its last word piece referred to, if it chose a slot. */
  lastReference: number;
  /** The beat it is cast in, or 0. */
  beat: number;
  /** The last few word pieces, kept only so the demo can show them. */
  spoken: number[];
}

export interface World {
  seed: number;
  tick: number;
  /** Index is the entity identifier. Index 0 is "none". */
  bodies: Body[];
  characters: CharacterRow[];
  /** One bit per yes-or-no fact. */
  facts: number;
  /** Whole numbers: counts[entity * CAP.items + item]. */
  counts: Uint32Array;
  story: {
    beats: Beat[];
    happened: number;
    allowed: number;
    directorState: number[];
  };
  /** Contacts reported by the last tick's physics. */
  contacts: Contact[];
  /** Colors from the light network, one per body. */
  colors: d.v3f[];
  /** Moves that were void when applied. The factory reads these as errors. */
  voidMoves: number;
}

const zeros = (n: number): number[] => Array.from({ length: n }, () => 0);

/** A body's position in metres, across cells. */
export function position(body: Body): [number, number, number] {
  return [
    body.cell.x * CELL_SIZE + body.offset.x,
    body.cell.y * CELL_SIZE + body.offset.y,
    body.cell.z * CELL_SIZE + body.offset.z,
  ];
}

export function count(world: World, entity: number, item: number): number {
  return world.counts[entity * CAP.items + item];
}

/** Which beats can be chosen now. Bit operations only: this is plumbing. */
export function allowedBeats(beats: Beat[], facts: number, happened: number): number {
  let allowed = 1; // beat 0, "no beat now", is always on the list
  for (let i = 1; i < beats.length; i++) {
    const done = (happened >>> i) & 1;
    const needs = (facts & beats[i].needsTrue) >>> 0 === beats[i].needsTrue >>> 0;
    const blocked = (facts & beats[i].needsFalse) !== 0;
    if (!done && needs && !blocked) {
      allowed |= 1 << i;
    }
  }
  return allowed >>> 0;
}

function makeBody(
  rand: () => number,
  at: [number, number, number],
  mass: number,
  radius: number,
  flags: number,
): Body {
  return Body({
    cell: d.vec3i(0, 0, 0),
    offset: d.vec3f(at[0], at[1], at[2]),
    orientation: d.vec4f(0, 0, 0, 1),
    momentum: d.vec3f(0, 0, 0),
    spin: d.vec3f(0, 0, 0),
    mass,
    inertia: d.vec3f(1, 1, 1),
    radius,
    shape: Array.from({ length: WIDTH }, () => rand() * 2 - 1),
    material: Array.from({ length: 8 }, () => rand() * 2 - 1),
    parent: 0,
    flags,
  });
}

/**
 * A small starting world: a room's worth of loose things and a few people.
 * Later this comes from a starting-state file written by the factory.
 */
export function createWorld(seed: number, people = 6, things = 12): World {
  const rand = mulberry32(seed);
  const bodies: Body[] = [makeBody(rand, [0, 0, 0], 1, 0, 0)]; // entity 0: none
  const characters: CharacterRow[] = [];
  const names = ['none', 'Ada', 'Bram', 'Cyra', 'Dov', 'Esme', 'Finn', 'Gale', 'Hale'];

  // Entity 0 has a matching character 0, so both tables start at 1.
  for (let c = 0; c <= Math.min(people, CAP.characters - 1); c++) {
    let root = 0;
    if (c > 0) {
      bodies.push(
        makeBody(rand, [rand() * 10 - 5, 0.4, rand() * 10 - 5], 70, 0.4, FLAG.character),
      );
      root = bodies.length - 1;
    }
    characters.push({
      name: names[c] ?? `Person ${c}`,
      identity: Array.from({ length: WIDTH }, () => rand() * 2 - 1),
      mood: d.vec4f(0, 0, 0, 0),
      intent: Intent(),
      mindState: zeros(WIDTH),
      speechState: zeros(WIDTH),
      memory: Array.from({ length: CAP.memoryRows }, () => ({ row: zeros(WIDTH), weight: 0 })),
      root,
      force: d.vec3f(0, 0, 0),
      say: zeros(CAP.slots),
      speaking: false,
      lastPiece: 0,
      lastReference: 0,
      beat: 0,
      spoken: [],
    });
  }

  for (let t = 0; t < things && bodies.length < CAP.entities; t++) {
    const radius = 0.1 + rand() * 0.2;
    bodies.push(
      makeBody(rand, [rand() * 10 - 5, radius + rand() * 2, rand() * 10 - 5], 0.5 + rand() * 4.5, radius, 0),
    );
  }

  const counts = new Uint32Array(CAP.entities * CAP.items);
  for (let c = 1; c < characters.length; c++) {
    counts[characters[c].root * CAP.items + ITEM.health] = 100;
    counts[characters[c].root * CAP.items + ITEM.gold] = 10;
  }
  if (characters.length > 1) {
    counts[characters[1].root * CAP.items + ITEM.key] = 1;
  }

  // A tiny story graph. Fact 0: a quarrel has started. Fact 1: it is settled.
  const beats: Beat[] = [
    { name: 'no beat', needsTrue: 0, needsFalse: 0, sets: 0, clears: 0 },
    { name: 'arrival', needsTrue: 0, needsFalse: 0, sets: 0, clears: 0 },
    { name: 'quarrel', needsTrue: 0, needsFalse: 0b01, sets: 0b01, clears: 0 },
    { name: 'reconciliation', needsTrue: 0b01, needsFalse: 0b10, sets: 0b10, clears: 0 },
    { name: 'farewell', needsTrue: 0b10, needsFalse: 0, sets: 0, clears: 0 },
  ];

  return {
    seed,
    tick: 0,
    bodies,
    characters,
    facts: 0,
    counts,
    story: {
      beats,
      happened: 0,
      allowed: allowedBeats(beats, 0, 0),
      directorState: zeros(WIDTH),
    },
    contacts: [],
    colors: bodies.map(() => d.vec3f(0.5, 0.5, 0.5)),
    voidMoves: 0,
  };
}
