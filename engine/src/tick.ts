/**
 * Spec 2: one tick.
 *
 * A tick always runs the same seven phases. Six run networks. One, the commit,
 * applies typed values and runs none. This file is the CPU reference: it calls
 * the same typed functions the GPU will run, one row at a time.
 *
 * Everything outside a network call here is plumbing. It gathers rows for a
 * network or applies a typed value a network produced. It never decides what
 * happens.
 */
import { d } from 'typegpu';
import {
  CAP,
  CELL_SIZE,
  FLAG,
  ITEM,
  MIND_PERIOD,
  MOVE,
  PHYSICS_STEPS,
  PLOT_PERIOD,
  SPEECH_PERIOD,
} from './capacities.ts';
import { commitMoves } from './commit.ts';
import type { Networks } from './networks.ts';
import {
  Body,
  Contact,
  GameEvent,
  LightInput,
  MindInput,
  Party,
  Seen,
  SpeechInput,
  StoryInput,
} from './schema.ts';
import type { Move, Perception } from './schema.ts';
import { allowedBeats, count, position } from './state.ts';
import type { CharacterRow, MemoryRow, World } from './state.ts';

/** Pairs closer than this are shown to the contact network. */
const NEAR_METRES = 2;
/** A contact softer than this is not an event for the rules. */
const EVENT_IMPULSE = 1;
/** Memory weights fade a little every tick. */
const MEMORY_FADE = 0.999;

const zeros = (n: number): number[] => Array.from({ length: n }, () => 0);
const sub = (p: number[], q: number[]): [number, number, number] => [
  p[0] - q[0],
  p[1] - q[1],
  p[2] - q[2],
];
const length = (v: number[]): number => Math.hypot(v[0], v[1], v[2]);

/** Move whole cells out of the offset so it stays inside one cell. */
function settleCell(body: Body): Body {
  const cell = [body.cell.x, body.cell.y, body.cell.z];
  const offset = [body.offset.x, body.offset.y, body.offset.z];
  let moved = false;
  for (let k = 0; k < 3; k++) {
    const carry = Math.floor(offset[k] / CELL_SIZE);
    if (carry !== 0) {
      cell[k] += carry;
      offset[k] -= carry * CELL_SIZE;
      moved = true;
    }
  }
  if (!moved) {
    return body;
  }
  return Body({
    ...body,
    cell: d.vec3i(cell[0], cell[1], cell[2]),
    offset: d.vec3f(offset[0], offset[1], offset[2]),
  });
}

/** Phase 1. Gather what each character can see, then run perception. */
function perceive(world: World, nets: Networks): Perception[] {
  const out: Perception[] = [];
  for (let c = 0; c < world.characters.length; c++) {
    const me = world.characters[c];
    const here = position(world.bodies[me.root]);
    let other = 0;
    let otherApart: number[] = [0, 0, 0];
    let otherDistance = Infinity;
    let thing = 0;
    let thingApart: number[] = [0, 0, 0];
    let thingDistance = Infinity;
    let told = 0;

    if (c > 0) {
      for (let e = 1; e < world.bodies.length; e++) {
        if (e === me.root) {
          continue;
        }
        const apart = sub(position(world.bodies[e]), here);
        const dist = length(apart);
        if (world.bodies[e].flags & FLAG.character) {
          if (dist < otherDistance) {
            other = e;
            otherApart = apart;
            otherDistance = dist;
          }
        } else if (dist < thingDistance) {
          thing = e;
          thingApart = apart;
          thingDistance = dist;
        }
      }
      // What the nearest person just referred to is perceived as "told".
      const speaker = world.characters.find((p) => p.root === other);
      if (speaker && speaker.speaking) {
        told = speaker.lastReference;
      }
    }

    out.push(
      nets.perceive(
        Seen({
          other: d.vec3f(otherApart[0], otherApart[1], otherApart[2]),
          otherId: other,
          thing: d.vec3f(thingApart[0], thingApart[1], thingApart[2]),
          thingId: thing,
          height: here[1],
          told,
        }),
      ),
    );
  }
  return out;
}

/** Phase 2. Minds, speech and bodies for every character. */
function runCharacters(world: World, nets: Networks, seen: Perception[]): CharacterRow[] {
  return world.characters.map((me, c) => {
    if (c === 0) {
      return me;
    }
    let next: CharacterRow = {
      ...me,
      memory: me.memory.map((m) => ({ row: m.row, weight: m.weight * MEMORY_FADE })),
    };

    // Mind: 4 times a second, spread across ticks so the cost per tick is flat.
    if ((world.tick + c) % MIND_PERIOD === 0) {
      const strongest = next.memory.reduce((p, q) => (q.weight > p.weight ? q : p));
      const out = nets.mind(
        seen[c],
        MindInput({
          identity: me.identity,
          mood: me.mood,
          state: me.mindState,
          remembered: strongest.row,
          beat: me.beat,
          health: Math.min(1, count(world, me.root, ITEM.health) / 100),
        }),
      );
      // Writing memory replaces the weakest row.
      let weakest = 0;
      for (let r = 1; r < next.memory.length; r++) {
        if (next.memory[r].weight < next.memory[weakest].weight) {
          weakest = r;
        }
      }
      const memory: MemoryRow[] = next.memory.map((m, r) =>
        r === weakest ? { row: [...out.row], weight: out.rowWeight } : m,
      );
      next = {
        ...next,
        intent: out.intent,
        mood: out.intent.mood,
        mindState: [...out.state],
        memory,
        say: [...out.say],
        speaking: out.speak === 1,
      };
    }

    // Speech: the next word piece for everyone who is talking.
    if (next.speaking && (world.tick + c) % SPEECH_PERIOD === 0) {
      let filled = 0;
      for (let s = 0; s < CAP.slots; s++) {
        if (next.say[s] > 0) {
          filled |= 1 << s;
        }
      }
      const out = nets.speech(
        SpeechInput({
          identity: me.identity,
          mood: next.mood,
          last: next.lastPiece,
          filled,
          state: next.speechState,
        }),
      );
      // A slot piece is read out from the state: it names what the mind chose.
      const reference = out.piece >= CAP.vocab ? next.say[out.piece - CAP.vocab] : 0;
      next = {
        ...next,
        lastPiece: out.piece,
        lastReference: reference,
        speechState: [...out.state],
        speaking: out.piece !== 0, // piece 0 is silence: the utterance ends
        spoken: [...next.spoken, out.piece].slice(-12),
      };
    }

    // Body: intent becomes a force on the character's own root.
    next = { ...next, force: nets.body(next.intent, world.bodies[me.root]) };
    return next;
  });
}

/** Phase 3. One physics step: contacts, impulses, then every body advances. */
function physicsStep(
  bodies: Body[],
  forces: Map<number, d.v3f>,
  nets: Networks,
): { bodies: Body[]; contacts: Contact[] } {
  const impulses = bodies.map(() => [0, 0, 0]);
  const contacts: Contact[] = [];
  const at = bodies.map(position);

  for (let a = 1; a < bodies.length; a++) {
    for (let b = a + 1; b < bodies.length; b++) {
      const apart = sub(at[b], at[a]);
      if (length(apart) > NEAR_METRES) {
        continue;
      }
      const geometry = nets.contact(bodies[a], bodies[b], d.vec3f(apart[0], apart[1], apart[2]));
      if (geometry.distance >= 0) {
        continue;
      }
      const push = nets.impulse(geometry, bodies[a], bodies[b]);
      const dir = geometry.direction;
      // Equal and opposite. This gather is what conserves momentum.
      impulses[a] = [impulses[a][0] - push * dir.x, impulses[a][1] - push * dir.y, impulses[a][2] - push * dir.z];
      impulses[b] = [impulses[b][0] + push * dir.x, impulses[b][1] + push * dir.y, impulses[b][2] + push * dir.z];
      contacts.push(
        Contact({
          a,
          b,
          point: d.vec3f(
            at[a][0] + apart[0] / 2,
            at[a][1] + apart[1] / 2,
            at[a][2] + apart[2] / 2,
          ),
          direction: dir,
          impulse: push,
        }),
      );
    }
  }

  const none = d.vec3f(0, 0, 0);
  const next = bodies.map((body, e) =>
    e === 0
      ? body
      : settleCell(
          nets.step(
            body,
            d.vec3f(impulses[e][0], impulses[e][1], impulses[e][2]),
            forces.get(e) ?? none,
          ),
        ),
  );
  return { bodies: next, contacts };
}

/** Phase 4. Turn contacts and chosen actions into events for the rules. */
function runMechanics(
  world: World,
  characters: CharacterRow[],
  bodies: Body[],
  contacts: Contact[],
  seen: Perception[],
  nets: Networks,
): Move[] {
  const party = (entity: number): Party =>
    Party({
      health: count(world, entity, ITEM.health) / 100,
      gold: count(world, entity, ITEM.gold),
      flags: bodies[entity].flags,
    });
  const moves: Move[] = [];

  // Contacts that involve a character and are hard enough to matter.
  for (const c of contacts) {
    const involvesCharacter = ((bodies[c.a].flags | bodies[c.b].flags) & FLAG.character) !== 0;
    if (!involvesCharacter || c.impulse < EVENT_IMPULSE) {
      continue;
    }
    const allowed = (1 << MOVE.none) | (1 << MOVE.damage);
    moves.push(
      nets.outcome(
        GameEvent({ isContact: 1, a: c.a, b: c.b, impulse: c.impulse, action: 0, allowed }),
        party(c.a),
        party(c.b),
      ),
    );
  }

  // Actions a character chose this tick, aimed at the nearest other person.
  for (let c = 1; c < characters.length; c++) {
    const me = characters[c];
    const thinksNow = (world.tick + c) % MIND_PERIOD === 0;
    if (!thinksNow || me.intent.action === 0 || seen[c].otherId === 0) {
      continue;
    }
    const allowed =
      (1 << MOVE.none) |
      (1 << MOVE.transfer) |
      (1 << MOVE.restore) |
      (1 << MOVE.setFact) |
      (1 << MOVE.clearFact);
    moves.push(
      nets.outcome(
        GameEvent({
          isContact: 0,
          a: me.root,
          b: seen[c].otherId,
          impulse: 0,
          action: me.intent.action,
          allowed,
        }),
        party(me.root),
        party(seen[c].otherId),
      ),
    );
  }
  return moves;
}

/** One tick. Reads `world` and returns the next world; `world` is unchanged. */
export function tick(world: World, nets: Networks): World {
  // 1. Perceive
  const seen = perceive(world, nets);

  // 2. Characters
  let characters = runCharacters(world, nets, seen);

  // 3. Physics
  const forces = new Map<number, d.v3f>();
  for (let c = 1; c < characters.length; c++) {
    forces.set(characters[c].root, characters[c].force);
  }
  let bodies = world.bodies;
  let contacts: Contact[] = [];
  for (let s = 0; s < PHYSICS_STEPS; s++) {
    const stepped = physicsStep(bodies, forces, nets);
    bodies = stepped.bodies;
    contacts = contacts.concat(stepped.contacts);
  }

  // 4. Mechanics
  const moves = runMechanics(world, characters, bodies, contacts, seen, nets);

  // 5. Plot
  let story = world.story;
  let beatFacts = { sets: 0, clears: 0 };
  if (world.tick % PLOT_PERIOD === 0) {
    const nearby = Math.min(characters.length - 1, 8);
    const choice = nets.director(
      StoryInput({
        happened: story.happened,
        allowed: story.allowed,
        facts: world.facts,
        nearby,
        tension: Math.min(1, contacts.length * 0.1),
        state: story.directorState,
      }),
    );
    story = { ...story, directorState: [...choice.state] };
    if (choice.beat !== 0) {
      const beat = story.beats[choice.beat];
      story = { ...story, happened: (story.happened | (1 << choice.beat)) >>> 0 };
      beatFacts = { sets: beat.sets, clears: beat.clears };
      // The chosen character reads the beat as part of its next perception.
      const cast = choice.actor + 1;
      characters = characters.map((p, c) => (c === cast ? { ...p, beat: choice.beat } : p));
    }
  }

  // 6. Commit. No network runs here.
  const committed = commitMoves(world.counts, world.facts, moves);
  const facts = ((committed.facts | beatFacts.sets) & ~beatFacts.clears) >>> 0;
  story = { ...story, allowed: allowedBeats(story.beats, facts, story.happened) };

  // 7. Draw. The light network colors every body. The demo page draws them.
  const hour = (world.tick / 600) % (2 * Math.PI);
  const light = d.vec4f(Math.sin(hour), Math.cos(hour), 0, 0);
  const colors = bodies.map((body) =>
    nets.light(
      LightInput({
        material: body.material,
        facing: d.vec3f(0, 1, 0),
        view: d.vec3f(0, -1, 0),
        light,
      }),
    ),
  );

  return {
    seed: world.seed,
    tick: world.tick + 1,
    bodies,
    characters,
    facts,
    counts: committed.counts,
    story,
    contacts,
    colors,
    voidMoves: world.voidMoves + committed.voided,
  };
}

/** A short text digest of a world, for checking that two runs agree. */
export function digest(world: World): string {
  const text = JSON.stringify(
    [world.tick, world.bodies, world.characters, world.facts, Array.from(world.counts), world.story],
  );
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h = Math.imul(h ^ text.charCodeAt(i), 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, '0');
}

export { zeros };
