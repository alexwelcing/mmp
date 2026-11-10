/**
 * The Characters part: perception, mind, speech and body.
 *
 * All characters share these networks. A character is a row of typed state;
 * one more character is one more row in each batch. See Spec 3, "Characters".
 *
 * Not built yet: voice, face, and the input network for the player.
 */
import tgpu, { d, std } from 'typegpu';
import { CAP, STRENGTH } from '../capacities.ts';
import { choose, within, zeroToOne } from '../kinds.ts';
import { makeMlp } from '../mlp.ts';
import {
  Body,
  Intent,
  MindInput,
  MindOutput,
  Perception,
  Seen,
  Slots,
  SpeechInput,
  SpeechOutput,
  Vec,
  WIDTH,
} from '../schema.ts';

/** Every action is always on offer. Action 0 is "do nothing". */
const ALL_ACTIONS = (1 << CAP.actions) - 1;

/** Perception: what is near, as a summary the mind can read. */
export function makePerceive(seed: number) {
  const net = makeMlp('perceive', seed);
  return tgpu
    .fn([Seen], Perception)((seen) => {
      'use gpu';
      const x = Vec();
      x[0] = seen.other.x * 0.1;
      x[1] = seen.other.y * 0.1;
      x[2] = seen.other.z * 0.1;
      x[3] = seen.thing.x * 0.1;
      x[4] = seen.thing.y * 0.1;
      x[5] = seen.thing.z * 0.1;
      x[6] = seen.height;
      x[7] = std.min(d.f32(seen.told), 1);
      const y = net(x);
      const summary = Vec();
      for (let i = 0; i < WIDTH; i++) {
        summary[i] = std.tanh(y[i]);
      }
      // The identifiers pass straight through. They are what the mind may
      // later choose to refer to.
      return Perception({
        summary: summary,
        otherId: seen.otherId,
        thingId: seen.thingId,
        told: seen.told,
      });
    })
    .$name('perceive');
}

/**
 * Mind: perception, memory and the current beat become intent, things to say
 * and a memory row to write.
 */
export function makeMind(seed: number) {
  const trunk = makeMlp('mind_trunk', seed);
  const motionHead = makeMlp('mind_motion', seed + 1);
  const actionHead = makeMlp('mind_action', seed + 2);
  const sayHead = makeMlp('mind_say', seed + 3);
  const rowHead = makeMlp('mind_row', seed + 4);

  return tgpu
    .fn([Perception, MindInput], MindOutput)((seen, me) => {
      'use gpu';
      const x = Vec();
      for (let i = 0; i < WIDTH; i++) {
        x[i] =
          seen.summary[i] + 0.5 * me.identity[i] + 0.5 * me.state[i] + 0.25 * me.remembered[i];
      }
      x[0] += me.mood.x;
      x[1] += me.mood.y;
      x[2] += d.f32(me.beat) * 0.1;
      x[3] += me.health;

      const core = trunk(x);
      const motion = motionHead(core);
      const actionScores = actionHead(core);
      const sayScores = sayHead(core);
      const rowRaw = rowHead(core);

      // Last layers. Goal and velocity are Bounded; action is a Choice.
      const goal = within(
        std.mul(5, d.vec3f(std.tanh(motion[0]), std.tanh(motion[1]), std.tanh(motion[2]))),
        5,
      );
      const velocity = within(
        std.mul(2, d.vec3f(std.tanh(motion[3]), std.tanh(motion[4]), std.tanh(motion[5]))),
        2,
      );
      const action = choose(actionScores, CAP.actions, d.u32(ALL_ACTIONS));

      // Each slot is a Choice among what this character can refer to:
      // nothing, the nearest person, the nearest thing, or what it was told.
      let canRefer = d.u32(1);
      if (seen.otherId > 0) {
        canRefer = canRefer | 2;
      }
      if (seen.thingId > 0) {
        canRefer = canRefer | 4;
      }
      if (seen.told > 0) {
        canRefer = canRefer | 8;
      }
      const say = Slots();
      for (let s = 0; s < CAP.slots; s++) {
        const slotScores = Vec();
        for (let k = 0; k < 4; k++) {
          slotScores[k] = sayScores[s * 4 + k];
        }
        const pick = choose(slotScores, 4, canRefer);
        let reference = d.u32(0);
        if (pick === 1) {
          reference = seen.otherId;
        }
        if (pick === 2) {
          reference = seen.thingId;
        }
        if (pick === 3) {
          reference = seen.told;
        }
        say[s] = reference;
      }

      const state = Vec();
      const row = Vec();
      for (let i = 0; i < WIDTH; i++) {
        state[i] = std.tanh(core[i]);
        row[i] = std.tanh(rowRaw[i]);
      }
      let speak = d.u32(0);
      if (motion[13] > 0) {
        speak = 1;
      }

      return MindOutput({
        intent: Intent({
          goal: goal,
          velocity: velocity,
          facing: d.vec2f(std.tanh(motion[6]), std.tanh(motion[7])),
          action: action,
          urgency: zeroToOne(motion[8]),
          mood: d.vec4f(
            std.tanh(motion[9]),
            std.tanh(motion[10]),
            std.tanh(motion[11]),
            std.tanh(motion[12]),
          ),
        }),
        state: state,
        row: row,
        rowWeight: zeroToOne(motion[14]),
        say: say,
        speak: speak,
      });
    })
    .$name('mind');
}

/** Every word piece is always allowed; a slot only when the mind filled it. */
const VOCAB_MASK = (1 << CAP.vocab) - 1;

/**
 * Speech: the next word piece for one speaker.
 *
 * The vocabulary is CAP.vocab word pieces plus CAP.slots slots. The network
 * can choose a slot but cannot invent what is in it, so a character can only
 * name what its mind chose to mention.
 */
export function makeSpeech(seed: number) {
  const trunk = makeMlp('speech_trunk', seed);
  const head = makeMlp('speech_head', seed + 1);
  return tgpu
    .fn([SpeechInput], SpeechOutput)((s) => {
      'use gpu';
      const x = Vec();
      for (let i = 0; i < WIDTH; i++) {
        x[i] = 0.5 * s.identity[i] + s.state[i];
      }
      x[0] += s.mood.x;
      x[1] += s.mood.y;
      x[2] += d.f32(s.last) * 0.1;
      const core = trunk(x);
      const scores = head(core);
      const mask = VOCAB_MASK | (s.filled << CAP.vocab);
      const piece = choose(scores, CAP.vocab + CAP.slots, mask);
      const state = Vec();
      for (let i = 0; i < WIDTH; i++) {
        state[i] = std.tanh(core[i]);
      }
      return SpeechOutput({ piece: piece, state: state });
    })
    .$name('speech');
}

/**
 * Body: intent becomes a force on the character's root, bounded by strength.
 * Jointed bodies with per-joint targets come with the trained controller.
 */
export function makeBody(seed: number) {
  const net = makeMlp('body', seed);
  return tgpu
    .fn([Intent, Body], d.vec3f)((intent, body) => {
      'use gpu';
      const x = Vec();
      x[0] = intent.goal.x * 0.2;
      x[1] = intent.goal.y * 0.2;
      x[2] = intent.goal.z * 0.2;
      x[3] = intent.velocity.x;
      x[4] = intent.velocity.y;
      x[5] = intent.velocity.z;
      x[6] = body.momentum.x / body.mass;
      x[7] = body.momentum.y / body.mass;
      x[8] = body.momentum.z / body.mass;
      x[9] = intent.urgency;
      x[10] = d.f32(intent.action) * 0.1;
      const y = net(x);
      const raw = std.mul(STRENGTH, d.vec3f(std.tanh(y[0]), std.tanh(y[1]), std.tanh(y[2])));
      return within(raw, STRENGTH);
    })
    .$name('body');
}
