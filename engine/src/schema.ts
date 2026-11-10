/**
 * Spec 1: every value that exists between ticks, and every value that passes
 * between networks.
 *
 * Each type is written once as a TypeGPU schema. The same definition sizes the
 * GPU buffer, types the TypeScript value and types the shader. If two parts
 * disagree about a type, the TypeScript compiler rejects the build.
 *
 * Field names avoid WGSL reserved words. `from` and `target` are reserved,
 * which is why a move has a `giver` and a `taker`.
 */
import { d } from 'typegpu';
import { CAP } from './capacities.ts';

/** The width of every network's working vector, and of most codes. */
export const WIDTH = 16;
export const Vec = d.arrayOf(d.f32, WIDTH);
export const Code8 = d.arrayOf(d.f32, 8);
export const Slots = d.arrayOf(d.u32, CAP.slots);

/** Identifiers are indices into their tables. 0 means "none". */
export const EntityId = d.u32;
export const CharacterId = d.u32;

/** One physical thing, from a goblet to a limb. */
export const Body = d.struct({
  cell: d.vec3i, // which 64 m cell
  offset: d.vec3f, // metres inside the cell
  orientation: d.vec4f, // unit quaternion
  momentum: d.vec3f,
  spin: d.vec3f, // angular momentum
  mass: d.f32,
  inertia: d.vec3f,
  radius: d.f32, // coarse size, until shape codes carry it
  shape: Vec, // read by the contact and sound networks
  material: Code8, // friction, bounce, ring, surface look
  parent: EntityId,
  flags: d.u32,
});

/** What a character is trying to do. Produced by a mind or by the player. */
export const Intent = d.struct({
  goal: d.vec3f, // metres from the character's own position
  velocity: d.vec3f,
  facing: d.vec2f,
  action: d.u32, // Choice of CAP.actions
  urgency: d.f32,
  mood: d.vec4f,
});

/** A typed change to facts and counts. The only way they ever change. */
export const Move = d.struct({
  kind: d.u32, // Choice of 8 move kinds
  giver: EntityId,
  taker: EntityId,
  item: d.u32, // Choice of CAP.items; for fact moves, the fact index
  amount: d.u32, // Choice from the whole-number ladder
});

/** Two bodies touching, as reported by physics. */
export const Contact = d.struct({
  a: EntityId,
  b: EntityId,
  point: d.vec3f,
  direction: d.vec3f, // unit vector from a to b
  impulse: d.f32,
});

/** The contact network's answer for one nearby pair. */
export const ContactGeometry = d.struct({
  distance: d.f32, // metres between surfaces; negative means overlap
  direction: d.vec3f, // unit vector from a to b
});

/** What the tick gathers for one character before perception runs. */
export const Seen = d.struct({
  other: d.vec3f, // metres to the nearest other character
  otherId: EntityId,
  thing: d.vec3f, // metres to the nearest thing that is not a character
  thingId: EntityId,
  height: d.f32, // metres above the ground
  told: EntityId, // what the nearest speaker just referred to, if anything
});

/** A character's summary of what is near. */
export const Perception = d.struct({
  summary: Vec,
  otherId: EntityId,
  thingId: EntityId,
  told: EntityId,
});

/** Everything the mind network reads besides perception. */
export const MindInput = d.struct({
  identity: Vec,
  mood: d.vec4f,
  state: Vec, // the mind's own carried state
  remembered: Vec, // the strongest memory row
  beat: d.u32, // the beat this character is cast in, or 0
  health: d.f32, // own health count, scaled to 0..1
});

/** Everything the mind network writes. */
export const MindOutput = d.struct({
  intent: Intent,
  state: Vec,
  row: Vec, // a memory row to write
  rowWeight: d.f32, // how much it matters, 0..1
  say: Slots, // references handed to speech
  speak: d.u32, // 1 to start or keep talking
});

/** What the speech network reads for one speaker. */
export const SpeechInput = d.struct({
  identity: Vec,
  mood: d.vec4f,
  last: d.u32, // the last word piece
  filled: d.u32, // bit i set when slot i holds a reference
  state: Vec,
});

export const SpeechOutput = d.struct({
  piece: d.u32, // Choice of CAP.vocab word pieces plus CAP.slots slots
  state: Vec,
});

/** One event for the outcome network: a contact or a chosen action. */
export const GameEvent = d.struct({
  isContact: d.u32,
  a: EntityId,
  b: EntityId,
  impulse: d.f32,
  action: d.u32,
  allowed: d.u32, // mask over the 8 move kinds
});

/** The counts of one party to an event, gathered for the outcome network. */
export const Party = d.struct({
  health: d.f32,
  gold: d.f32,
  flags: d.u32,
});

/** What the director reads. */
export const StoryInput = d.struct({
  happened: d.u32, // bit i set when beat i has played
  allowed: d.u32, // bit i set when beat i's conditions hold now
  facts: d.u32,
  nearby: d.u32, // how many characters could be cast
  tension: d.f32,
  state: Vec,
});

export const BeatChoice = d.struct({
  beat: d.u32, // Choice of CAP.beats under the allowed mask
  actor: d.u32, // Choice among the nearby characters (`cast` is reserved in WGSL)
  state: Vec,
});

/** What the light network reads for one visible thing. */
export const LightInput = d.struct({
  material: Code8,
  facing: d.vec3f,
  view: d.vec3f,
  light: d.vec4f, // the region's light state
});

/**
 * A fingerprint of a schema: its field names, types and order, hashed.
 * Network files and saves state the fingerprints they were made for, and the
 * loader refuses a mismatch. See Spec 1, "Versions, saves and compatibility".
 */
export function describe(schema: unknown): string {
  const s = schema as {
    type?: string;
    propTypes?: Record<string, unknown>;
    elementType?: unknown;
    elementCount?: number;
  };
  if (s.type === 'struct' && s.propTypes) {
    const fields = Object.entries(s.propTypes).map(([name, t]) => `${name}:${describe(t)}`);
    return `{${fields.join(',')}}`;
  }
  if (s.type === 'array') {
    return `[${describe(s.elementType)};${s.elementCount}]`;
  }
  if (typeof s.type === 'string') {
    return s.type;
  }
  throw new Error('describe: not a schema');
}

export function fingerprint(schema: unknown): string {
  const text = describe(schema);
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h = Math.imul(h ^ text.charCodeAt(i), 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, '0');
}

/** Every connection type by name, for manifests and recordings. */
export const CONNECTIONS = {
  Body,
  Intent,
  Move,
  Contact,
  ContactGeometry,
  Seen,
  Perception,
  MindInput,
  MindOutput,
  SpeechInput,
  SpeechOutput,
  GameEvent,
  Party,
  StoryInput,
  BeatChoice,
  LightInput,
} as const;

export function fingerprints(): Record<string, string> {
  return Object.fromEntries(
    Object.entries(CONNECTIONS).map(([name, schema]) => [name, fingerprint(schema)]),
  );
}

export type Body = d.Infer<typeof Body>;
export type Intent = d.Infer<typeof Intent>;
export type Move = d.Infer<typeof Move>;
export type Contact = d.Infer<typeof Contact>;
export type Seen = d.Infer<typeof Seen>;
export type Perception = d.Infer<typeof Perception>;
export type MindOutput = d.Infer<typeof MindOutput>;
export type BeatChoice = d.Infer<typeof BeatChoice>;
export type Party = d.Infer<typeof Party>;
export type GameEvent = d.Infer<typeof GameEvent>;
